"""Property test for featured repository auto-selection."""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from profile_gen.fetch.featured import select_top_repos

_BASE = datetime(2020, 1, 1, tzinfo=timezone.utc)


@st.composite
def repo_lists(draw):
    n = draw(st.integers(min_value=0, max_value=20))
    # Unique push times make the tie-break order fully determined.
    offsets = draw(
        st.lists(
            st.integers(min_value=0, max_value=100000),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    repos = []
    for i, off in enumerate(offsets):
        pushed = _BASE + timedelta(minutes=off)
        repos.append(
            {
                "full_name": f"owner/repo{i}",
                "html_url": f"https://github.com/owner/repo{i}",
                "description": None,
                "language": None,
                "stargazers_count": draw(st.integers(min_value=0, max_value=5)),
                "pushed_at": pushed.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fork": draw(st.booleans()),
                "private": draw(st.booleans()),
            }
        )
    return repos


# Feature: professional-profile-readme, Property 13: Auto-selected featured repositories are the top 6 by stars
# **Validates: Requirements 9.3**
@settings(max_examples=200)
@given(repo_lists())
def test_auto_selected_repos_are_top_six_by_stars(repos):
    result = select_top_repos(repos)

    eligible = [r for r in repos if not r["fork"] and not r["private"]]
    expected = sorted(
        eligible,
        key=lambda r: (r["stargazers_count"], r["pushed_at"]),
        reverse=True,
    )[:6]

    assert len(result) <= 6
    assert [r.full_name for r in result] == [r["full_name"] for r in expected]
    assert [r.stars for r in result] == sorted(
        (r.stars for r in result), reverse=True
    )
