"""Generator entry point: fetch, render, and rewrite marker-delimited sections."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import markers
from .client import (
    ApiError,
    AuthError,
    GitHubClient,
    RateLimitError,
    logger,
    redact,
)
from .config import ConfigError, load_config
from .fetch.activity import fetch_activity
from .fetch.contributions import fetch_contributions
from .fetch.featured import fetch_featured
from .fetch.stats import fetch_calendar, fetch_stats
from .markers import MarkerError
from .models import Mode
from .render.activity import render_activity
from .render.contributions import render_contributions
from .render.featured import render_featured
from .render.graph import render_graph_picture, render_graph_svg
from .render.stats import render_stats

SECTIONS = ("FEATURED", "STATS", "GRAPH", "ACTIVITY", "CONTRIBUTIONS")
TOKEN_ENV = "PROFILE_STATS_TOKEN"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent
THEMES = ("dark", "light")

ClientFactory = Callable[[str], Any]


def _default_factory(token: str) -> GitHubClient:
    return GitHubClient(token)


def _select_client(
    token: str, client_factory: ClientFactory
) -> tuple[Any, Mode]:
    """Return (client, mode). Falls back to Public when the token is rejected."""
    if not token:
        return client_factory(""), "public"
    client = client_factory(token)
    try:
        client.graphql("query { viewer { login } }", {})
    except AuthError as exc:
        logger.warning(
            redact(
                f"WARNING: {TOKEN_ENV} was rejected ({exc}); falling back to Public mode",
                token,
            )
        )
        return client_factory(""), "public"
    return client, "extended"


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    client_factory: ClientFactory | None = None,
    now: datetime | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="profile_gen")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    root: Path = args.root
    env = os.environ if env is None else env
    client_factory = client_factory or _default_factory
    now = now or datetime.now(tz=timezone.utc)
    token = (env.get(TOKEN_ENV) or "").strip()

    def log_error(msg: str) -> None:
        logger.error(redact(msg, token))

    try:
        cfg = load_config(root / "profile.config.json")
    except ConfigError as exc:
        log_error(f"ERROR config: {exc}")
        return 1

    readme_path = root / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        log_error(f"ERROR cannot read README.md: {exc}")
        return 1
    try:
        markers.validate(readme, SECTIONS)
    except MarkerError as exc:
        log_error(f"ERROR section={exc.section}: {exc}")
        return 1

    try:
        client, mode = _select_client(token, client_factory)

        fetchers: dict[str, Callable[[], str]] = {
            "FEATURED": lambda: render_featured(fetch_featured(client, cfg)),
            "STATS": lambda: render_stats(fetch_stats(client, cfg, mode, now), mode),
            "GRAPH": render_graph_picture,
            "ACTIVITY": lambda: render_activity(
                fetch_activity(client, cfg), cfg.feed_length
            ),
            "CONTRIBUTIONS": lambda: render_contributions(
                fetch_contributions(client, cfg, mode, now), mode
            ),
        }

        bodies: dict[str, str] = {}
        for name in SECTIONS:
            try:
                bodies[name] = fetchers[name]()
            except RateLimitError:
                raise
            except ApiError as exc:
                log_error(f"ERROR section={name} {exc}")
                bodies[name] = markers.extract(readme, name)

        svgs: dict[str, str] = {}
        try:
            calendar = fetch_calendar(client, cfg, now)
            svgs = {t: render_graph_svg(calendar, t) for t in THEMES}  # type: ignore[arg-type]
        except RateLimitError:
            raise
        except ApiError as exc:
            log_error(f"ERROR section=GRAPH calendar fetch failed: {exc}")

        new_readme = markers.replace_all(readme, bodies)
    except RateLimitError as exc:
        log_error(f"ERROR rate limit exhausted; resets at {exc.reset_at.isoformat()}")
        return 1
    except MarkerError as exc:
        log_error(f"ERROR section={exc.section}: {exc}")
        return 1

    # All sections processed: write outputs.
    if svgs:
        assets = root / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        for theme, svg in svgs.items():
            (assets / f"contribution-graph-{theme}.svg").write_text(
                svg, encoding="utf-8"
            )
    if new_readme != readme:
        readme_path.write_text(new_readme, encoding="utf-8")
    logger.log(logging.INFO, f"profile_gen: done (mode={mode})")
    return 0
