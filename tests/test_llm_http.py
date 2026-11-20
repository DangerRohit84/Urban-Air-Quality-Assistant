"""Tests for the dependency-free JSON HTTP helper."""

from __future__ import annotations

import json

from backend.app.llm import http_json


class _Response:
    """Minimal stand-in for ``urllib``'s response context manager."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        """Return the raw response body."""
        return self._payload

    def __enter__(self) -> _Response:
        """Enter the response context."""
        return self

    def __exit__(self, *args: object) -> bool:
        """Leave the response context without suppressing exceptions."""
        return False


def test_post_json_encodes_and_decodes(monkeypatch: object) -> None:
    """The helper posts JSON and returns the decoded object."""
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _Response:
        captured.update(request=request, timeout=timeout)
        return _Response(json.dumps({"ok": True}).encode("utf-8"))

    monkeypatch.setattr(http_json.urllib.request, "urlopen", fake_urlopen)

    result = http_json.post_json(
        "https://example.test/x", {"a": 1}, {"X-Test": "1"}
    )

    assert result == {"ok": True}
    request = captured["request"]
    assert request.get_method() == "POST"
    assert json.loads(request.data.decode("utf-8")) == {"a": 1}
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("X-test") == "1"
    assert captured["timeout"] == http_json.TIMEOUT_SECONDS


def test_post_json_rejects_non_object(monkeypatch: object) -> None:
    """A JSON array response is rejected as malformed."""
    monkeypatch.setattr(
        http_json.urllib.request,
        "urlopen",
        lambda request, timeout: _Response(b"[]"),
    )

    try:
        http_json.post_json("https://example.test/x", {}, {})
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected ValueError")
