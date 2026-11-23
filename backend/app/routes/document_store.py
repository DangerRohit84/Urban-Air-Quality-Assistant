"""Shared document persistence used by the text and upload routes."""

from __future__ import annotations

from fastapi import HTTPException

from backend.app.chunking import chunk_text
from backend.app.config import settings
from backend.app.models import Document
from backend.app.retrieval import invalidate_cache
from backend.app.schemas.documents import DocumentResponse
from backend.app.security import MAX_DOCUMENT_CHARS, sanitize_text
from backend.app.storage.store import get_repo


def store_document(
    user_id: str, title: str, text: str, kind: str, source: str
) -> DocumentResponse:
    """Persist a document and invalidate the owner's retrieval cache.

    Args:
        user_id: The verified owner id.
        title: The document title.
        text: The document text.
        kind: The document kind.
        source: The document source.

    Returns:
        The stored document response.

    Raises:
        HTTPException: 409 when the document limit is reached, 422 when the
            text is empty after sanitization or exceeds ``MAX_DOCUMENT_CHARS``.
    """
    # Keep one character past the cap so the explicit 422 wins over silent
    # truncation, and sanitize PDF text on the same path as manual text.
    text = sanitize_text(text, MAX_DOCUMENT_CHARS + 1)
    if not text:
        raise HTTPException(status_code=422, detail="document text must not be empty")
    if len(text) > MAX_DOCUMENT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"document text exceeds {MAX_DOCUMENT_CHARS} characters",
        )
    repo = get_repo()
    if repo.count_documents(user_id) >= settings.max_documents:
        raise HTTPException(status_code=409, detail="document limit reached")
    saved = repo.create_document(
        Document(
            id="",
            owner_id=user_id,
            kind=kind,
            title=title,
            text=text,
            chunks=chunk_text(text),
            source=source,
            created_at="",
        )
    )
    invalidate_cache(user_id)
    return DocumentResponse(**saved.to_dict())
