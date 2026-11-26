"""Fetch statistics and the contribution calendar via the GraphQL API.

In Extended mode the token can see private and organization activity. Those
contributions are only ever reduced to counts here: repository names of
private or non-allow-listed organization repositories are used for
de-duplication in memory and never stored in the returned models.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from profile_gen.client import GitHubClient
from profile_gen.config import Config
from profile_gen.models import Calendar, CalendarDay, Mode, Stats
from profile_gen.render.stats import streaks

CALENDAR_DAYS = 365
_MAX_LANGUAGE_PAGES = 10

_REPO_FIELDS = "repository { databaseId nameWithOwner isPrivate owner { __typename login } }"

_CONTRIBUTIONS_QUERY = (
    """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      commitContributionsByRepository(maxRepositories: 100) { %(r)s }
      pullRequestContributionsByRepository(maxRepositories: 100) { %(r)s }
      issueContributionsByRepository(maxRepositories: 100) { %(r)s }
      pullRequestReviewContributionsByRepository(maxRepositories: 100) { %(r)s }
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""
    % {"r": _REPO_FIELDS}
)

_CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

_SEARCH_QUERY = """
query($q: String!) {
  search(query: $q, type: ISSUE, first: 1) { issueCount }
}
"""

_LANGUAGES_QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(
      first: 100, after: $after, isFork: false, privacy: PUBLIC,
      ownerAffiliations: OWNER
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _user(data: dict) -> dict:
    user = (data or {}).get("user")
    if not user:
        raise ValueError("user not found in GraphQL response")
    return user


def _parse_calendar(collection: dict) -> Calendar:
    weeks = collection["contributionCalendar"]["weeks"]
    days = [
        CalendarDay(
            date=date.fromisoformat(d["date"]), count=int(d["contributionCount"])
        )
        for w in weeks
        for d in w["contributionDays"]
    ]
    days.sort(key=lambda d: d.date)
    return Calendar(days=tuple(days))


def _calendar_window(now: datetime) -> tuple[str, str]:
    return _iso(now - timedelta(days=CALENDAR_DAYS)), _iso(now)


def fetch_calendar(client: GitHubClient, cfg: Config, now: datetime) -> Calendar:
    """Contribution calendar for the previous 12 months."""
    start, end = _calendar_window(now)
    data = client.graphql(
        _CALENDAR_QUERY, {"login": cfg.owner, "from": start, "to": end}
    )
    return _parse_calendar(_user(data)["contributionsCollection"])


def _distinct_repo_count(collection: dict) -> int:
    """Count distinct repositories across all contribution kinds.

    Private and non-allow-listed organization repositories are counted
    anonymously: only their identity is used for de-duplication.
    """
    keys: set[object] = set()
    for field in (
        "commitContributionsByRepository",
        "pullRequestContributionsByRepository",
        "issueContributionsByRepository",
        "pullRequestReviewContributionsByRepository",
    ):
        for item in collection.get(field) or []:
            repo = item.get("repository") or {}
            keys.add(repo.get("databaseId") or repo.get("nameWithOwner"))
    keys.discard(None)
    return len(keys)


def _fetch_languages(client: GitHubClient, cfg: Config) -> dict[str, int]:
    totals: dict[str, int] = {}
    after: str | None = None
    for _ in range(_MAX_LANGUAGE_PAGES):
        data = client.graphql(_LANGUAGES_QUERY, {"login": cfg.owner, "after": after})
        repos = _user(data)["repositories"]
        for node in repos.get("nodes") or []:
            if not node:
                continue
            for edge in (node.get("languages") or {}).get("edges") or []:
                name = edge["node"]["name"]
                totals[name] = totals.get(name, 0) + int(edge["size"])
        info = repos["pageInfo"]
        if not info["hasNextPage"]:
            break
        after = info["endCursor"]
    return {k: v for k, v in totals.items() if v > 0}


def _count_merged_prs(
    client: GitHubClient, cfg: Config, mode: Mode, start: datetime
) -> int:
    query = f"author:{cfg.owner} is:pr is:merged merged:>={start.date().isoformat()}"
    if mode == "public":
        query += " is:public"
    data = client.graphql(_SEARCH_QUERY, {"q": query})
    return int(data["search"]["issueCount"])


def fetch_stats(
    client: GitHubClient, cfg: Config, mode: Mode, now: datetime
) -> Stats:
    """Collect summary counts, languages, and streaks for the owner."""
    period_start = now - timedelta(days=cfg.contribution_period_days)
    data = client.graphql(
        _CONTRIBUTIONS_QUERY,
        {"login": cfg.owner, "from": _iso(period_start), "to": _iso(now)},
    )
    collection = _user(data)["contributionsCollection"]

    # Streaks need a full 12 months of calendar regardless of the period.
    if cfg.contribution_period_days >= CALENDAR_DAYS:
        calendar = _parse_calendar(collection)
    else:
        calendar = fetch_calendar(client, cfg, now)
    today = now.astimezone(timezone.utc).date() if now.tzinfo else now.date()
    current, longest = streaks(calendar.days, today)

    merged = _count_merged_prs(client, cfg, mode, period_start)
    languages = _fetch_languages(client, cfg)

    return Stats(
        total_commits=int(collection["totalCommitContributions"]),
        prs_opened=int(collection["totalPullRequestContributions"]),
        prs_merged=merged,
        issues_opened=int(collection["totalIssueContributions"]),
        reviews=int(collection["totalPullRequestReviewContributions"]),
        repos_contributed_to=_distinct_repo_count(collection),
        languages=languages,
        current_streak=current,
        longest_streak=longest,
    )
