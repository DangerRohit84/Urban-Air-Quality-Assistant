"""Efficiency tests: latency bounds, clamping and bounded reads."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backend.app import retrieval
from backend.app.config import settings

MAX_LATENCY_SECONDS = 1.0


def test_health_latency_is_bounded(client: TestClient) -> None:
    """``GET /health`` answers in well under a second."""
    start = time.perf_counter()
    response = client.get("/health")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < MAX_LATENCY_SECONDS


def test_search_latency_is_bounded() -> None:
    """A corpus search answers in well under a second."""
    retrieval.reset_cache()
    start = time.perf_counter()
    hits = retrieval.search("indoor air purifier")
    elapsed = time.perf_counter() - start

    assert hits
    assert elapsed < MAX_LATENCY_SECONDS


def test_top_k_is_clamped_to_ten() -> None:
    """``top_k`` never returns more than ten hits."""
    assert len(retrieval.search("air quality", top_k=100)) <= 10
    assert len(retrieval.search("air quality", top_k=0)) <= 10


def test_oversize_upload_is_413(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """A payload above the cap is rejected before parsing."""
    monkeypatch.setattr(settings, "max_upload_bytes", 64)
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("big.pdf", b"%PDF-" + b"x" * 128, "application/pdf")},
    )

    assert response.status_code == 413


def test_non_pdf_upload_is_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A payload with the wrong magic bytes is rejected."""
    response = client.post(
        "/documents/upload",
        headers=auth_headers,
        files={"file": ("note.pdf", b"not a pdf", "application/pdf")},
    )

    assert response.status_code == 400


def test_process_time_header_is_present(client: TestClient) -> None:
    """Every response reports its processing time."""
    response = client.get("/health")

    assert response.status_code == 200
    assert "x-process-time" in response.headers
    assert float(response.headers["x-process-time"]) >= 0
