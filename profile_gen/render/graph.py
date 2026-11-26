"""Contribution graph renderer: deterministic SVG and the <picture> snippet."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

from ..models import Calendar

Theme = Literal["dark", "light"]

CELL = 11
GAP = 3
STEP = CELL + GAP
MARGIN = 10
TOP = 10

PALETTES: dict[str, dict[str, object]] = {
    "dark": {
        "background": "#0d1117",
        "levels": ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"),
    },
    "light": {
        "background": "#ffffff",
        "levels": ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"),
    },
}

ALT_TEXT = "Contribution graph for the last 12 months"
GRAPH_PATHS = {
    "dark": "assets/contribution-graph-dark.svg",
    "light": "assets/contribution-graph-light.svg",
}


def _level(count: int, max_count: int) -> int:
    if count <= 0 or max_count <= 0:
        return 0
    # Quartile buckets of the busiest day: levels 1..4.
    return min(4, 1 + (count - 1) * 4 // max_count)


def render_graph_svg(calendar: Calendar, theme: Theme) -> str:
    """Render the calendar as a themed SVG. Pure; contains no timestamps."""
    if theme not in PALETTES:
        raise ValueError(f"unknown theme: {theme!r}")
    palette = PALETTES[theme]
    levels: tuple[str, ...] = palette["levels"]  # type: ignore[assignment]
    days = sorted(calendar.days, key=lambda d: d.date)

    cells: list[str] = []
    columns = 1
    if days:
        max_count = max(d.count for d in days)
        first = days[0].date
        # Weeks start on Sunday; weekday(): Monday=0 .. Sunday=6.
        week_start = first - timedelta(days=(first.weekday() + 1) % 7)
        for d in days:
            offset = (d.date - week_start).days
            col, row = divmod(offset, 7)
            columns = max(columns, col + 1)
            x = MARGIN + col * STEP
            y = TOP + row * STEP
            fill = levels[_level(d.count, max_count)]
            cells.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{fill}"><title>{d.date.isoformat()}: {d.count}</title></rect>'
            )

    width = MARGIN * 2 + columns * STEP - GAP
    height = TOP * 2 + 7 * STEP - GAP
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{ALT_TEXT}">',
        f'<rect width="{width}" height="{height}" fill="{palette["background"]}"/>',
        *cells,
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def render_graph_picture() -> str:
    """Static <picture> snippet with dark and light sources and alt text."""
    return "\n".join(
        [
            "<picture>",
            f'  <source media="(prefers-color-scheme: dark)" srcset="{GRAPH_PATHS["dark"]}">',
            f'  <source media="(prefers-color-scheme: light)" srcset="{GRAPH_PATHS["light"]}">',
            f'  <img alt="{ALT_TEXT}" src="{GRAPH_PATHS["light"]}">',
            "</picture>",
        ]
    )
