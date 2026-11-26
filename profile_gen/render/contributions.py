"""Render the contributions-to-other-repositories section."""
from __future__ import annotations

from collections.abc import Iterable

from ..models import Mode, PullRequestItem, RepoContribution
from ..text import escape_md, truncate

EMPTY_TEXT = "No contributions to other repositories in the last 12 months."
MAX_ROWS = 10
_PR_TITLE_LIMIT = 72


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _render_pr(pr: PullRequestItem) -> str:
    title = escape_md(truncate(pr.title, _PR_TITLE_LIMIT))
    return f"  - [{title}]({pr.url}) ({pr.state})"


def _render_repo(repo: RepoContribution) -> list[str]:
    name = escape_md(repo.full_name)
    line = f"- [{name}]({repo.url})"
    if repo.description:
        line += f" \u2014 {escape_md(repo.description)}"
    lines = [
        line,
        f"  {_plural(repo.commits, 'commit')}, "
        f"{_plural(repo.pull_requests, 'pull request')}, "
        f"{_plural(repo.issues, 'issue')}",
    ]
    lines.extend(_render_pr(pr) for pr in repo.pr_items)
    return lines


def render_contributions(
    repos: Iterable[RepoContribution], mode: Mode = "public"
) -> str:
    """Return Markdown for the contribution section.

    Rows are ordered by total descending (ties by full name) and capped at 10.
    The fetch layer folds private and non-allow-listed organization repositories
    into anonymous counts before this point, so every record received here is
    listable; the renderer adds no row for anything else. ``mode`` is accepted
    for interface symmetry and does not change the output.
    """
    ordered = sorted(repos, key=lambda r: (-r.total, r.full_name))[:MAX_ROWS]
    if not ordered:
        return EMPTY_TEXT
    lines: list[str] = []
    for repo in ordered:
        lines.extend(_render_repo(repo))
    return "\n".join(lines)
