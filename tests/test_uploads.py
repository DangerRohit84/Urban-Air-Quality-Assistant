"""Tests for metadata-only security logging on upload rejections."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from backend.app.body_limit import UPLOAD_HEADROOM, BodyLimitMiddleware
from backend.app.config import settings
from backend.app.upload_slot import UPLOAD_SLOT
from tests.pdf_fixtures import flate_bomb_pdf, text_pdf

UPLOAD = "/documents/upload"


def _upload(
    client: TestClient,
    headers: dict[str, str],
    body: bytes,
    filename: str = "note.pdf",
) -> Response:
    """POST one PDF file part and return the response.

    Args:
        client: The test client.
        headers: The bearer header.
        body: The file bytes.
        filename: The uploaded filename.

    Returns:
        The HTTP response.
    """
    return client.post(
        UPLOAD,
        headers=headers,
        files={"file": (filename, body, "application/pdf")},
    )


def _rejections(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    """Return parsed ``upload_rejected`` events from the security logger.

    Args:
        caplog: The captured log fixture.

    Returns:
        The parsed events.
    """
    events: list[dict[str, object]] = []
    for record in caplog.records:
        if record.name != "security":
            continue
        try:
            payload = json.loads(record.getMessage())
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "upload_rejected":
            events.append(payload)
    return events


def _assert_rejection(
    caplog: pytest.LogCaptureFixture, reason: str, secret: str | None = None
) -> None:
    """Assert exactly one rejection event with metadata-only fields.

    Args:
        caplog: The captured log fixture.
        reason: The expected rejection reason.
        secret: An optional marker that must not appear in the logs.
    """
    assert _rejections(caplog) == [
        {"event": "upload_rejected", "path": UPLOAD, "reason": reason}
    ]
    if secret is not None:
        assert secret not in caplog.text


def test_missing_file_part_logs_missing_file(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A form without a file part logs the missing-file reason."""
    caplog.set_level(logging.WARNING, logger="security")

    response = client.post(UPLOAD, headers=auth_headers, data={"file": "not-a-file"})

    assert response.status_code == 400
    _assert_rejection(caplog, "missing_file")


def test_pre_parse_rejection_logs_pre_parse_failed(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-PDF filename is rejected and logged before parsing."""
    caplog.set_level(logging.WARNING, logger="security")

    response = _upload(client, auth_headers, b"plain text", filename="notes.txt")

    assert response.status_code == 400
    _assert_rejection(caplog, "pre_parse_failed")


def test_route_oversize_logs_too_large(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A body above the route cap logs the too-large reason."""
    caplog.set_level(logging.WARNING, logger="security")
    monkeypatch.setattr(settings, "max_upload_bytes", 64)

    response = _upload(client, auth_headers, b"%PDF-1.4\n" + b"x" * 128)

    assert response.status_code == 413
    _assert_rejection(caplog, "too_large")


def test_middleware_oversize_logs_too_large(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A body above the middleware limit logs before the route runs."""
    caplog.set_level(logging.WARNING, logger="security")
    body = b"%PDF-1.4\n" + b"x" * (settings.max_upload_bytes + UPLOAD_HEADROOM)

    response = _upload(client, auth_headers, body)

    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}
    _assert_rejection(caplog, "too_large")


def test_streamed_upload_oversize_logs_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A chunked body crossing the cap logs one metadata-only event."""
    caplog.set_level(logging.WARNING, logger="security")
    chunks = iter([{"type": "http.request", "body": b"xxx", "more_body": True}])
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return next(chunks)

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    async def app(scope, receive, send) -> None:
        await receive()

    middleware = BodyLimitMiddleware(app, json_limit=2, upload_limit=2)
    scope = {"type": "http", "path": UPLOAD, "headers": []}
    asyncio.run(middleware(scope, receive, send))

    assert sent[0]["status"] == 413
    _assert_rejection(caplog, "too_large")


def test_complex_pdf_logs_pdf_too_complex(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A decompression bomb logs the complexity reason."""
    caplog.set_level(logging.WARNING, logger="security")

    response = _upload(client, auth_headers, flate_bomb_pdf())

    assert response.status_code == 422
    _assert_rejection(caplog, "pdf_too_complex")


def test_malformed_pdf_logs_malformed_pdf(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A malformed PDF logs only metadata, never the filename."""
    caplog.set_level(logging.WARNING, logger="security")
    marker = "private-upload-marker"

    response = _upload(
        client, auth_headers, b"%PDF-1.4\n" + b"x" * 64, filename=f"{marker}.pdf"
    )

    assert response.status_code == 400
    _assert_rejection(caplog, "malformed_pdf", secret=marker)


def test_document_limit_logs_document_limit(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistence-layer 409 logs the document-limit reason."""
    caplog.set_level(logging.WARNING, logger="security")
    monkeypatch.setattr(settings, "max_documents", 1)
    created = client.post(
        "/documents",
        headers=auth_headers,
        json={"title": "Existing", "text": "one document"},
    )
    assert created.status_code == 201

    response = _upload(client, auth_headers, text_pdf("second document"))

    assert response.status_code == 409
    _assert_rejection(caplog, "document_limit")


def test_empty_extracted_text_logs_invalid_text(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A PDF with no extractable text logs the invalid-text reason."""
    caplog.set_level(logging.WARNING, logger="security")

    response = _upload(client, auth_headers, text_pdf(""))

    assert response.status_code == 422
    _assert_rejection(caplog, "invalid_text")


def test_busy_slot_logs_busy(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A request while another upload holds the slot logs the busy reason."""
    caplog.set_level(logging.WARNING, logger="security")
    asyncio.run(UPLOAD_SLOT.acquire())
    try:
        response = _upload(client, auth_headers, text_pdf("busy"))
    finally:
        UPLOAD_SLOT.release()

    assert response.status_code == 503
    _assert_rejection(caplog, "busy")
