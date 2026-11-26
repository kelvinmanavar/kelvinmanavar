"""Text helpers: Markdown/HTML escaping and truncation."""

from __future__ import annotations

ELLIPSIS = "\u2026"

# Characters that carry Markdown or HTML meaning. Each is prefixed with a backslash.
_CONTROL_CHARS = frozenset("\\`*_{}[]()#+-.!|<>&~")


def escape_md(s: str) -> str:
    """Escape Markdown and HTML control characters and flatten newlines.

    Every character in the control set is prefixed with a backslash (the backslash
    itself is escaped too). Line breaks of any kind become a single space so the
    result stays on one line.
    """
    # str.split() with no argument splits on any Unicode line break or whitespace.
    # Only line breaks need flattening here, so splitlines() keeps other spacing.
    flat = " ".join(s.splitlines()) if s else ""
    return "".join("\\" + c if c in _CONTROL_CHARS else c for c in flat)


def truncate(s: str, limit: int = 72) -> str:
    """Collapse whitespace, then cut to at most ``limit`` characters.

    When the collapsed text is longer than ``limit``, it is cut at ``limit - 1``
    characters and ``…`` is appended. Otherwise it is returned unchanged.
    """
    if limit <= 0:
        return ""
    collapsed = " ".join(s.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + ELLIPSIS
