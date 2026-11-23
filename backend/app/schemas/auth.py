"""Auth request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Body of ``POST /auth/register``."""

    email: str = Field(
        min_length=1,
        max_length=254,
        description="Account email; normalized to lower case.",
        examples=["asha@example.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="8-128 characters with at least one letter and one digit.",
        examples=["CorrectHorse9"],
    )


class LoginRequest(BaseModel):
    """Body of ``POST /auth/login``."""

    email: str = Field(
        min_length=1,
        max_length=254,
        description="Registered account email.",
        examples=["asha@example.com"],
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Account password.",
        examples=["CorrectHorse9"],
    )


class UserOut(BaseModel):
    """Public user representation."""

    id: str = Field(description="Stable user identifier.", examples=["user-0001"])
    email: str = Field(
        description="Normalized account email.", examples=["asha@example.com"]
    )
    created_at: str = Field(
        description="ISO-8601 creation timestamp (UTC).",
        examples=["2026-01-02T03:04:05+00:00"],
    )


class TokenResponse(BaseModel):
    """Register and login response."""

    user: UserOut = Field(
        description="The authenticated user.",
        examples=[
            {
                "id": "user-0001",
                "email": "asha@example.com",
                "created_at": "2026-01-02T03:04:05+00:00",
            }
        ],
    )
    token: str = Field(
        description="HMAC-signed bearer token; send as `Bearer`.",
        examples=["test-token-value"],
    )
