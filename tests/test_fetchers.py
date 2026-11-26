"""Unit tests for fetchers using a mocked GitHub client.

Validates: Requirements 7.4, 8.1, 9.4, 12.5
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from profile_gen.client import ApiError
from profile_gen.config import Config
from profile_gen.fetch.activity import fetch_activity
from profile_gen.fetch.contributions import fetch_contributions
from profile_gen.fetch.featured import fetch_featured

NOW = datetime(2024, 6, 1, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, graphql=None, pages=None):
        self._graphql = graphql
        self._pages = pages or []
        self.graphql_calls = []
        self.rest_paths = []

    def graphql(self, query, variables=None):
        self.graphql_calls.append(variables)
        if callable(self._graphql):
            return self._graphql(variables)
        return self._graphql

    def rest_pages(self, path, *a, **k):
        self.rest_paths.append(path)
        return iter(self._pages)


def cfg(**kw) -> Config:
    base = dict(owner="me", profile_repo="me/me")
    base.update(kw)
    return Config(**base)


# ---------- featured ----------

def _repo_node(name, private=False):
    return {
        "repository": {
            "nameWithOwner": name,
            "url": f"https://github.com/{name}",
            "description": "d",
            "isPrivate": private,
            "stargazerCount": 3,
            "pushedAt": "2024-05-01T00:00:00Z",
            "primaryLanguage": {"name": "Python"},
            "languages": {"nodes": [{"name": "Python"}, {"name": "Shell"}]},
        }
    }


def test_missing_featured_repo_skipped_with_warning(caplog):
    def gql(v):
        if v["name"] == "gone":
            return {"repository": None}
        return _repo_node(f"{v['owner']}/{v['name']}")

    client = FakeClient(graphql=gql)
    with caplog.at_level(logging.WARNING, logger="profile_gen"):
        result = fetch_featured(
            client, cfg(featured_repos=["me/ok", "me/gone", "x/also"])
        )
    assert [r.full_name for r in result] == ["me/ok", "x/also"]
    assert (
        "WARNING: featured repository me/gone not found or inaccessible"
        in caplog.text
    )


def test_featured_api_error_skipped_with_warning(caplog):
    def gql(v):
        if v["name"] == "bad":
            raise ApiError("Could not resolve to a Repository")
        return _repo_node("me/ok")

    with caplog.at_level(logging.WARNING, logger="profile_gen"):
        result = fetch_featured(
            FakeClient(graphql=gql), cfg(featured_repos=["me/bad", "me/ok"])
        )
    assert [r.full_name for r in result] == ["me/ok"]
    assert "featured repository me/bad not found or inaccessible" in caplog.text


def test_private_featured_repo_never_returned(caplog):
    client = FakeClient(graphql=lambda v: _repo_node("me/secret", private=True))
    with caplog.at_level(logging.WARNING, logger="profile_gen"):
        result = fetch_featured(client, cfg(featured_repos=["me/secret"]))
    assert result == []
    assert "featured repository me/secret not found or inaccessible" in caplog.text


def test_auto_selected_featured_excludes_private_and_forks():
    def r(name, **kw):
        d = {
            "full_name": f"me/{name}",
            "html_url": f"https://github.com/me/{name}",
            "description": None,
            "language": "Go",
            "stargazers_count": 5,
            "pushed_at": "2024-01-01T00:00:00Z",
            "fork": False,
            "private": False,
        }
        d.update(kw)
        return d

    pages = [r("pub"), r("priv", private=True), r("frk", fork=True)]
    result = fetch_featured(FakeClient(pages=pages), cfg())
    assert [x.full_name for x in result] == ["me/pub"]


# ---------- contributions ----------

def _entry(name, owner_login, typename="User", private=False, total=1):
    return {
        "repository": {
            "nameWithOwner": name,
            "url": f"https://github.com/{name}",
            "description": None,
            "isPrivate": private,
            "owner": {"__typename": typename, "login": owner_login},
        },
        "contributions": {"totalCount": total, "nodes": []},
    }


def _contrib_data(commits=(), prs=(), issues=()):
    return {
        "user": {
            "contributionsCollection": {
                "commitContributionsByRepository": list(commits),
                "pullRequestContributionsByRepository": list(prs),
                "issueContributionsByRepository": list(issues),
            }
        }
    }


def test_owner_repositories_excluded_from_contributions():
    data = _contrib_data(
        commits=[
            _entry("me/mine", "me"),
            _entry("Me/MixedCase", "Me"),
            _entry("other/theirs", "other"),
        ],
        prs=[_entry("me/mine", "me")],
        issues=[_entry("me/mine", "me")],
    )
    result = fetch_contributions(FakeClient(graphql=data), cfg(), "public", NOW)
    assert [r.full_name for r in result] == ["other/theirs"]


def test_private_repositories_never_in_contributions():
    data = _contrib_data(
        commits=[
            _entry("other/secret", "other", private=True),
            _entry("other/open", "other"),
        ],
        prs=[_entry("other/secret", "other", private=True)],
        issues=[_entry("other/secret", "other", private=True)],
    )
    for mode in ("public", "extended"):
        result = fetch_contributions(FakeClient(graphql=data), cfg(), mode, NOW)
        assert [r.full_name for r in result] == ["other/open"]
        assert "secret" not in repr(result)


def test_extended_mode_drops_non_allow_listed_orgs():
    data = _contrib_data(
        commits=[
            _entry("corp/internal", "corp", typename="Organization"),
            _entry("oss/lib", "oss", typename="Organization"),
        ]
    )
    result = fetch_contributions(
        FakeClient(graphql=data), cfg(org_allow_list=["OSS"]), "extended", NOW
    )
    assert [r.full_name for r in result] == ["oss/lib"]
    assert "corp" not in repr(result)


def test_contribution_counts_and_pr_state_aggregated():
    pr_entry = _entry("other/x", "other", total=2)
    pr_entry["contributions"]["nodes"] = [
        {"pullRequest": {"title": "a", "url": "u1", "state": "MERGED", "merged": True}},
        {"pullRequest": {"title": "b", "url": "u2", "state": "OPEN", "merged": False}},
    ]
    data = _contrib_data(
        commits=[_entry("other/x", "other", total=4)],
        prs=[pr_entry],
        issues=[_entry("other/x", "other", total=1)],
    )
    (rc,) = fetch_contributions(FakeClient(graphql=data), cfg(), "public", NOW)
    assert (rc.commits, rc.pull_requests, rc.issues) == (4, 2, 1)
    assert [p.state for p in rc.pr_items] == ["merged", "open"]


# ---------- activity ----------

def _push_event(repo, ts):
    return {
        "type": "PushEvent",
        "repo": {"name": repo},
        "created_at": ts,
        "payload": {"head": "abc123", "size": 1, "commits": [{"message": "m"}]},
    }


def test_events_from_other_owners_retained():
    pages = [
        _push_event("me/mine", "2024-05-01T00:00:00Z"),
        _push_event("other/theirs", "2024-05-03T00:00:00Z"),
        _push_event("some-org/project", "2024-05-02T00:00:00Z"),
    ]
    client = FakeClient(pages=pages)
    result = fetch_activity(client, cfg())
    assert [e.repo for e in result] == [
        "other/theirs",
        "some-org/project",
        "me/mine",
    ]
    # Only the public events endpoint is used, so private events are not requested.
    assert client.rest_paths == ["/users/me/events/public"]


def test_activity_respects_feed_length():
    pages = [_push_event(f"o/r{i}", f"2024-05-0{i + 1}T00:00:00Z") for i in range(5)]
    result = fetch_activity(FakeClient(pages=pages), cfg(feed_length=2))
    assert [e.repo for e in result] == ["o/r4", "o/r3"]
