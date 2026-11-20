"""Document request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    """Payload accepted by ``POST /documents``."""

    title: str = Field(min_length=1, max_length=200)
    # The route enforces non-empty text and MAX_DOCUMENT_CHARS so an empty or
    # over-limit body gets the documented 422 message instead of a generic
    # schema error.
    text: str


class DocumentResponse(BaseModel):
    """Payload returned by the document routes."""

    id: str
    owner_id: str
    kind: str
    title: str
    text: str
    chunks: list[str]
    source: str
    created_at: str
