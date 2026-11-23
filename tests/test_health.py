"""Tests for the ``/health`` endpoint and the root route."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routes import system as system_routes

PROVIDERS = {"gemini", "openai-compat", "local_synth", "echo"}


def test_health_returns_status_provider_cache_store_and_uptime() -> None:
    """``GET /health`` reports the provider, cache, store counts and uptime."""
    client = TestClient(app)

    start = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] in PROVIDERS
    assert {"hits", "misses", "size"} <= set(body["cache"])
    assert {"users", "profiles", "documents"} <= set(body["store"])
    assert body["uptime_seconds"] >= 0
    assert elapsed < 1.0


def test_health_provider_matches_the_factory() -> None:
    """``/health`` reports the provider the factory actually builds."""
    from backend.app.llm.factory import build_provider, provider_name

    body = TestClient(app).get("/health").json()

    assert body["provider"] == provider_name()
    assert body["provider"] == build_provider().name


def test_index_serves_the_frontend_shell(client: TestClient) -> None:
    """``GET /`` serves the HTML shell when the assets are present."""
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Urban Air Quality Assistant" in response.text


def test_index_falls_back_to_json_when_the_shell_is_absent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A wheel-only install returns API pointers instead of a 500."""
    monkeypatch.setattr(system_routes, "FRONTEND_DIR", tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["service"] == "Urban Air Quality Assistant"
    assert body["docs"] == "/docs"
    assert body["health"] == "/health"
    assert "not installed" in body["note"]
