"""Property tests for profile_gen.text."""

from hypothesis import given, settings, strategies as st

from profile_gen.text import _CONTROL_CHARS, escape_md

# Feature: professional-profile-readme, Property 5: Escaping removes unescaped control characters
# **Validates: Requirements 7.6, 14.6**

_control_heavy = st.text(
    alphabet=st.one_of(
        st.sampled_from(sorted(_CONTROL_CHARS) + ["\n", "\r", "\u2028", "\x0b", "\x1c", "\x85", " "]),
        st.characters(),
    ),
    max_size=80,
)


def _unescaped_controls(escaped: str) -> list[str]:
    """Walk the output, treating a backslash as escaping the next character."""
    found = []
    i = 0
    while i < len(escaped):
        c = escaped[i]
        if c == "\\":
            if i + 1 >= len(escaped) or escaped[i + 1] not in _CONTROL_CHARS:
                found.append(c)  # dangling or non-escaping backslash
            i += 2
            continue
        if c in _CONTROL_CHARS:
            found.append(c)
        i += 1
    return found


@settings(max_examples=200)
@given(_control_heavy)
def test_escape_md_leaves_no_unescaped_control_characters(s):
    out = escape_md(s)
    assert _unescaped_controls(out) == []
    assert "\n" not in out and "\r" not in out
