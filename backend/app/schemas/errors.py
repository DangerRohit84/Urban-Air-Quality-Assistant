"""Shared error response schema for OpenAPI declarations."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard ``{"detail": str}`` envelope returned by error paths."""

    detail: str = Field(
        description="Human-readable error message; never contains internals.",
        examples=["invalid credentials"],
    )
