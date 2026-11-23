"""Owner-scoped document routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from backend.app import access
from backend.app.auth.dependencies import require_user_id
from backend.app.retrieval import invalidate_cache
from backend.app.routes.common import AUTH_RESPONSES, BODY_LIMIT_RESPONSE
from backend.app.routes.document_store import store_document
from backend.app.schemas.documents import (
    DocumentIn,
    DocumentResponse,
    DocumentSummary,
)
from backend.app.schemas.errors import ErrorResponse
from backend.app.security import sanitize_text
from backend.app.storage.store import get_repo

router = APIRouter(tags=["documents"])

CREATE_DOCUMENT_RESPONSES: dict[int | str, dict[str, object]] = {
    **AUTH_RESPONSES,
    **BODY_LIMIT_RESPONSE,
    409: {
        "model": ErrorResponse,
        "description": "Document limit reached for this owner.",
    },
}
DELETE_DOCUMENT_RESPONSES: dict[int | str, dict[str, object]] = {
    **AUTH_RESPONSES,
    404: {
        "model": ErrorResponse,
        "description": "Document missing or owned by another account.",
    },
}


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=201,
    responses=CREATE_DOCUMENT_RESPONSES,
)
def create_document(
    payload: DocumentIn,
    user_id: Annotated[str, Depends(require_user_id)],
) -> DocumentResponse:
    """Store a text document for the caller.

    Args:
        payload: The document fields.
        user_id: The verified owner id.

    Returns:
        The stored document.
    """
    return store_document(
        user_id,
        sanitize_text(payload.title, 200),
        payload.text,
        "corpus",
        "user",
    )


@router.get(
    "/documents",
    response_model=list[DocumentSummary],
    responses=AUTH_RESPONSES,
)
def list_documents(
    user_id: Annotated[str, Depends(require_user_id)],
) -> list[DocumentSummary]:
    """List the caller's documents without their full text.

    Args:
        user_id: The verified owner id.

    Returns:
        A compact summary for each of the owner's documents.
    """
    return [
        DocumentSummary(
            id=doc.id,
            kind=doc.kind,
            title=doc.title,
            created_at=doc.created_at,
        )
        for doc in get_repo().list_documents(user_id)
    ]


@router.delete(
    "/documents/{doc_id}",
    status_code=204,
    responses=DELETE_DOCUMENT_RESPONSES,
)
def delete_document(
    doc_id: str,
    user_id: Annotated[str, Depends(require_user_id)],
) -> Response:
    """Delete a document owned by the caller.

    Args:
        doc_id: The document id.
        user_id: The verified owner id.

    Returns:
        An empty 204 response.

    Raises:
        HTTPException: 404 when the document is missing or foreign.
    """
    repo = get_repo()
    access.get_owned_document(repo, doc_id, user_id)
    repo.delete_document(doc_id, user_id)
    invalidate_cache(user_id)
    return Response(status_code=204)
