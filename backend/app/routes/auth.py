"""Auth routes: register, login, logout and the current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.app.auth import service
from backend.app.auth.dependencies import bearer_claims, current_user
from backend.app.auth.service import DuplicateEmailError
from backend.app.models import User
from backend.app.routes.common import (
    AUTH_RESPONSES,
    BODY_LIMIT_RESPONSE,
    INTERNAL_ERROR,
    RATE_LIMIT_RESPONSE,
)
from backend.app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from backend.app.schemas.errors import ErrorResponse
from backend.app.storage.store import get_repo

router = APIRouter(tags=["auth"])

REGISTER_RESPONSES: dict[int | str, dict[str, object]] = {
    409: {
        "model": ErrorResponse,
        "description": "Email already registered.",
    },
    **RATE_LIMIT_RESPONSE,
    **BODY_LIMIT_RESPONSE,
    **INTERNAL_ERROR,
}
LOGIN_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {
        "model": ErrorResponse,
        "description": "Invalid email or password.",
    },
    **RATE_LIMIT_RESPONSE,
    **BODY_LIMIT_RESPONSE,
    **INTERNAL_ERROR,
}


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


@router.post(
    "/auth/register",
    status_code=201,
    response_model=TokenResponse,
    responses=REGISTER_RESPONSES,
)
def register(body: RegisterRequest) -> TokenResponse:
    """Register a new account and return a token.

    Args:
        body: The register request.

    Returns:
        The created user and its token.
    """
    try:
        user, token = service.register_user(body.email, body.password)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _token_response(user, token)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    responses=LOGIN_RESPONSES,
)
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


@router.get("/auth/me", response_model=UserOut, responses=AUTH_RESPONSES)
def me(user: Annotated[User, Depends(current_user)]) -> UserOut:
    """Return the authenticated user.

    Args:
        user: The current user injected by the dependency.

    Returns:
        The public user representation.
    """
    return UserOut(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/auth/logout", status_code=204, responses=AUTH_RESPONSES)
def logout(request: Request) -> Response:
    """Revoke the bearer token presented with the request.

    Args:
        request: The request carrying the token to revoke.

    Returns:
        An empty 204 response.
    """
    claims = bearer_claims(request)
    if claims.jti is not None:
        get_repo().revoke_token(claims.jti, claims.expires_ns)
    return Response(status_code=204)
