"""Tests for the ``/health`` endpoint."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backend.app.main import app

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
