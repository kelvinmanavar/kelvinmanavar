"""Property test for streak computation."""
from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given, settings, strategies as st

from profile_gen.models import CalendarDay
from profile_gen.render.stats import streaks

TODAY = date(2024, 6, 15)


@st.composite
def calendars(draw):
    offsets = draw(
        st.lists(st.integers(min_value=-60, max_value=5), unique=True, max_size=66)
    )
    counts = draw(
        st.lists(
            st.integers(min_value=0, max_value=3),
            min_size=len(offsets),
            max_size=len(offsets),
        )
    )
    days = [
        CalendarDay(date=TODAY + timedelta(days=o), count=c)
        for o, c in zip(offsets, counts)
    ]
    return draw(st.permutations(days))


def _reference(days, today):
    """Naive model: walk day by day over a dense array of counts."""
    counts = {d.date: d.count for d in days if d.date <= today}
    if not counts:
        return 0, 0
    longest = run = 0
    d = min(counts)
    while d <= today:
        if counts.get(d, 0) > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
        d += timedelta(days=1)
    return run, longest  # run at end of walk is the trailing run ending today


# Feature: professional-profile-readme, Property 8: Streak computation matches a reference model
@settings(max_examples=200)
@given(days=calendars())
def test_streaks_match_reference_model(days):
    """**Validates: Requirements 5.5**"""
    current, longest = streaks(days, TODAY)
    ref_current, ref_longest = _reference(days, TODAY)
    assert (current, longest) == (ref_current, ref_longest)
    assert longest >= current
