"""FastAPI authentication dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request

from backend.app.auth.tokens import verify_token
from backend.app.models import User
from backend.app.storage.store import get_repo

INVALID_CREDENTIALS = "invalid credentials"


def bearer_token(request: Request) -> str:
    """Extract and verify the bearer token.

    Args:
        request: The incoming request.

    Returns:
        The verified user id.

    Raises:
        HTTPException: 401 with a generic detail on any failure.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    user_id = verify_token(token.strip())
    if user_id is None:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    return user_id


def require_user_id(request: Request) -> str:
    """Return the verified user id or raise a generic 401.

    Args:
        request: The incoming request.

    Returns:
        The verified user id.
    """
    return bearer_token(request)


def current_user(request: Request) -> User:
    """Return the stored user for the bearer token.

    Args:
        request: The incoming request.

    Returns:
        The stored user.

    Raises:
        HTTPException: 401 when the token is invalid or the user is gone.
    """
    user_id = bearer_token(request)
    user = get_repo().get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    return user
