"""Property test for REST pagination."""

import json
import re

from hypothesis import given, settings, strategies as st

from profile_gen.client import GitHubClient


class _FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = {}

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@st.composite
def _paged(draw):
    per_page = draw(st.integers(min_value=1, max_value=5))
    max_pages = draw(st.integers(min_value=1, max_value=5))
    full = draw(st.integers(min_value=0, max_value=max_pages))
    counter = iter(range(10_000))
    pages = [[{"id": next(counter)} for _ in range(per_page)] for _ in range(full)]
    if full < max_pages:
        short = draw(st.integers(min_value=0, max_value=per_page - 1))
        pages.append([{"id": next(counter)} for _ in range(short)])
    return per_page, max_pages, pages


# Feature: professional-profile-readme, Property 15: Pagination yields all items exactly once
@settings(max_examples=100)
@given(_paged())
def test_pagination_yields_all_items_exactly_once(case):
    """**Validates: Requirements 13.4**"""
    per_page, max_pages, pages = case
    requested = []

    def opener(req):
        page = int(re.search(r"[?&]page=(\d+)", req.full_url).group(1))
        requested.append(page)
        return _FakeResponse(pages[page - 1])

    client = GitHubClient(opener=opener, sleep=lambda _s: None)
    got = list(client.rest_pages("/x", per_page=per_page, max_pages=max_pages))

    assert got == [item for page in pages for item in page]
    assert requested == list(range(1, len(pages) + 1))
