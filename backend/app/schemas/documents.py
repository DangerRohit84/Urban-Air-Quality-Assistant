"""Document request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    """Payload accepted by ``POST /documents``."""

    title: str = Field(
        min_length=1,
        max_length=200,
        description="Human-readable document title.",
        examples=["Indoor air notes"],
    )
    # The route enforces non-empty text and MAX_DOCUMENT_CHARS so an empty or
    # over-limit body gets the documented 422 message instead of a generic
    # schema error.
    text: str = Field(
        description="Document body; sanitized before storage.",
        examples=["HEPA filters remove fine particles from indoor air."],
    )


class DocumentSummary(BaseModel):
    """Compact payload returned by ``GET /documents``."""

    id: str = Field(description="Stable document identifier.", examples=["doc-0001"])
    kind: str = Field(description="Document kind, e.g. `corpus`.", examples=["corpus"])
    title: str = Field(
        description="Sanitized document title.", examples=["Indoor air notes"]
    )
    created_at: str = Field(
        description="ISO-8601 creation timestamp (UTC).",
        examples=["2026-01-02T03:04:05+00:00"],
    )


class DocumentResponse(BaseModel):
    """Payload returned by the document routes."""

    id: str = Field(description="Stable document identifier.", examples=["doc-0001"])
    owner_id: str = Field(description="Owner user id.", examples=["user-0001"])
    kind: str = Field(description="Document kind, e.g. `corpus`.", examples=["corpus"])
    title: str = Field(
        description="Sanitized document title.", examples=["Indoor air notes"]
    )
    text: str = Field(
        description="Sanitized document body.",
        examples=["HEPA filters remove fine particles from indoor air."],
    )
    chunks: list[str] = Field(
        description="Chunks used for retrieval.",
        examples=[["HEPA filters remove fine particles from indoor air."]],
    )
    source: str = Field(
        description="Origin of the document, e.g. `user`.", examples=["user"]
    )
    created_at: str = Field(
        description="ISO-8601 creation timestamp (UTC).",
        examples=["2026-01-02T03:04:05+00:00"],
    )
