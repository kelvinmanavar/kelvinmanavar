"""Unit tests for profile_gen.main.main (orchestration).

Fetchers are replaced with in-module fakes; renderers, markers, and file I/O
are real and operate on tmp_path copies of README.md and profile.config.json.
"""
from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from profile_gen import main as main_mod
from profile_gen import markers
from profile_gen.client import ApiError, AuthError, RateLimitError
from profile_gen.models import Calendar, CalendarDay, Stats

REPO_ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2025, 6, 1, tzinfo=timezone.utc)
TOKEN = "ghp_secrettoken123"


class FakeClient:
    def __init__(self, token: str, reject: bool = False) -> None:
        self.token = token
        self.reject = reject

    def graphql(self, query, variables=None):
        if self.reject and self.token:
            raise AuthError(f"401 bad credentials for {self.token}")
        return {"viewer": {"login": "x"}}


class Factory:
    def __init__(self, reject: bool = False) -> None:
        self.tokens: list[str] = []
        self.reject = reject

    def __call__(self, token: str) -> FakeClient:
        self.tokens.append(token)
        return FakeClient(token, self.reject)


def _stats() -> Stats:
    return Stats(
        total_commits=5, prs_opened=1, prs_merged=1, issues_opened=0,
        reviews=2, repos_contributed_to=1, languages={"Python": 100},
        current_streak=1, longest_streak=3,
    )


def _calendar() -> Calendar:
    d0 = date(2025, 5, 1)
    return Calendar(days=tuple(CalendarDay(d0 + timedelta(days=i), i % 4) for i in range(30)))


@pytest.fixture
def modes():
    return []


@pytest.fixture
def root(tmp_path, monkeypatch, modes):
    shutil.copy(REPO_ROOT / "README.md", tmp_path / "README.md")
    shutil.copy(REPO_ROOT / "profile.config.json", tmp_path / "profile.config.json")
    monkeypatch.setattr(main_mod, "fetch_featured", lambda c, cfg: [])
    monkeypatch.setattr(
        main_mod, "fetch_stats", lambda c, cfg, mode, now: (modes.append(mode), _stats())[1]
    )
    monkeypatch.setattr(main_mod, "fetch_activity", lambda c, cfg: [])
    monkeypatch.setattr(main_mod, "fetch_contributions", lambda c, cfg, mode, now: [])
    monkeypatch.setattr(main_mod, "fetch_calendar", lambda c, cfg, now: _calendar())
    return tmp_path


def run(root, env=None, factory=None):
    return main_mod.main(
        ["--root", str(root)], env or {}, factory or Factory(), NOW
    )


def body(root, name):
    return markers.extract((root / "README.md").read_text(encoding="utf-8"), name)


def svg_paths(root):
    return [root / "assets" / f"contribution-graph-{t}.svg" for t in ("dark", "light")]


# --- mode selection (12.3, 12.4) ---

def test_no_token_uses_public_mode(root, modes):
    factory = Factory()
    assert run(root, {}, factory) == 0
    assert modes == ["public"]
    assert factory.tokens == [""]


def test_valid_token_uses_extended_mode(root, modes):
    factory = Factory()
    assert run(root, {"PROFILE_STATS_TOKEN": TOKEN}, factory) == 0
    assert modes == ["extended"]
    assert factory.tokens == [TOKEN]


# --- auth fallback (12.4, 13.3) ---

def test_rejected_token_falls_back_to_public_with_redacted_warning(root, modes, caplog):
    factory = Factory(reject=True)
    with caplog.at_level("DEBUG"):
        assert run(root, {"PROFILE_STATS_TOKEN": TOKEN}, factory) == 0
    assert modes == ["public"]
    assert factory.tokens == [TOKEN, ""]
    assert "WARNING" in caplog.text
    assert TOKEN not in caplog.text


# --- per-section fallback (11.5, 12.7) ---

def test_section_api_error_keeps_previous_body_and_exits_zero(root, monkeypatch, caplog):
    def boom(c, cfg, mode, now):
        raise ApiError("server down")

    monkeypatch.setattr(main_mod, "fetch_stats", boom)
    before = body(root, "STATS")
    with caplog.at_level("DEBUG"):
        assert run(root) == 0
    assert body(root, "STATS") == before
    assert "ERROR section=STATS" in caplog.text
    # other sections still updated
    assert body(root, "GRAPH") != "_Contribution graph will appear here._"
    assert "No recent public activity." in body(root, "ACTIVITY")


# --- calendar failure (6.4) ---

def test_calendar_failure_leaves_svgs_unchanged(root, monkeypatch):
    assert run(root) == 0
    paths = svg_paths(root)
    originals = [p.read_bytes() for p in paths]
    assert all(originals)

    def boom(c, cfg, now):
        raise ApiError("calendar down")

    monkeypatch.setattr(main_mod, "fetch_calendar", boom)
    monkeypatch.setattr(
        main_mod, "render_graph_svg", lambda cal, theme: pytest.fail("must not render")
    )
    assert run(root) == 0
    assert [p.read_bytes() for p in paths] == originals


def test_calendar_failure_without_existing_svgs_creates_none(root, monkeypatch):
    def boom(c, cfg, now):
        raise ApiError("calendar down")

    monkeypatch.setattr(main_mod, "fetch_calendar", boom)
    assert run(root) == 0
    assert not any(p.exists() for p in svg_paths(root))


# --- forced exception writes nothing (11.5, 13.2) ---

def test_exception_after_two_sections_writes_nothing(root, monkeypatch):
    def boom():
        raise RuntimeError("unexpected")

    monkeypatch.setattr(main_mod, "render_graph_picture", boom)  # third section
    readme_before = (root / "README.md").read_bytes()
    with pytest.raises(RuntimeError):
        run(root)
    assert (root / "README.md").read_bytes() == readme_before
    assert not (root / "assets").exists()


# --- rate limit (12.7, 13.2) ---

def test_rate_limit_exits_nonzero_and_writes_nothing(root, monkeypatch, caplog):
    reset = datetime(2025, 6, 1, 1, 0, tzinfo=timezone.utc)

    def limited(c, cfg):
        raise RateLimitError("limit", reset)

    monkeypatch.setattr(main_mod, "fetch_activity", limited)
    readme_before = (root / "README.md").read_bytes()
    with caplog.at_level("DEBUG"):
        code = run(root)
    assert code != 0
    assert reset.isoformat() in caplog.text
    assert (root / "README.md").read_bytes() == readme_before
    assert not (root / "assets").exists()


def test_rate_limit_during_calendar_fetch_exits_nonzero(root, monkeypatch):
    def limited(c, cfg, now):
        raise RateLimitError("limit", NOW)

    monkeypatch.setattr(main_mod, "fetch_calendar", limited)
    readme_before = (root / "README.md").read_bytes()
    assert run(root) != 0
    assert (root / "README.md").read_bytes() == readme_before
