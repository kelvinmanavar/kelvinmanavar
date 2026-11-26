"""Fetch featured repositories (Requirements 9.1, 9.3, 9.4)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from ..client import ApiError, AuthError, GitHubClient, RateLimitError, logger
from ..config import Config
from ..models import FeaturedRepo

TOP_N = 6
TOP_LANGUAGES = 4

_REPO_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    url
    description
    isPrivate
    stargazerCount
    pushedAt
    primaryLanguage { name }
    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { nodes { name } }
  }
}
"""


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def select_top_repos(repos: Iterable[dict], limit: int = TOP_N) -> list[FeaturedRepo]:
    """Pick the top `limit` non-fork public repos by stars, ties by latest push.

    `repos` are GitHub REST repository objects. Pure: no network access.
    """
    eligible = [
        r
        for r in repos
        if not r.get("fork") and not r.get("private") and r.get("pushed_at")
    ]
    eligible.sort(key=lambda r: _parse_time(r["pushed_at"]), reverse=True)
    eligible.sort(key=lambda r: r.get("stargazers_count") or 0, reverse=True)
    return [
        FeaturedRepo(
            full_name=r["full_name"],
            url=r["html_url"],
            description=r.get("description"),
            language=r.get("language"),
            stars=r.get("stargazers_count") or 0,
            pushed_at=_parse_time(r["pushed_at"]),
        )
        for r in eligible[:limit]
    ]


def _warn_missing(name: str) -> None:
    logger.log(
        logging.WARNING,
        f"WARNING: featured repository {name} not found or inaccessible",
    )


def _fetch_configured(client: GitHubClient, name: str) -> FeaturedRepo | None:
    owner, _, repo = name.partition("/")
    try:
        data = client.graphql(_REPO_QUERY, {"owner": owner, "name": repo})
    except (RateLimitError, AuthError):
        raise
    except ApiError:
        _warn_missing(name)
        return None
    node = data.get("repository") if isinstance(data, dict) else None
    if not node or node.get("isPrivate") or not node.get("pushedAt"):
        _warn_missing(name)
        return None
    language = node.get("primaryLanguage") or {}
    names = tuple(
        n["name"]
        for n in ((node.get("languages") or {}).get("nodes") or [])
        if n and n.get("name")
    )[:TOP_LANGUAGES]
    return FeaturedRepo(
        full_name=node["nameWithOwner"],
        url=node["url"],
        description=node.get("description"),
        language=language.get("name"),
        stars=node.get("stargazerCount") or 0,
        pushed_at=_parse_time(node["pushedAt"]),
        languages=names,
    )


def fetch_featured(client: GitHubClient, cfg: Config) -> list[FeaturedRepo]:
    if cfg.featured_repos:
        repos = (_fetch_configured(client, name) for name in cfg.featured_repos)
        return [r for r in repos if r is not None]
    pages = client.rest_pages(f"/users/{cfg.owner}/repos?type=owner&sort=pushed")
    selected = select_top_repos(pages)
    # Re-fetch each pick through GraphQL to get its full language list.
    detailed = (_fetch_configured(client, r.full_name) for r in selected)
    return [d or r for d, r in zip(detailed, selected)]
