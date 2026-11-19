"""Owner-scoped access helpers shared by the data routes."""

from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException

from backend.app.models import Document, Profile
from backend.app.storage.protocol import Repository

NOT_FOUND = "not found"


class Owned(Protocol):
    """A resource that belongs to exactly one owner."""

    owner_id: str


def owner_or_404(repo: Repository, resource: Owned, user_id: str) -> Owned:
    """Return ``resource`` when it is owned by ``user_id``.

    Args:
        repo: The repository holding the resource.
        resource: The resource to check.
        user_id: The requesting owner.

    Returns:
        The resource.

    Raises:
        HTTPException: 404 when the resource belongs to another owner.
    """
    if resource.owner_id != user_id:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return resource


def get_owned_document(repo: Repository, doc_id: str, user_id: str) -> Document:
    """Return a document when it exists and is owned by ``user_id``.

    Args:
        repo: The repository to query.
        doc_id: The document id.
        user_id: The requesting owner.

    Returns:
        The document.

    Raises:
        HTTPException: 404 when the document is missing or foreign.
    """
    doc = repo.get_document(doc_id)
    if doc is None or doc.owner_id != user_id:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return doc


def get_owned_profile(repo: Repository, user_id: str) -> Profile | None:
    """Return the profile for ``user_id`` or None when absent.

    Args:
        repo: The repository to query.
        user_id: The owner.

    Returns:
        The stored profile, or None.
    """
    return repo.get_profile(user_id)
