"""Plans route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.auth.dependencies import load_profile_or_default, require_user_id
from backend.app.plans import AREAS, PlansPayload, build_plans
from backend.app.retrieval import search
from backend.app.routes.common import AUTH_RESPONSES
from backend.app.schemas.plans import PlansResponse, to_response
from backend.app.storage.store import get_repo

router = APIRouter(tags=["plans"])


def payload_for_user(user_id: str) -> PlansPayload:
    """Build the plans payload for ``user_id``.

    Args:
        user_id: The verified owner id.

    Returns:
        The personalized payload.
    """
    repo = get_repo()
    profile = load_profile_or_default(repo, user_id)
    context = repo.get_aqi_context(user_id)
    query = f"{profile.city} air quality".strip()
    hits = search(query, owner_id=user_id)
    return build_plans(profile, context, hits)


@router.get("/plans", response_model=PlansResponse, responses=AUTH_RESPONSES)
def get_plans(
    user_id: Annotated[str, Depends(require_user_id)],
    area: str | None = None,
) -> PlansResponse:
    """Return the caller's personalized plans.

    Args:
        user_id: The verified owner id.
        area: An optional section filter.

    Returns:
        The plans payload, filtered when ``area`` is given.

    Raises:
        HTTPException: 422 when the area is unknown.
    """
    if area is not None and area not in AREAS:
        raise HTTPException(status_code=422, detail="unknown area")
    payload = payload_for_user(user_id)
    if area is not None:
        payload.routines = payload.routines if area == "routines" else []
        payload.hacks = payload.hacks if area == "hacks" else []
        payload.alternatives = payload.alternatives if area == "alternatives" else []
    return to_response(payload)
