"""PDF upload route."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import UploadFile

from backend.app.auth.dependencies import require_user_id
from backend.app.config import settings
from backend.app.pdf_text import PdfTooComplexError, extract_pdf_text
from backend.app.routes.documents import store_document
from backend.app.schemas.documents import DocumentResponse
from backend.app.security import sanitize_filename
from backend.app.upload_guard import validate_pre_parse
from backend.app.upload_slot import BUSY_DETAIL, RETRY_AFTER_SECONDS, UPLOAD_SLOT

router = APIRouter(tags=["documents"])

UPLOAD_REQUEST_BODY: dict[str, Any] = {
    "required": True,
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["file"],
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        }
    },
}


@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=201,
    openapi_extra={"requestBody": UPLOAD_REQUEST_BODY},
)
async def upload_document(
    request: Request,
    user_id: Annotated[str, Depends(require_user_id)],
) -> DocumentResponse:
    """Upload and parse a PDF for the caller.

    The process-wide single-flight slot is taken before the multipart body is
    read, so concurrent uploads cannot hold several large bodies and PDF
    workers in memory at once. A caller that arrives while the slot is busy
    gets a 503 with ``Retry-After`` instead of queueing.

    Args:
        request: The incoming request carrying the multipart body.
        user_id: The verified owner id.

    Returns:
        The stored document.

    Raises:
        HTTPException: 400 on a bad upload, 409 on the limit, 413 on oversize,
            422 when the PDF is too complex or the extracted text is empty or
            exceeds ``MAX_DOCUMENT_CHARS``, and 503 while another upload is
            being parsed.
    """
    if UPLOAD_SLOT.locked():
        raise HTTPException(
            status_code=503,
            detail=BUSY_DETAIL,
            headers={"Retry-After": RETRY_AFTER_SECONDS},
        )
    # No await separates the check above from this take, so the pair is
    # atomic on the single event loop and no waiter is ever queued.
    await UPLOAD_SLOT.acquire()
    try:
        form = await request.form()
        try:
            upload = form.get("file")
            if not isinstance(upload, UploadFile):
                raise HTTPException(status_code=400, detail="file field is required")
            raw = await upload.read(settings.max_upload_bytes + 1)
            if len(raw) > settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail="file too large")
            try:
                validate_pre_parse(
                    upload.filename or "", upload.content_type or "", len(raw), raw
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            try:
                text = await asyncio.to_thread(extract_pdf_text, raw)
            except PdfTooComplexError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 - malformed PDFs are client errors
                raise HTTPException(
                    status_code=400, detail="could not parse PDF"
                ) from exc
            return store_document(
                user_id,
                sanitize_filename(upload.filename or "upload.pdf"),
                text,
                "upload",
                "upload",
            )
        finally:
            # FastAPI's ``File()`` path closes the parsed form for us; a
            # manual ``request.form()`` must close it or the spooled upload
            # file is left to the garbage collector.
            await form.close()
    finally:
        UPLOAD_SLOT.release()
