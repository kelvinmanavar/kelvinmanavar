"""Marker-delimited section handling for the profile README.

All operations use plain string search and slicing, so text outside a marker
pair is preserved byte for byte.
"""

from __future__ import annotations

from typing import Mapping, Sequence


class MarkerError(Exception):
    """A section's markers are missing, duplicated, out of order, or misused."""

    def __init__(self, section: str, message: str = "invalid markers") -> None:
        self.section = section
        super().__init__(f"section={section}: {message}")


def start_marker(name: str) -> str:
    return f"<!-- {name}:START -->"


def end_marker(name: str) -> str:
    return f"<!-- {name}:END -->"


def _locate(readme: str, name: str) -> tuple[int, int, int, int]:
    """Return (start_begin, body_begin, body_end, end_finish) for a section."""
    start, end = start_marker(name), end_marker(name)
    n_start, n_end = readme.count(start), readme.count(end)
    if n_start == 0:
        raise MarkerError(name, f"missing {start}")
    if n_end == 0:
        raise MarkerError(name, f"missing {end}")
    if n_start > 1 or n_end > 1:
        raise MarkerError(name, "duplicated markers")
    s = readme.find(start)
    e = readme.find(end)
    if s > e:
        raise MarkerError(name, "START marker appears after END marker")
    if s + len(start) > e:
        raise MarkerError(name, "markers overlap")
    return s, s + len(start), e, e + len(end)


def validate(readme: str, names: Sequence[str]) -> None:
    """Raise MarkerError naming the first section whose markers are malformed."""
    for name in names:
        _locate(readme, name)


def extract(readme: str, name: str) -> str:
    """Return the body between a section's markers.

    Exactly one leading and one trailing newline (added by replace) are removed.
    """
    _, body_begin, body_end, _ = _locate(readme, name)
    body = readme[body_begin:body_end]
    if body.startswith("\n"):
        body = body[1:]
    if body.endswith("\n"):
        body = body[:-1]
    return body


def replace(readme: str, name: str, body: str) -> str:
    """Replace only the body of the named section."""
    for marker in (start_marker(name), end_marker(name)):
        if marker in body:
            raise MarkerError(name, f"body contains marker {marker}")
    _, body_begin, body_end, _ = _locate(readme, name)
    return readme[:body_begin] + "\n" + body + "\n" + readme[body_end:]


def replace_all(readme: str, bodies: Mapping[str, str]) -> str:
    """Validate every section first, then replace each body in turn."""
    validate(readme, list(bodies))
    for name, body in bodies.items():
        readme = replace(readme, name, body)
    return readme
