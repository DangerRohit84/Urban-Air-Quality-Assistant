"""Owner-scoped document routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.app import access
from backend.app.auth.dependencies import require_user_id
from backend.app.chunking import chunk_text
from backend.app.config import settings
from backend.app.models import Document
from backend.app.retrieval import reset_cache
from backend.app.schemas.documents import DocumentIn, DocumentResponse
from backend.app.security import sanitize_text
from backend.app.storage.store import get_repo

router = APIRouter(tags=["documents"])


def store_document(
    user_id: str, title: str, text: str, kind: str, source: str
) -> DocumentResponse:
    """Persist a document and invalidate the retrieval cache.

    Args:
        user_id: The verified owner id.
        title: The document title.
        text: The document text.
        kind: The document kind.
        source: The document source.

    Returns:
        The stored document response.

    Raises:
        HTTPException: 409 when the document limit is reached.
    """
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
    reset_cache()
    return DocumentResponse(**saved.to_dict())


@router.post("/documents", response_model=DocumentResponse, status_code=201)
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
        sanitize_text(payload.text),
        "corpus",
        "user",
    )


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    user_id: Annotated[str, Depends(require_user_id)],
) -> list[DocumentResponse]:
    """List the caller's documents.

    Args:
        user_id: The verified owner id.

    Returns:
        The owner's documents.
    """
    return [
        DocumentResponse(**doc.to_dict())
        for doc in get_repo().list_documents(user_id)
    ]


@router.delete("/documents/{doc_id}", status_code=204)
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
    reset_cache()
    return Response(status_code=204)
