"""Render the GitHub stats section as Markdown."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from ..models import CalendarDay, Mode, Stats
from ..text import escape_md

TOP_LANGUAGES = 8

PUBLIC_LABEL = "public contributions"
EXTENDED_LABEL = "includes private and organization contributions"


def language_percentages(bytes_by_lang: Mapping[str, int]) -> dict[str, float]:
    """Percent share per language, rounded to 0.1 and summing to exactly 100.0.

    Uses the largest-remainder method on tenths of a percent. Languages with
    non-positive byte counts are dropped. Returns {} when there is no data.
    """
    items = [(k, v) for k, v in bytes_by_lang.items() if v > 0]
    total = sum(v for _, v in items)
    if total == 0:
        return {}
    total_tenths = 1000
    exact = [(k, v * total_tenths / total) for k, v in items]
    floors = [int(x) for _, x in exact]
    remaining = total_tenths - sum(floors)
    order = sorted(
        range(len(exact)), key=lambda i: (-(exact[i][1] - floors[i]), i)
    )
    for i in order[:remaining]:
        floors[i] += 1
    return {k: floors[i] / 10 for i, (k, _) in enumerate(exact)}


def streaks(days: Sequence[CalendarDay], today: date) -> tuple[int, int]:
    """Return (current, longest) streaks in days.

    A day counts when its contribution count is above zero. Days after
    ``today`` are ignored. The current streak is the run of consecutive days
    ending on ``today`` (0 if today has no contributions).
    """
    active = {d.date for d in days if d.count > 0 and d.date <= today}
    longest = 0
    for d in active:
        if d - timedelta(days=1) in active:
            continue  # not the start of a run
        length = 1
        while d + timedelta(days=length) in active:
            length += 1
        longest = max(longest, length)
    current = 0
    d = today
    while d in active:
        current += 1
        d -= timedelta(days=1)
    return current, longest


def render_stats(stats: Stats, mode: Mode) -> str:
    """Render the stats body: totals table, language table, streak line."""
    label = PUBLIC_LABEL if mode == "public" else EXTENDED_LABEL
    lines = [
        f"_All figures are {label}._",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Total commits | {stats.total_commits} |",
        f"| Pull requests opened | {stats.prs_opened} |",
        f"| Pull requests merged | {stats.prs_merged} |",
        f"| Issues opened | {stats.issues_opened} |",
        f"| Code reviews | {stats.reviews} |",
        f"| Repositories contributed to | {stats.repos_contributed_to} |",
        "",
    ]
    pct = language_percentages(stats.languages)
    if pct:
        top = sorted(pct.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_LANGUAGES]
        lines += ["| Language | Share |", "|---|---:|"]
        lines += [f"| {escape_md(name)} | {p:.1f}% |" for name, p in top]
    else:
        lines.append("No language data available.")
    lines += [
        "",
        f"**Current streak:** {stats.current_streak} days"
        f" · **Longest streak:** {stats.longest_streak} days",
    ]
    return "\n".join(lines)
