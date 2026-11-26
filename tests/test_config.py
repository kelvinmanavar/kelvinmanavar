"""Unit tests for config loading. Validates: Requirements 14.1"""
import json

import pytest

from profile_gen.config import ConfigError, load_config


def _write(tmp_path, data):
    p = tmp_path / "profile.config.json"
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return p


def test_valid_config_loads(tmp_path):
    p = _write(tmp_path, {
        "owner": "kelvinmanavar",
        "featured_repos": ["kelvinmanavar/app", "org/some.repo"],
        "org_allow_list": ["org"],
        "feed_length": 5,
        "contribution_period_days": 90,
    })
    cfg = load_config(p)
    assert cfg.owner == "kelvinmanavar"
    assert cfg.profile_repo == "kelvinmanavar/kelvinmanavar"
    assert cfg.featured_repos == ["kelvinmanavar/app", "org/some.repo"]
    assert cfg.org_allow_list == ["org"]
    assert cfg.feed_length == 5
    assert cfg.contribution_period_days == 90


def test_repo_config_file_loads():
    from pathlib import Path
    cfg = load_config(Path(__file__).resolve().parent.parent / "profile.config.json")
    assert cfg.owner == "kelvinmanavar"


def test_missing_owner_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, {"featured_repos": []}))


@pytest.mark.parametrize("data", [
    {"owner": 123},
    {"owner": "me", "featured_repos": "a/b"},
    {"owner": "me", "org_allow_list": [1]},
    {"owner": "me", "feed_length": "10"},
    {"owner": "me", "feed_length": True},
])
def test_wrong_type_raises(tmp_path, data):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, data))


@pytest.mark.parametrize("entry", ["noslash", "a/b/c", "/name", "owner/", "bad owner/x"])
def test_invalid_owner_name_entry_raises(tmp_path, entry):
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, {"owner": "me", "featured_repos": [entry]}))
