"""Profile routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app import access
from backend.app.auth.dependencies import require_user_id
from backend.app.profile import normalize_profile
from backend.app.routes.common import AUTH_RESPONSES, BODY_LIMIT_RESPONSE
from backend.app.schemas.errors import ErrorResponse
from backend.app.schemas.profile import ProfileResponse, ProfileUpdate
from backend.app.storage.store import get_repo

router = APIRouter(tags=["profile"])

PROFILE_RESPONSES: dict[int | str, dict[str, object]] = {
    **AUTH_RESPONSES,
    404: {
        "model": ErrorResponse,
        "description": "No profile saved for the caller.",
    },
}

PROFILE_UPDATE_RESPONSES: dict[int | str, dict[str, object]] = {
    **AUTH_RESPONSES,
    **BODY_LIMIT_RESPONSE,
}


@router.get("/profile", response_model=ProfileResponse, responses=PROFILE_RESPONSES)
def get_profile(
    user_id: Annotated[str, Depends(require_user_id)],
) -> ProfileResponse:
    """Return the caller's profile.

    Args:
        user_id: The verified owner id.

    Returns:
        The stored profile.

    Raises:
        HTTPException: 404 when the caller has no profile.
    """
    profile = access.get_owned_profile(get_repo(), user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return ProfileResponse(**profile.to_dict())


@router.put(
    "/profile", response_model=ProfileResponse, responses=PROFILE_UPDATE_RESPONSES
)
def update_profile(
    payload: ProfileUpdate,
    user_id: Annotated[str, Depends(require_user_id)],
) -> ProfileResponse:
    """Validate and store the caller's profile.

    Args:
        payload: The incoming profile fields.
        user_id: The verified owner id.

    Returns:
        The stored profile.

    Raises:
        HTTPException: 422 when a field is out of range.
    """
    try:
        profile = normalize_profile({**payload.model_dump(), "user_id": user_id})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved = get_repo().save_profile(profile)
    return ProfileResponse(**saved.to_dict())
