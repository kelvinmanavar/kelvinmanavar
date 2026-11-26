"""Fetch per-repository contributions to repositories owned by others."""
from __future__ import annotations

from datetime import datetime, timedelta

from profile_gen.client import GitHubClient
from profile_gen.config import Config
from profile_gen.models import Mode, PullRequestItem, RepoContribution

_REPO_FIELDS = """
repository {
  nameWithOwner
  url
  description
  isPrivate
  owner { __typename login }
}
"""

QUERY = (
    """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commitContributionsByRepository(maxRepositories: 100) {
        %(repo)s
        contributions { totalCount }
      }
      pullRequestContributionsByRepository(maxRepositories: 100) {
        %(repo)s
        contributions(first: 100) {
          totalCount
          nodes { pullRequest { title url state merged } }
        }
      }
      issueContributionsByRepository(maxRepositories: 100) {
        %(repo)s
        contributions { totalCount }
      }
    }
  }
}
"""
    % {"repo": _REPO_FIELDS}
)


def _pr_state(pr: dict) -> str:
    if pr.get("merged") or pr.get("state") == "MERGED":
        return "merged"
    if pr.get("state") == "CLOSED":
        return "closed"
    return "open"


def _include(repo: dict, cfg: Config, mode: Mode) -> bool:
    """Apply owner, privacy, and organization allow-list filters."""
    owner = repo.get("owner") or {}
    login = str(owner.get("login", ""))
    if login.lower() == cfg.owner.lower():
        return False  # Requirement 8.1: other owners only
    if repo.get("isPrivate"):
        return False  # Requirements 8.5, 12.5: private repos never listed
    if mode == "extended" and owner.get("__typename") == "Organization":
        allowed = {o.lower() for o in cfg.org_allow_list}
        if login.lower() not in allowed:
            return False  # Requirement 12.6
    return True


def fetch_contributions(
    client: GitHubClient, cfg: Config, mode: Mode, now: datetime
) -> list[RepoContribution]:
    """Return per-repository contribution counts for the configured period."""
    start = now - timedelta(days=cfg.contribution_period_days)
    data = client.graphql(
        QUERY,
        {
            "login": cfg.owner,
            "from": start.isoformat(),
            "to": now.isoformat(),
        },
    )
    user = data.get("user") or {}
    coll = user.get("contributionsCollection") or {}

    info: dict[str, dict] = {}
    commits: dict[str, int] = {}
    prs: dict[str, int] = {}
    issues: dict[str, int] = {}
    pr_items: dict[str, list[PullRequestItem]] = {}

    def visit(key: str, counts: dict[str, int], with_prs: bool = False) -> None:
        for entry in coll.get(key) or []:
            repo = entry.get("repository") or {}
            name = repo.get("nameWithOwner")
            if not name or not _include(repo, cfg, mode):
                continue
            info.setdefault(name, repo)
            contribs = entry.get("contributions") or {}
            counts[name] = counts.get(name, 0) + int(contribs.get("totalCount", 0))
            if with_prs:
                items = pr_items.setdefault(name, [])
                for node in contribs.get("nodes") or []:
                    pr = (node or {}).get("pullRequest")
                    if pr:
                        items.append(
                            PullRequestItem(
                                title=pr.get("title") or "",
                                url=pr.get("url") or "",
                                state=_pr_state(pr),  # type: ignore[arg-type]
                            )
                        )

    visit("commitContributionsByRepository", commits)
    visit("pullRequestContributionsByRepository", prs, with_prs=True)
    visit("issueContributionsByRepository", issues)

    result = [
        RepoContribution(
            full_name=name,
            url=repo.get("url") or f"https://github.com/{name}",
            description=repo.get("description"),
            commits=commits.get(name, 0),
            pull_requests=prs.get(name, 0),
            issues=issues.get(name, 0),
            pr_items=tuple(pr_items.get(name, ())),
        )
        for name, repo in info.items()
    ]
    result.sort(key=lambda r: (-r.total, r.full_name))
    return result
