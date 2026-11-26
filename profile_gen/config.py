"""Configuration loading and schema validation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
_MAX_PERIOD_DAYS = 365


class ConfigError(Exception):
    """Raised when the configuration file is missing or invalid."""


@dataclass(frozen=True)
class Config:
    owner: str
    profile_repo: str
    featured_repos: list[str] = field(default_factory=list)
    org_allow_list: list[str] = field(default_factory=list)
    feed_length: int = 10
    contribution_period_days: int = 365
    max_contribution_repos: int = 10
    max_title_length: int = 72


def _is_pos_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _str_list(data: dict, key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ConfigError(f"'{key}' must be a list of strings")
    return list(value)


def load_config(path: Path) -> Config:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ConfigError(f"cannot read config {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError("config must be a JSON object")

    owner = data.get("owner")
    if not isinstance(owner, str) or not re.fullmatch(r"[\w.-]+", owner):
        raise ConfigError("'owner' must be a non-empty string")

    featured = _str_list(data, "featured_repos")
    for name in featured:
        if not _REPO_RE.match(name):
            raise ConfigError(
                f"featured_repos entry {name!r} must match owner/name"
            )
    allow = _str_list(data, "org_allow_list")

    kwargs: dict[str, int] = {}
    for key in (
        "feed_length",
        "contribution_period_days",
        "max_contribution_repos",
        "max_title_length",
    ):
        if key in data:
            if not _is_pos_int(data[key]):
                raise ConfigError(f"'{key}' must be a positive integer")
            kwargs[key] = data[key]
    if kwargs.get("contribution_period_days", 365) > _MAX_PERIOD_DAYS:
        raise ConfigError(
            f"'contribution_period_days' must be at most {_MAX_PERIOD_DAYS}"
        )

    return Config(
        owner=owner,
        profile_repo=f"{owner}/{owner}",
        featured_repos=featured,
        org_allow_list=allow,
        **kwargs,
    )
