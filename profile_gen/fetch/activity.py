"""Fetch recent public events of the profile owner as ActivityEvent models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from profile_gen.client import GitHubClient
from profile_gen.config import Config
from profile_gen.models import ActivityEvent

_WEB_ROOT = "https://github.com"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _push(repo: str, created_at: datetime, payload: dict) -> ActivityEvent:
    commits = payload.get("commits")
    commits = commits if isinstance(commits, list) else []
    size = payload.get("size")
    count = size if isinstance(size, int) and not isinstance(size, bool) else len(commits)
    sha = _str_or_none(payload.get("head"))
    last = commits[-1] if commits and isinstance(commits[-1], dict) else {}
    message = _str_or_none(last.get("message"))
    title = message.splitlines()[0] if message else None
    url = f"{_WEB_ROOT}/{repo}/commit/{sha}" if sha else None
    return ActivityEvent("push", repo, created_at, title, url, count)


def _convert(event: Any) -> ActivityEvent | None:
    """Map one raw API event to an ActivityEvent, or None if not shown."""
    if not isinstance(event, dict):
        return None
    repo = _str_or_none((event.get("repo") or {}).get("name"))
    created_at = _parse_time(event.get("created_at"))
    payload = event.get("payload")
    if repo is None or created_at is None or not isinstance(payload, dict):
        return None

    kind = event.get("type")
    action = payload.get("action")
    if kind == "PushEvent":
        return _push(repo, created_at, payload)
    if kind == "PullRequestEvent":
        pr = payload.get("pull_request") or {}
        if action == "opened":
            etype = "pr_opened"
        elif action == "closed":
            etype = "pr_merged" if pr.get("merged") else "pr_closed"
        else:
            return None
        return ActivityEvent(
            etype, repo, created_at,
            _str_or_none(pr.get("title")), _str_or_none(pr.get("html_url")), None,
        )
    if kind == "IssuesEvent":
        if action != "opened":
            return None
        issue = payload.get("issue") or {}
        return ActivityEvent(
            "issue_opened", repo, created_at,
            _str_or_none(issue.get("title")), _str_or_none(issue.get("html_url")), None,
        )
    if kind == "PullRequestReviewEvent":
        if action not in (None, "created"):
            return None
        pr = payload.get("pull_request") or {}
        review = payload.get("review") or {}
        return ActivityEvent(
            "review", repo, created_at,
            _str_or_none(pr.get("title")),
            _str_or_none(review.get("html_url")) or _str_or_none(pr.get("html_url")),
            None,
        )
    return None


def fetch_activity(client: GitHubClient, cfg: Config) -> list[ActivityEvent]:
    """Return the newest supported public events, newest first.

    Events in repositories owned by other users and organizations are kept.
    Results are paginated so the feed is not limited to the first page.
    """
    path = f"/users/{cfg.owner}/events/public"
    events = [
        e for e in map(_convert, client.rest_pages(path)) if e is not None
    ]
    events.sort(key=lambda e: e.created_at, reverse=True)
    return events[: cfg.feed_length]
