"""Unit tests for GitHubClient retry, rate limit, auth, and redaction behavior."""

import io
import json
import logging
import urllib.error
from datetime import datetime, timezone

import pytest

from profile_gen.client import ApiError, AuthError, GitHubClient, RateLimitError

TOKEN = "ghp_SECRET_token_value_123"
RESET = 1893456000  # 2030-01-01T00:00:00Z


class FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = {}

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, headers=None):
    return urllib.error.HTTPError(
        "https://api.github.com/x", code, "err", headers or {}, io.BytesIO(b"")
    )


class ScriptedOpener:
    """Returns or raises each scripted item in turn."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, req):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(script, token=TOKEN):
    sleeps = []
    opener = ScriptedOpener(script)
    return GitHubClient(token, sleep=sleeps.append, opener=opener), opener, sleeps


def test_fails_twice_then_succeeds():
    ok = FakeResponse({"data": {"v": 1}})
    client, opener, sleeps = make_client([http_error(500), http_error(502), ok])
    assert client.graphql("query { v }") == {"v": 1}
    assert opener.calls == 3
    assert sleeps == [1, 2]


def test_persistent_5xx_raises_api_error_after_four_attempts():
    client, opener, sleeps = make_client([http_error(503) for _ in range(4)])
    with pytest.raises(ApiError) as info:
        client.graphql("query { v }")
    assert not isinstance(info.value, (AuthError, RateLimitError))
    assert opener.calls == 4
    assert sleeps == [1, 2, 4]


def test_network_error_is_retried():
    ok = FakeResponse({"data": {}})
    client, opener, sleeps = make_client([urllib.error.URLError("boom"), ok])
    assert client.graphql("query { v }") == {}
    assert sleeps == [1]


def test_rate_limit_raises_immediately_with_reset_time():
    err = http_error(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(RESET)})
    client, opener, sleeps = make_client([err])
    with pytest.raises(RateLimitError) as info:
        client.graphql("query { v }")
    assert opener.calls == 1
    assert sleeps == []
    reset_at = datetime.fromtimestamp(RESET, tz=timezone.utc)
    assert info.value.reset_at == reset_at
    assert reset_at.isoformat() in str(info.value)


def test_401_raises_auth_error_without_retry():
    client, opener, sleeps = make_client([http_error(401)])
    with pytest.raises(AuthError):
        client.graphql("query { v }")
    assert opener.calls == 1
    assert sleeps == []


def test_token_never_appears_in_messages(caplog):
    caplog.set_level(logging.DEBUG, logger="profile_gen")
    logger = logging.getLogger("profile_gen")
    logger.addHandler(caplog.handler)
    try:
        # Token embedded in error text paths: retries (logged) then failure.
        fail = [
            urllib.error.URLError(f"connect failed using {TOKEN}") for _ in range(4)
        ]
        client, _, _ = make_client(fail)
        with pytest.raises(ApiError) as info:
            client.graphql("query { v }")
        assert TOKEN not in str(info.value)

        # Auth failure message.
        client, _, _ = make_client([http_error(401)])
        with pytest.raises(AuthError) as info:
            client.graphql("query { v }")
        assert TOKEN not in str(info.value)

        # GraphQL error message that echoes the token.
        resp = FakeResponse({"errors": [{"message": f"bad {TOKEN}"}]})
        client, _, _ = make_client([resp])
        with pytest.raises(ApiError) as info:
            client.graphql("query { v }")
        assert TOKEN not in str(info.value)
    finally:
        logger.removeHandler(caplog.handler)

    assert caplog.records
    assert all(TOKEN not in r.getMessage() for r in caplog.records)
