"""Property test for token redaction."""

from hypothesis import given, settings, strategies as st

from profile_gen.client import redact

# Feature: professional-profile-readme, Property 14: Token redaction in logs


@settings(max_examples=200)
@given(
    token=st.text(min_size=1, max_size=40),
    prefix=st.text(max_size=40),
    middle=st.text(max_size=40),
    suffix=st.text(max_size=40),
)
def test_redacted_output_never_contains_token(token, prefix, middle, suffix):
    """**Validates: Requirements 12.8, 13.3**"""
    text = f"{prefix}{token}{middle}{token}{suffix}"
    assert token not in redact(text, token)
