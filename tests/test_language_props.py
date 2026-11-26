"""Property tests for language percentages in profile_gen.render.stats."""
from hypothesis import given, settings, strategies as st

from profile_gen.render.stats import language_percentages

# Feature: professional-profile-readme, Property 7: Language percentages sum to 100
# **Validates: Requirements 5.4**
_inputs = st.dictionaries(
    st.text(min_size=1, max_size=12),
    st.integers(min_value=1, max_value=10**12),
    min_size=1,
    max_size=30,
)


@settings(max_examples=200)
@given(_inputs)
def test_language_percentages_sum_to_100(bytes_by_lang):
    result = language_percentages(bytes_by_lang)
    assert set(result) == set(bytes_by_lang)
    assert all(v >= 0 for v in result.values())
    assert abs(sum(result.values()) - 100) <= 0.1
