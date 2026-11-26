"""Static document tests for README.md."""

from __future__ import annotations

import re
from pathlib import Path

from profile_gen.markers import validate

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
LINES = README.splitlines()

SECTIONS = [
    "About",
    "Tech Stack",
    "Featured Projects",
    "GitHub Stats",
    "Contribution Graph",
    "Recent Activity",
    "Open Source Contributions",
    "Connect",
]
MARKERS = ["FEATURED", "STATS", "GRAPH", "ACTIVITY", "CONTRIBUTIONS"]


def _headings(level: int) -> list[str]:
    pat = re.compile(r"^" + "#" * level + r"\s+(.*?)\s*#*\s*$")
    return [m.group(1) for line in LINES if (m := pat.match(line))]


def test_exactly_one_atx_h1_with_required_text():
    h1 = _headings(1)
    assert len(h1) == 1
    assert "Kelvin Manavar" in h1[0]
    assert "<img" not in h1[0] and "![" not in h1[0]


def test_no_setext_headings():
    for i, line in enumerate(LINES[1:], start=1):
        if re.fullmatch(r"(=+|-{2,})\s*", line):
            assert not LINES[i - 1].strip() or LINES[i - 1].lstrip().startswith(("-", "|")), (
                f"setext heading at line {i}"
            )


def test_h2_section_order():
    assert _headings(2) == SECTIONS


def test_no_banned_hosts_or_gprm_comment():
    assert "demolab" not in README
    assert "shion" not in README
    assert "GPRM" not in README


def test_every_image_has_alt_text():
    md_images = re.findall(r"!\[([^\]]*)\]\(", README)
    assert md_images
    assert all(alt.strip() for alt in md_images)
    for tag in re.findall(r"<img\b[^>]*>", README):
        m = re.search(r'\balt="([^"]*)"', tag)
        assert m and m.group(1).strip(), tag


def test_badge_lines_under_300_characters():
    for line in LINES:
        if line.startswith("<a ") and "<picture>" in line:
            continue  # Connect lines are exempt
        assert len(line) < 300, line[:80]


def test_all_marker_pairs_valid():
    validate(README, MARKERS)
