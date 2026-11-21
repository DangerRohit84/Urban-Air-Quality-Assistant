"""FastAPI authentication dependencies."""

from __future__ import annotations

from dataclasses import replace

from fastapi import HTTPException, Request

from backend.app.auth.claims import TokenClaims
from backend.app.auth.tokens import verify_claims
from backend.app.models import Profile, User
from backend.app.profile import DEFAULT_PROFILE
from backend.app.storage.protocol import Repository
from backend.app.storage.store import get_repo

INVALID_CREDENTIALS = "invalid credentials"


def bearer_claims(request: Request) -> TokenClaims:
    """Extract, verify and revocation-check the bearer token.

    Args:
        request: The incoming request.

    Returns:
        The verified token claims.

    Raises:
        HTTPException: 401 with a generic detail on any failure.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    claims = verify_claims(token.strip())
    if claims is None:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    if claims.jti is not None and get_repo().is_token_revoked(claims.jti):
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    return claims


def bearer_token(request: Request) -> str:
    """Extract and verify the bearer token.

    Args:
        request: The incoming request.

    Returns:
        The verified user id.

    Raises:
        HTTPException: 401 with a generic detail on any failure.
    """
    return bearer_claims(request).subject


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


def load_profile_or_default(repo: Repository, user_id: str) -> Profile:
    """Return the stored profile or the shared default.

    Args:
        repo: The repository to query.
        user_id: The owner.

    Returns:
        The stored profile, or ``DEFAULT_PROFILE`` stamped with ``user_id``.
    """
    profile = repo.get_profile(user_id)
    if profile is not None:
        return profile
    return replace(DEFAULT_PROFILE, user_id=user_id)
