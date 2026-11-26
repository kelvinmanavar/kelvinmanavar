"""Property tests for profile_gen.markers."""

from hypothesis import given, settings, strategies as st

from profile_gen import markers

SETTINGS = settings(max_examples=100, deadline=None)

names = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ_", min_size=1, max_size=12)
text = st.text(max_size=80)


@st.composite
def readme_and_body(draw):
    name = draw(names)
    start, end = markers.start_marker(name), markers.end_marker(name)
    # Surrounding text must not contain this section's markers.
    free = text.filter(lambda t: start not in t and end not in t)
    prefix, old, suffix = draw(free), draw(free), draw(free)
    # Prevent markers formed across the joins.
    readme = prefix + start + old + end + suffix
    if readme.count(start) != 1 or readme.count(end) != 1:
        from hypothesis import assume
        assume(False)
    body = draw(text.filter(lambda t: start not in t and end not in t))
    return readme, name, prefix, suffix, body


@SETTINGS
@given(readme_and_body())
def test_replacement_is_localized(data):
    # Feature: professional-profile-readme, Property 1: Marker replacement is localized
    # Validates: Requirements 11.1, 11.2
    readme, name, prefix, suffix, body = data
    out = markers.replace(readme, name, body)
    start, end = markers.start_marker(name), markers.end_marker(name)
    assert out.startswith(prefix + start)
    assert out.endswith(end + suffix)


@SETTINGS
@given(readme_and_body())
def test_replace_then_extract_round_trip(data):
    # Feature: professional-profile-readme, Property 2: Replace-then-extract round trip
    # Validates: Requirements 14.4
    readme, name, _, _, body = data
    assert markers.extract(markers.replace(readme, name, body), name) == body


@SETTINGS
@given(readme_and_body())
def test_replacement_is_idempotent(data):
    # Feature: professional-profile-readme, Property 3: Replacement is idempotent
    # Validates: Requirements 14.5
    readme, name, _, _, body = data
    once = markers.replace(readme, name, body)
    assert markers.replace(once, name, body) == once
