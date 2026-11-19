"""Auth routes: register, login and the current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth import service
from backend.app.auth.dependencies import current_user
from backend.app.models import User
from backend.app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(tags=["auth"])


def _map_value_error(exc: ValueError) -> HTTPException:
    """Map a service ``ValueError`` to 409 (duplicate) or 422 (validation)."""
    if "already registered" in str(exc):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _token_response(user: User, token: str) -> TokenResponse:
    """Build a ``TokenResponse`` from a user and token."""
    return TokenResponse(
        user=UserOut(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
        ),
        token=token,
    )


@router.post("/auth/register", status_code=201, response_model=TokenResponse)
def register(body: RegisterRequest) -> TokenResponse:
    """Register a new account and return a token.

    Args:
        body: The register request.

    Returns:
        The created user and its token.
    """
    try:
        user, token = service.register_user(body.email, body.password)
    except ValueError as exc:
        raise _map_value_error(exc) from exc
    return _token_response(user, token)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    """Log in with email and password.

    Args:
        body: The login request.

    Returns:
        The user and a fresh token.

    Raises:
        HTTPException: 401 with a generic detail on failure.
    """
    result = service.authenticate(body.email, body.password)
    if result is None:
        raise HTTPException(
            status_code=401,
            detail="invalid credentials",
        )
    user, token = result
    return _token_response(user, token)


@router.get("/auth/me", response_model=UserOut)
def me(user: Annotated[User, Depends(current_user)]) -> UserOut:
    """Return the authenticated user.

    Args:
        user: The current user injected by the dependency.

    Returns:
        The public user representation.
    """
    return UserOut(id=user.id, email=user.email, created_at=user.created_at)
