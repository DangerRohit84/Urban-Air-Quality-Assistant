"""Metadata-only security events for rejected PDF uploads."""

from __future__ import annotations

from fastapi import HTTPException

from backend.app.security_log import log_event

STORE_REASONS = {409: "document_limit", 422: "invalid_text"}


def log_rejected(path: str, reason: str) -> None:
    """Emit one metadata-only ``upload_rejected`` event.

    Args:
        path: The request path.
        reason: A short, non-secret rejection code.
    """
    log_event("upload_rejected", path=path, reason=reason)


def log_store_rejected(path: str, exc: HTTPException) -> None:
    """Log why the persistence layer rejected extracted document text.

    Args:
        path: The request path.
        exc: The rejection raised by ``store_document``.
    """
    reason = STORE_REASONS.get(exc.status_code)
    if reason is not None:
        log_rejected(path, reason)
