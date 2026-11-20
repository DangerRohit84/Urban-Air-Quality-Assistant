"""Tests for the dependency-free JSON HTTP helper."""

from __future__ import annotations

import json

import pytest

from backend.app.llm import http_json
from tests.http_server import serve


class _Response:
    """Minimal stand-in for ``urllib``'s response context manager."""

    def __init__(self, payload: bytes, headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self.headers = headers or {}

    def read(self, amount: int | None = None) -> bytes:
        """Return the raw response body, optionally capped."""
        return self._payload if amount is None else self._payload[:amount]

    def __enter__(self) -> _Response:
        """Enter the response context."""
        return self

    def __exit__(self, *args: object) -> bool:
        """Leave the response context without suppressing exceptions."""
        return False


class _Opener:
    """Fake opener that records the request and returns a canned response."""

    def __init__(self, response: _Response) -> None:
        self.response = response
        self.captured: dict[str, object] = {}

    def open(self, request: object, timeout: float) -> _Response:
        """Record the request and return the canned response."""
        self.captured.update(request=request, timeout=timeout)
        return self.response


def test_post_json_encodes_and_decodes(monkeypatch: object) -> None:
    """The helper posts JSON and returns the decoded object."""
    opener = _Opener(_Response(json.dumps({"ok": True}).encode("utf-8")))
    monkeypatch.setattr(http_json, "_opener", lambda: opener)

    result = http_json.post_json(
        "https://example.test/x", {"a": 1}, {"X-Test": "1"}
    )

    assert result == {"ok": True}
    request = opener.captured["request"]
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8")) == {"a": 1}
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("X-test") == "1"
    assert opener.captured["timeout"] == http_json.TIMEOUT_SECONDS


def test_post_json_rejects_non_object(monkeypatch: object) -> None:
    """A JSON array response is rejected as malformed."""
    monkeypatch.setattr(http_json, "_opener", lambda: _Opener(_Response(b"[]")))

    with pytest.raises(ValueError, match="JSON object"):
        http_json.post_json("https://example.test/x", {}, {})


def test_post_json_rejects_unsupported_schemes() -> None:
    """Only HTTP(S) endpoints are accepted."""
    with pytest.raises(ValueError, match="http"):
        http_json.post_json("file:///etc/passwd", {}, {})


def test_post_json_does_not_follow_redirects() -> None:
    """A 302 never reaches the redirect target with the bearer token."""
    with serve(302, b"", location="/capture") as server, pytest.raises(
        (OSError, ValueError)
    ):
        http_json.post_json(
            f"{server.base_url}/chat/completions",
            {},
            {"Authorization": "Bearer secret"},
        )

    assert [hit.path for hit in server.hits] == ["/chat/completions"]
    assert server.hits[0].authorization == "Bearer secret"


def test_post_json_rejects_declared_oversize(monkeypatch: object) -> None:
    """A declared ``Content-Length`` above the cap is rejected before reading."""
    headers = {"Content-Length": str(http_json.MAX_RESPONSE_BYTES + 1)}
    opener = _Opener(_Response(b"{}", headers))
    monkeypatch.setattr(http_json, "_opener", lambda: opener)

    with pytest.raises(ValueError, match="too large"):
        http_json.post_json("https://example.test/x", {}, {})


def test_post_json_caps_undeclared_bodies(monkeypatch: object) -> None:
    """A response without a declared length is read only up to the cap."""
    opener = _Opener(_Response(b"x" * (http_json.MAX_RESPONSE_BYTES + 1)))
    monkeypatch.setattr(http_json, "_opener", lambda: opener)

    with pytest.raises(ValueError, match="too large"):
        http_json.post_json("https://example.test/x", {}, {})
