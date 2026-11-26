"""Render the Recent Activity section."""
from __future__ import annotations

from ..models import ActivityEvent
from ..text import escape_md, truncate

EMPTY_TEXT = "No recent public activity."
TITLE_LIMIT = 72

_LABELS = {
    "pr_opened": "Opened pull request",
    "pr_merged": "Merged pull request",
    "pr_closed": "Closed pull request",
    "issue_opened": "Opened issue",
    "review": "Reviewed pull request",
}


def _label(event: ActivityEvent) -> str:
    if event.type == "push":
        n = event.commit_count or 0
        return f"Pushed {n} commit{'' if n == 1 else 's'} to"
    return _LABELS[event.type] + " in"


def _render_event(event: ActivityEvent) -> str:
    repo_link = f"[{escape_md(event.repo)}](https://github.com/{event.repo})"
    line = f"- **{_label(event)}** {repo_link}"
    if event.title:
        title = escape_md(truncate(event.title, TITLE_LIMIT))
        line += f": [{title}]({event.url})" if event.url else f": {title}"
    elif event.url:
        line += f" ([link]({event.url}))"
    return f"{line} ({event.created_at.strftime('%Y-%m-%d')})"


def render_activity(events: list[ActivityEvent], feed_length: int = 10) -> str:
    """Newest first, at most ``feed_length`` entries, or the empty fallback."""
    ordered = sorted(events, key=lambda e: e.created_at, reverse=True)[
        : max(feed_length, 0)
    ]
    if not ordered:
        return EMPTY_TEXT
    return "\n".join(_render_event(e) for e in ordered)
