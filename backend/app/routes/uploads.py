"""PDF upload route."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.auth.dependencies import require_user_id
from backend.app.config import settings
from backend.app.pdf_text import extract_pdf_text
from backend.app.routes.documents import store_document
from backend.app.schemas.documents import DocumentResponse
from backend.app.security import sanitize_filename
from backend.app.upload_guard import validate_pre_parse

router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    user_id: Annotated[str, Depends(require_user_id)],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    """Upload and parse a PDF for the caller.

    Args:
        user_id: The verified owner id.
        file: The uploaded PDF.

    Returns:
        The stored document.

    Raises:
        HTTPException: 400 on a bad upload, 409 on the limit, 413 on oversize,
            422 when the extracted text is empty or exceeds
            ``MAX_DOCUMENT_CHARS``.
    """
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file too large")
    try:
        validate_pre_parse(
            file.filename or "", file.content_type or "", len(raw), raw
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        text = await asyncio.to_thread(extract_pdf_text, raw)
    except Exception as exc:  # noqa: BLE001 - malformed PDFs are client errors
        raise HTTPException(status_code=400, detail="could not parse PDF") from exc
    return store_document(
        user_id,
        sanitize_filename(file.filename or "upload.pdf"),
        text,
        "upload",
        "upload",
    )
