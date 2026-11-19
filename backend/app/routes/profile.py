"""Profile routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app import access
from backend.app.auth.dependencies import require_user_id
from backend.app.schemas.profile import ProfileResponse
from backend.app.storage.store import get_repo

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
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
