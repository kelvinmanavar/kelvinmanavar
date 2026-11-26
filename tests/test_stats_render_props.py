"""Property tests for render_stats in profile_gen.render.stats."""
from hypothesis import given, settings, strategies as st

from profile_gen.models import Stats
from profile_gen.render.stats import render_stats

# Feature: professional-profile-readme, Property 9: Stats rendering shows all required figures and mode label
# **Validates: Requirements 5.3, 5.7, 5.8**

_count = st.integers(min_value=0, max_value=10**7)

_stats = st.builds(
    Stats,
    total_commits=_count,
    prs_opened=_count,
    prs_merged=_count,
    issues_opened=_count,
    reviews=_count,
    repos_contributed_to=_count,
    languages=st.dictionaries(
        st.text(min_size=1, max_size=12), st.integers(1, 10**9), max_size=10
    ),
    current_streak=_count,
    longest_streak=_count,
)


@settings(max_examples=200)
@given(_stats, st.sampled_from(["public", "extended"]))
def test_stats_rendering_shows_figures_and_mode_label(stats, mode):
    out = render_stats(stats, mode)
    rows = {
        line.split("|")[1].strip(): line.split("|")[2].strip()
        for line in out.splitlines()
        if line.startswith("| ") and line.count("|") == 3
    }
    assert rows["Total commits"] == str(stats.total_commits)
    assert rows["Pull requests opened"] == str(stats.prs_opened)
    assert rows["Pull requests merged"] == str(stats.prs_merged)
    assert rows["Issues opened"] == str(stats.issues_opened)
    assert rows["Code reviews"] == str(stats.reviews)
    assert rows["Repositories contributed to"] == str(stats.repos_contributed_to)

    lowered = out.lower()
    if mode == "public":
        assert "public contributions" in lowered
    else:
        assert "private" in lowered and "organization" in lowered
