"""Render the Featured Projects section as a Markdown table."""

from __future__ import annotations

from collections.abc import Sequence

from ..models import FeaturedRepo
from ..text import escape_md

_HEADER = "| Project | Description | Languages |"
_SEPARATOR = "| --- | --- | --- |"


def _link_url(url: str) -> str:
    """Make a URL safe inside a Markdown link destination."""
    return (
        url.replace(" ", "%20")
        .replace("(", "%28")
        .replace(")", "%29")
        .replace("|", "%7C")
        .replace("<", "%3C")
        .replace(">", "%3E")
    )


def render_featured(repos: Sequence[FeaturedRepo]) -> str:
    """Return a table with name link, description and languages."""
    lines = [_HEADER, _SEPARATOR]
    for repo in repos:
        name = f"[{escape_md(repo.full_name)}]({_link_url(repo.url)})"
        description = escape_md(repo.description) if repo.description else ""
        names = repo.languages or ((repo.language,) if repo.language else ())
        language = ", ".join(escape_md(n) for n in names)
        lines.append(f"| {name} | {description} | {language} |")
    return "\n".join(lines)
