"""Property test for text.truncate."""

from hypothesis import given, settings, strategies as st

from profile_gen.text import ELLIPSIS, truncate

LIMIT = 72

# Arbitrary text, plus strings built around the 71/72/73 boundary with whitespace.
_arbitrary = st.text(max_size=300)
_boundary = st.integers(min_value=70, max_value=74).flatmap(
    lambda n: st.text(alphabet=st.characters(blacklist_categories=("Z", "C")), min_size=n, max_size=n)
)
_spaced = st.lists(
    st.text(alphabet="ab \t\n\r", max_size=20), max_size=20
).map("".join)


# Feature: professional-profile-readme, Property 6: Truncation bounds length and marks truncation
# **Validates: Requirements 7.5, 14.7**
@settings(max_examples=200)
@given(st.one_of(_arbitrary, _boundary, _spaced))
def test_truncation_bounds_length_and_marks_truncation(s):
    normalized = " ".join(s.split())
    out = truncate(s, LIMIT)

    assert len(out) <= LIMIT
    if len(normalized) > LIMIT:
        assert out.endswith(ELLIPSIS)
        assert out == normalized[: LIMIT - 1] + ELLIPSIS
    else:
        assert out == normalized
