"""Property test for render.activity.render_activity."""
from datetime import datetime, timedelta

from hypothesis import given, settings, strategies as st

from profile_gen.models import ActivityEvent
from profile_gen.text import escape_md
from profile_gen.render.activity import EMPTY_TEXT, render_activity

_TYPES = ["push", "pr_opened", "pr_merged", "pr_closed", "issue_opened", "review"]
_BASE = datetime(2020, 1, 1)
_name = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=8)


@st.composite
def _events(draw):
    offsets = draw(
        st.lists(st.integers(0, 3000 * 24 * 60), unique=True, max_size=30)
    )  # unique minute offsets: no timestamp ties, so order is unambiguous
    events = []
    for i, off in enumerate(offsets):
        owner, name = draw(_name), draw(_name)
        t = draw(st.sampled_from(_TYPES))
        has_url = draw(st.booleans())
        events.append(
            ActivityEvent(
                type=t,
                repo=f"{owner}/{name}",
                created_at=_BASE + timedelta(minutes=off),
                title=draw(
                    st.one_of(st.none(), st.text("abcdefghij 0123456789", min_size=1, max_size=100))
                ),
                url=f"https://github.com/{owner}/{name}/item/{i}" if has_url else None,
                commit_count=draw(st.integers(0, 50)) if t == "push" else None,
            )
        )
    return draw(st.permutations(events)) if events else events


# Feature: professional-profile-readme, Property 10: Activity feed ordering, bound, and content
# **Validates: Requirements 7.1, 7.2, 7.3**
@settings(max_examples=200)
@given(_events(), st.integers(min_value=1, max_value=15))
def test_activity_feed_ordering_bound_and_content(events, feed_length):
    out = render_activity(events, feed_length)
    if not events:
        assert out == EMPTY_TEXT
        return

    expected = sorted(events, key=lambda e: e.created_at, reverse=True)[:feed_length]
    lines = out.split("\n")
    assert len(lines) == len(expected) <= feed_length

    for line, ev in zip(lines, expected):  # newest to oldest, same selection
        assert f"[{escape_md(ev.repo)}](https://github.com/{ev.repo})" in line
        assert ev.created_at.strftime("%Y-%m-%d") in line
        if ev.url:
            assert f"({ev.url})" in line
        if ev.type == "push":
            assert "Pushed" in line
        else:
            assert {
                "pr_opened": "Opened pull request",
                "pr_merged": "Merged pull request",
                "pr_closed": "Closed pull request",
                "issue_opened": "Opened issue",
                "review": "Reviewed pull request",
            }[ev.type] in line
