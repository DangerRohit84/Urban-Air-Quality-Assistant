"""Tests for security headers, rate limiting and body limits."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import create_app

EXPECTED_HEADERS = (
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "content-security-policy",
    "permissions-policy",
    "strict-transport-security",
    "cache-control",
)


def _make_client(limit: int = 200) -> TestClient:
    """Build a client for a fresh app with the given per-minute limit."""
    original_limit = settings.rate_limit_per_min
    settings.rate_limit_per_min = limit
    try:
        app = create_app()

        @app.get("/boom")
        def boom() -> None:
            raise RuntimeError("boom")

        return TestClient(app, raise_server_exceptions=False)
    finally:
        settings.rate_limit_per_min = original_limit


def test_security_headers_present_on_200_404_and_500() -> None:
    """Every response carries the full security header set."""
    client = _make_client()

    for path in ("/health", "/definitely-not-a-route", "/boom"):
        response = client.get(path)

        for header in EXPECTED_HEADERS:
            assert header in response.headers, f"{path} missing {header}"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"
        assert "x-process-time" not in response.headers


def test_unhandled_exception_is_bare_500_with_headers() -> None:
    """An unhandled exception yields a bare 500 that keeps the headers."""
    client = _make_client()

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "x-content-type-options" in response.headers
    assert "x-process-time" not in response.headers


def test_200_carries_rate_limit_headers() -> None:
    """A successful response reports the rate-limit budget."""
    client = _make_client(limit=10)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "10"
    assert response.headers["x-ratelimit-remaining"] == "10"
    assert "x-ratelimit-reset" in response.headers


def test_health_is_exempt_from_rate_limiting() -> None:
    """Health checks never consume or exhaust the budget."""
    client = _make_client(limit=1)

    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["x-ratelimit-remaining"] == "1"


def test_limit_plus_one_requests_is_429() -> None:
    """The (limit + 1)-th limited request is rejected with Retry-After."""
    client = _make_client(limit=5)

    for _ in range(5):
        assert client.get("/auth/me").status_code == 401

    response = client.get("/auth/me")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.headers["x-ratelimit-remaining"] == "0"


def test_forwarded_for_is_ignored_when_proxy_untrusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``X-Forwarded-For`` does not create a separate bucket by default."""
    monkeypatch.setattr(settings, "rate_limit_per_min", 2)
    monkeypatch.setattr(settings, "trust_proxy", False)
    client = TestClient(create_app())

    first = client.get("/auth/me", headers={"X-Forwarded-For": "1.1.1.1"})
    second = client.get("/auth/me", headers={"X-Forwarded-For": "2.2.2.2"})
    third = client.get("/auth/me", headers={"X-Forwarded-For": "3.3.3.3"})

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


def test_trusted_proxy_uses_the_first_forwarded_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``TRUST_PROXY`` the first hop identifies the client bucket."""
    monkeypatch.setattr(settings, "rate_limit_per_min", 1)
    monkeypatch.setattr(settings, "trust_proxy", True)
    client = TestClient(create_app())

    first = client.get("/auth/me", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"})
    second = client.get("/auth/me", headers={"X-Forwarded-For": "2.2.2.2, 10.0.0.1"})
    third = client.get("/auth/me", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.2"})

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


def test_oversized_json_body_is_413_without_echo() -> None:
    """A body above 1 MiB is rejected with a generic JSON 413."""
    client = _make_client()
    marker = "OVERSIZED_BODY_MARKER"
    payload = {"email": marker + "x" * (1024 * 1024), "password": "TestPass123"}

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}
    assert marker not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


def test_oversized_json_413_carries_cors_headers() -> None:
    """A browser client can read the 413 for an allowed origin."""
    client = _make_client()
    payload = {"email": "x" * (1024 * 1024), "password": "TestPass123"}

    response = client.post(
        "/auth/register",
        json=payload,
        headers={"Origin": "http://localhost:8000"},
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_streamed_oversized_body_is_413() -> None:
    """A chunked body is counted as it streams and rejected at the limit."""
    client = _make_client()
    prefix = b'{"email":"a@b.com","password":"TestPass123","padding":"'
    first_chunk = prefix + b"x" * (1024 * 1024)

    response = client.post(
        "/auth/login",
        content=iter([first_chunk, b'"}']),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}


def test_upload_path_allows_bodies_above_the_json_limit(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Uploads get headroom above 1 MiB and still reach the PDF parser."""
    body = b"%PDF-1.4\n" + b"x" * (1024 * 1024 + 64)

    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("large.pdf", body, "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "could not parse PDF"}
