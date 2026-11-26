"""Property test for the contribution section renderer."""
from __future__ import annotations

import string

from hypothesis import given, settings, strategies as st

from profile_gen.models import PullRequestItem, RepoContribution
from profile_gen.render.contributions import MAX_ROWS, render_contributions

_ALNUM = string.ascii_letters + string.digits
_word = st.text(alphabet=_ALNUM, min_size=1, max_size=8)

_pr = st.builds(
    PullRequestItem,
    title=st.text(alphabet=_ALNUM + " ", min_size=1, max_size=30).filter(str.strip),
    url=_word.map(lambda s: f"https://github.com/pr/{s}"),
    state=st.sampled_from(["open", "merged", "closed"]),
)


@st.composite
def _repos(draw):
    names = draw(st.lists(st.tuples(_word, _word), min_size=0, max_size=20, unique=True))
    repos = []
    for owner, name in names:
        repos.append(
            RepoContribution(
                full_name=f"{owner}/{name}",
                url=f"https://github.com/{owner}/{name}",
                description=draw(
                    st.one_of(st.none(), _word.map(lambda s: f"desc{s}"))
                ),
                commits=draw(st.integers(0, 500)),
                pull_requests=draw(st.integers(0, 50)),
                issues=draw(st.integers(0, 50)),
                pr_items=tuple(draw(st.lists(_pr, max_size=3))),
            )
        )
    return repos


# Feature: professional-profile-readme, Property 11: Contribution section content, ordering, and privacy
# **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 12.5, 12.6**
@settings(max_examples=200)
@given(repos=_repos(), mode=st.sampled_from(["public", "extended"]))
def test_contribution_content_ordering_and_privacy(repos, mode):
    out = render_contributions(repos, mode)
    expected = sorted(repos, key=lambda r: (-r.total, r.full_name))[:MAX_ROWS]

    rows = [ln for ln in out.splitlines() if ln.startswith("- [")]
    assert len(rows) == len(expected) <= MAX_ROWS

    # Ordering and per-row content.
    for line, repo in zip(rows, expected):
        assert line.startswith(f"- [{repo.full_name}]({repo.url})")
        if repo.description:
            assert repo.description in line
    positions = [out.index(f"[{r.full_name}]({r.url})") for r in expected]
    assert positions == sorted(positions)

    # Counts and PR states appear for every included repo.
    for repo in expected:
        assert f"{repo.commits} commit" in out
        assert f"{repo.pull_requests} pull request" in out
        assert f"{repo.issues} issue" in out
        for pr in repo.pr_items:
            assert f"]({pr.url}) ({pr.state})" in out

    # Privacy: only supplied (and not capped-out) repositories are referenced.
    for repo in repos:
        if repo not in expected:
            assert repo.url not in out
    assert "private-secret/hidden" not in out
