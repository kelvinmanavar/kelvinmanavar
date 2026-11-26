"""Property test for the featured projects renderer."""
from __future__ import annotations

import string
from datetime import datetime, timezone

from hypothesis import given, settings, strategies as st

from profile_gen.models import FeaturedRepo
from profile_gen.render.featured import render_featured

_ALNUM = string.ascii_letters + string.digits
_word = st.text(alphabet=_ALNUM, min_size=1, max_size=8)


@st.composite
def _repos(draw):
    names = draw(st.lists(st.tuples(_word, _word), min_size=0, max_size=10, unique=True))
    repos = []
    for owner, name in names:
        repos.append(
            FeaturedRepo(
                full_name=f"{owner}/{name}",
                url=f"https://github.com/{owner}/{name}",
                description=draw(st.one_of(st.none(), _word.map(lambda s: f"desc{s}"))),
                language=draw(st.one_of(st.none(), _word.map(lambda s: f"Lang{s}"))),
                stars=draw(st.integers(0, 1_000_000)),
                languages=tuple(draw(st.lists(_word.map(lambda s: f"L{s}"), max_size=4, unique=True))),
                pushed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        )
    return repos


# Feature: professional-profile-readme, Property 12: Featured project rendering completeness
# **Validates: Requirements 9.2**
@settings(max_examples=100)
@given(_repos())
def test_featured_rendering_completeness(repos):
    out = render_featured(repos)
    rows = [ln for ln in out.splitlines() if ln.startswith("|")][2:]
    assert len(rows) == len(repos)
    for repo, row in zip(repos, rows):
        assert f"[{repo.full_name}]({repo.url})" in row
        if repo.description:
            assert repo.description in row
        if repo.languages:
            assert ", ".join(repo.languages) in row
        elif repo.language:
            assert repo.language in row
        assert row.count("|") == 4  # three columns, no stars column
