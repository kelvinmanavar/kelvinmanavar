"""Property test for marker validation."""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from profile_gen.markers import MarkerError, end_marker, start_marker, validate

NAMES = st.lists(
    st.from_regex(r"[A-Z][A-Z0-9_]{0,10}", fullmatch=True),
    min_size=1,
    max_size=6,
    unique=True,
)
FILLER = st.text(alphabet="abc \n#-*", max_size=20)


@st.composite
def malformed_readme(draw):
    names = draw(NAMES)
    bad = draw(st.sampled_from(names))
    kind = draw(st.sampled_from(["missing_start", "missing_end", "swapped"]))
    parts = []
    for name in names:
        body = draw(FILLER)
        s, e = start_marker(name), end_marker(name)
        if name == bad:
            if kind == "missing_start":
                s = ""
            elif kind == "missing_end":
                e = ""
            else:
                s, e = e, s
        parts.append(f"{draw(FILLER)}{s}\n{body}\n{e}")
    return "\n".join(parts), names, bad


# Feature: professional-profile-readme, Property 4: Malformed markers are rejected by name
@settings(max_examples=200)
@given(malformed_readme())
def test_malformed_markers_rejected_by_name(case):
    """**Validates: Requirements 11.3**"""
    readme, names, bad = case
    with pytest.raises(MarkerError) as info:
        validate(readme, names)
    assert info.value.section == bad
    for other in names:
        if other != bad:
            assert f"section={other}:" not in str(info.value)
            validate(readme, [other])
