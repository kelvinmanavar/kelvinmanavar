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

_CREATED_QUERY = """
query($login: String!) { user(login: $login) { createdAt } }
"""

# GraphQL rejects contributionsCollection ranges longer than one year.
_WINDOW_DAYS = 365

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


_REPO_FIELD_NAMES = (
    "commitContributionsByRepository",
    "pullRequestContributionsByRepository",
    "issueContributionsByRepository",
    "pullRequestReviewContributionsByRepository",
)


def _repo_keys(collection: dict) -> set[object]:
    """Identity keys of every repository in a contribution collection.

    Private and non-allow-listed organization repositories are counted
    anonymously: only their identity is used for de-duplication.
    """
    keys: set[object] = set()
    for field in _REPO_FIELD_NAMES:
        for item in collection.get(field) or []:
            repo = item.get("repository") or {}
            keys.add(repo.get("databaseId") or repo.get("nameWithOwner"))
    keys.discard(None)
    return keys


def _distinct_repo_count(collection: dict) -> int:
    return len(_repo_keys(collection))


def _windows(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Consecutive windows of at most one year covering [start, end]."""
    out: list[tuple[datetime, datetime]] = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=_WINDOW_DAYS), end)
        out.append((cur, nxt))
        cur = nxt
    return out


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


def _account_created(client: GitHubClient, cfg: Config) -> datetime:
    data = client.graphql(_CREATED_QUERY, {"login": cfg.owner})
    created = _user(data)["createdAt"]
    return datetime.fromisoformat(created.replace("Z", "+00:00"))


def fetch_stats(
    client: GitHubClient, cfg: Config, mode: Mode, now: datetime
) -> Stats:
    """Collect lifetime counts, languages, and streaks for the owner.

    Totals cover the whole life of the account, fetched in one-year windows
    because the API limits each query to a year.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    created = _account_created(client, cfg)

    commits = prs = issues = reviews = 0
    repo_keys: set[object] = set()
    per_day: dict[date, int] = {}
    for start, end in _windows(created, now):
        data = client.graphql(
            _CONTRIBUTIONS_QUERY,
            {"login": cfg.owner, "from": _iso(start), "to": _iso(end)},
        )
        collection = _user(data)["contributionsCollection"]
        commits += int(collection["totalCommitContributions"])
        prs += int(collection["totalPullRequestContributions"])
        issues += int(collection["totalIssueContributions"])
        reviews += int(collection["totalPullRequestReviewContributions"])
        repo_keys |= _repo_keys(collection)
        for day in _parse_calendar(collection).days:
            per_day[day.date] = per_day.get(day.date, 0) + day.count

    days = [CalendarDay(date=d, count=c) for d, c in sorted(per_day.items())]
    current, longest = streaks(days, now.astimezone(timezone.utc).date())

    merged = _count_merged_prs(client, cfg, mode, created)
    languages = _fetch_languages(client, cfg)

    return Stats(
        total_commits=commits,
        prs_opened=prs,
        prs_merged=merged,
        issues_opened=issues,
        reviews=reviews,
        repos_contributed_to=len(repo_keys),
        languages=languages,
        current_streak=current,
        longest_streak=longest,
    )
