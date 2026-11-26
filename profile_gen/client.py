"""GitHub API client: GraphQL and paginated REST with retry and token redaction."""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

API_ROOT = "https://api.github.com"
GRAPHQL_URL = f"{API_ROOT}/graphql"
RETRY_DELAYS = (1, 2, 4)

logger = logging.getLogger("profile_gen")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


class ApiError(Exception):
    """A request failed after retries, or the API reported an error."""


class AuthError(ApiError):
    """The token was rejected (HTTP 401)."""


class RateLimitError(ApiError):
    """The rate limit is exhausted. Carries the reset time."""

    def __init__(self, message: str, reset_at: datetime) -> None:
        super().__init__(message)
        self.reset_at = reset_at


def redact(text: str, token: str | None) -> str:
    """Remove every occurrence of the token from text."""
    if not token:
        return text
    marker = "[REDACTED]"
    if token in marker:
        marker = ""  # the marker itself must never reveal the token
    out = text.replace(token, marker)
    while token in out:  # removal can join fragments into a new occurrence
        out = out.replace(token, marker)
    return out


class GitHubClient:
    def __init__(
        self,
        token: str = "",
        sleep: Callable[[float], None] = time.sleep,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self._token = token or ""
        self._sleep = sleep
        self._opener = opener

    # -- logging -----------------------------------------------------
    def _log(self, level: int, message: str) -> None:
        logger.log(level, redact(message, self._token))

    def _fail(self, exc_type: type[ApiError], message: str, *args: Any) -> ApiError:
        return exc_type(redact(message, self._token), *args)

    # -- transport ---------------------------------------------------
    def _request(self, url: str, body: bytes | None = None) -> tuple[Any, Any]:
        """Perform a request with retries. Returns (parsed JSON, headers)."""
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-gen",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if body is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            req = urllib.request.Request(url, data=body, headers=headers)
            try:
                with self._opener(req) as resp:
                    raw = resp.read()
                    resp_headers = resp.headers
                try:
                    return json.loads(raw.decode("utf-8")), resp_headers
                except ValueError as exc:
                    raise self._fail(ApiError, f"invalid JSON from {url}: {exc}") from None
            except urllib.error.HTTPError as err:
                self._handle_http_error(err, url)
                reason = f"HTTP {err.code}"
            except urllib.error.URLError as err:
                reason = f"network error: {err.reason}"

            if attempt >= len(RETRY_DELAYS):
                raise self._fail(
                    ApiError, f"request to {url} failed after retries ({reason})"
                )
            delay = RETRY_DELAYS[attempt]
            attempt += 1
            self._log(
                logging.WARNING,
                f"WARNING: {reason} for {url}; retry {attempt}/{len(RETRY_DELAYS)} in {delay}s",
            )
            self._sleep(delay)

    def _handle_http_error(self, err: urllib.error.HTTPError, url: str) -> None:
        """Raise for non-retryable errors; return for retryable (5xx)."""
        code = err.code
        if code >= 500:
            return
        hdrs = err.headers or {}
        if code == 401:
            raise self._fail(AuthError, f"authentication failed for {url} (HTTP 401)")
        if code in (403, 429) and hdrs.get("X-RateLimit-Remaining") == "0":
            reset_at = _parse_reset(hdrs.get("X-RateLimit-Reset"))
            raise self._fail(
                RateLimitError,
                f"rate limit exhausted; resets at {reset_at.isoformat()}",
                reset_at,
            )
        raise self._fail(ApiError, f"HTTP {code} for {url}")

    # -- public API --------------------------------------------------
    def graphql(self, query: str, variables: dict | None = None) -> dict:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        data, headers = self._request(GRAPHQL_URL, payload)
        errors = data.get("errors") if isinstance(data, dict) else None
        if errors:
            if any(isinstance(e, dict) and e.get("type") == "RATE_LIMITED" for e in errors):
                reset_at = _parse_reset(headers.get("X-RateLimit-Reset") if headers else None)
                raise self._fail(
                    RateLimitError,
                    f"rate limit exhausted; resets at {reset_at.isoformat()}",
                    reset_at,
                )
            messages = "; ".join(
                str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in errors
            )
            raise self._fail(ApiError, f"GraphQL error: {messages}")
        if not isinstance(data, dict) or "data" not in data:
            raise self._fail(ApiError, "GraphQL response missing data")
        return data["data"]

    def rest_pages(
        self, path: str, per_page: int = 100, max_pages: int = 3
    ) -> Iterator[dict]:
        """Yield items from a paginated REST list endpoint, in page order."""
        sep = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            url = f"{API_ROOT}{path}{sep}per_page={per_page}&page={page}"
            data, _ = self._request(url)
            if not isinstance(data, list):
                raise self._fail(ApiError, f"expected a list from {url}")
            yield from data
            if len(data) < per_page:
                return


def _parse_reset(value: str | None) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return datetime.now(tz=timezone.utc)
