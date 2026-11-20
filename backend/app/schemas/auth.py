"""Auth request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Body of ``POST /auth/register``."""

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Body of ``POST /auth/login``."""

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """Public user representation."""

    id: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    """Register and login response."""

    user: UserOut
    token: str
