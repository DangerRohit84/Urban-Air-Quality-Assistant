"""Tests for security headers and the sliding-window rate limiter."""

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
    "x-process-time",
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


def test_unhandled_exception_is_bare_500_with_headers() -> None:
    """An unhandled exception yields a bare 500 that keeps the headers."""
    client = _make_client()

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "x-content-type-options" in response.headers
    assert "x-process-time" in response.headers


def test_200_carries_rate_limit_headers() -> None:
    """A successful response reports the rate-limit budget."""
    client = _make_client(limit=10)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "10"
    assert "x-ratelimit-remaining" in response.headers
    assert "x-ratelimit-reset" in response.headers


def test_limit_plus_one_requests_is_429() -> None:
    """The (limit + 1)-th request in a window is rejected with Retry-After."""
    client = _make_client(limit=5)

    for _ in range(5):
        assert client.get("/health").status_code == 200

    response = client.get("/health")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.headers["x-ratelimit-remaining"] == "0"


def test_buckets_are_keyed_on_client_host_not_proxy_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``X-Forwarded-For`` does not create a separate rate-limit bucket."""
    monkeypatch.setattr(settings, "rate_limit_per_min", 2)
    client = TestClient(create_app())

    first = client.get("/health", headers={"X-Forwarded-For": "1.1.1.1"})
    second = client.get("/health", headers={"X-Forwarded-For": "2.2.2.2"})
    third = client.get("/health", headers={"X-Forwarded-For": "3.3.3.3"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
