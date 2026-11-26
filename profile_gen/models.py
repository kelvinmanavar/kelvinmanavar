"""Plain frozen data models shared by fetchers and renderers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

Mode = Literal["public", "extended"]


@dataclass(frozen=True)
class Stats:
    total_commits: int
    prs_opened: int
    prs_merged: int
    issues_opened: int
    reviews: int
    repos_contributed_to: int
    languages: dict[str, int]  # bytes per language, public non-fork repos
    current_streak: int
    longest_streak: int


@dataclass(frozen=True)
class CalendarDay:
    date: date
    count: int


@dataclass(frozen=True)
class Calendar:
    days: tuple[CalendarDay, ...]  # last 12 months, ascending by date


@dataclass(frozen=True)
class ActivityEvent:
    type: Literal[
        "push", "pr_opened", "pr_merged", "pr_closed", "issue_opened", "review"
    ]
    repo: str  # "owner/name"
    created_at: datetime
    title: str | None
    url: str | None
    commit_count: int | None  # push only


@dataclass(frozen=True)
class PullRequestItem:
    title: str
    url: str
    state: Literal["open", "merged", "closed"]


@dataclass(frozen=True)
class RepoContribution:
    full_name: str
    url: str
    description: str | None
    commits: int
    pull_requests: int
    issues: int
    pr_items: tuple[PullRequestItem, ...]

    @property
    def total(self) -> int:
        return self.commits + self.pull_requests + self.issues


@dataclass(frozen=True)
class FeaturedRepo:
    full_name: str
    url: str
    description: str | None
    language: str | None
    stars: int
    pushed_at: datetime
