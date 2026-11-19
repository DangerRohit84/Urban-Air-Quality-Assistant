"""Auth request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    """Body of ``POST /auth/register``."""

    email: str
    password: str


class LoginRequest(BaseModel):
    """Body of ``POST /auth/login``."""

    email: str
    password: str


class UserOut(BaseModel):
    """Public user representation."""

    id: str
    email: str
    created_at: str


class TokenResponse(BaseModel):
    """Register and login response."""

    user: UserOut
    token: str
