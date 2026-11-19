"""Shared pytest fixtures: environment, repo reset and authed client."""

from __future__ import annotations

import os

os.environ.setdefault("AUTH_SECRET", "test-secret")
os.environ.setdefault("LLM_PROVIDER", "local_synth")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.config import settings  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.rate_limiter import SlidingWindowRateLimiter  # noqa: E402
from backend.app.storage.memory import InMemoryRepo  # noqa: E402
from backend.app.storage.store import reset_repo  # noqa: E402


def _reset_retrieval_cache() -> None:
    """Reset the retrieval cache when that module exists."""
    try:
        from backend.app import retrieval
    except ImportError:
        return
    retrieval.reset_cache()


def _reset_rate_limiter() -> None:
    """Install a fresh rate limiter so tests never inherit a full bucket."""
    app.state.rate_limiter = SlidingWindowRateLimiter(
        limit=settings.rate_limit_per_min,
        max_buckets=settings.max_rate_buckets,
    )


@pytest.fixture(autouse=True)
def _fresh_repo() -> object:
    """Give every test a clean in-memory repository and limiter."""
    reset_repo(InMemoryRepo())
    _reset_retrieval_cache()
    _reset_rate_limiter()
    yield
    reset_repo(InMemoryRepo())
    _reset_retrieval_cache()
    _reset_rate_limiter()


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient for the shared application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Register a user and return its bearer header."""
    response = client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "TestPass123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['token']}"}
