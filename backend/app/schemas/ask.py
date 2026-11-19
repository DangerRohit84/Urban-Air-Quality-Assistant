"""Ask request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskIn(BaseModel):
    """Payload accepted by ``POST /ask``."""

    question: str = Field(min_length=1, max_length=500)
    plain_language: bool = False


class AskResponse(BaseModel):
    """Payload returned by ``POST /ask``."""

    answer: str
    citations: list[str]
    mode: str
    grounded: bool
