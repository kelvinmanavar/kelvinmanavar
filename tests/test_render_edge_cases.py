"""Unit tests for renderer edge cases.

Validates: Requirements 6.3, 7.7, 8.6, 14.3
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from profile_gen.models import Calendar, CalendarDay
from profile_gen.render.activity import EMPTY_TEXT as ACTIVITY_EMPTY
from profile_gen.render.activity import render_activity
from profile_gen.render.contributions import EMPTY_TEXT as CONTRIB_EMPTY
from profile_gen.render.contributions import render_contributions
from profile_gen.render.graph import render_graph_picture, render_graph_svg


def _calendar() -> Calendar:
    start = date(2024, 1, 1)
    return Calendar(
        days=tuple(CalendarDay(start + timedelta(days=i), i % 5) for i in range(60))
    )


def test_activity_empty_fallback_text():
    assert ACTIVITY_EMPTY == "No recent public activity."
    assert render_activity([]) == "No recent public activity."


@pytest.mark.parametrize("mode", ["public", "extended"])
def test_contributions_empty_fallback_text(mode):
    expected = "No contributions to other repositories in the last 12 months."
    assert CONTRIB_EMPTY == expected
    assert render_contributions([], mode) == expected


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_graph_svg_is_deterministic(theme):
    first = render_graph_svg(_calendar(), theme)
    second = render_graph_svg(_calendar(), theme)
    assert first == second
    assert first.startswith("<svg")


def test_graph_svg_themes_differ_and_empty_calendar_renders():
    cal = _calendar()
    assert render_graph_svg(cal, "dark") != render_graph_svg(cal, "light")
    assert "<svg" in render_graph_svg(Calendar(days=()), "dark")


def test_graph_picture_has_nonempty_alt_and_both_sources():
    html = render_graph_picture()
    alt = re.search(r'<img[^>]*\balt="([^"]*)"', html)
    assert alt is not None and alt.group(1).strip()
    assert "(prefers-color-scheme: dark)" in html
    assert "(prefers-color-scheme: light)" in html


def test_every_picture_has_img_with_nonempty_alt():
    html = render_graph_picture()
    pictures = re.findall(r"<picture>.*?</picture>", html, flags=re.S)
    assert pictures
    assert html.count("<picture>") == html.count("</picture>") == len(pictures)
    for pic in pictures:
        m = re.search(r'<img[^>]*\balt="([^"]+)"', pic)
        assert m and m.group(1).strip()
