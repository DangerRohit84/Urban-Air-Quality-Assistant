"""Ask request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskIn(BaseModel):
    """Payload accepted by ``POST /ask``."""

    question: str = Field(
        min_length=1,
        max_length=500,
        description="Air-quality question in natural language.",
        examples=["Does a HEPA purifier help indoors?"],
    )
    plain_language: bool = Field(
        default=False,
        description="Ask for a plain-language answer.",
        examples=[True],
    )


class AskResponse(BaseModel):
    """Payload returned by ``POST /ask``."""

    answer: str = Field(
        description="Grounded answer or a refusal.",
        examples=["Yes - a HEPA purifier lowers indoor PM2.5. [seed-001]"],
    )
    citations: list[str] = Field(
        description="Supporting document ids (max 3).",
        examples=[["seed-001"]],
    )
    mode: str = Field(description="`plain` or `standard`.", examples=["plain"])
    grounded: bool = Field(
        description="False when the answer is a refusal.",
        examples=[True],
    )
