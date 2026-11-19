"""Plans response schemas."""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.models import Recommendation
from backend.app.plans import PlansPayload


class ImpactOut(BaseModel):
    """Impact projection returned to clients."""

    co2e_kg_week: float
    exposure_reduction_pct: float
    cost_delta_inr_month: float


class RecommendationOut(BaseModel):
    """A single recommendation returned to clients."""

    key: str
    area: str
    title: str
    detail: str
    action_key: str
    baseline_key: str
    impact: ImpactOut
    citations: list[str]
    approximate: bool


class PlansResponse(BaseModel):
    """The plans payload returned to clients."""

    routines: list[RecommendationOut]
    hacks: list[RecommendationOut]
    alternatives: list[RecommendationOut]
    profile_note: str


def to_out(recommendation: Recommendation) -> RecommendationOut:
    """Convert a domain recommendation to its response schema.

    Args:
        recommendation: The domain recommendation.

    Returns:
        The response model.
    """
    return RecommendationOut(**recommendation.to_dict())


def to_response(payload: PlansPayload) -> PlansResponse:
    """Convert a plans payload to its response schema.

    Args:
        payload: The domain payload.

    Returns:
        The response model.
    """
    return PlansResponse(
        routines=[to_out(item) for item in payload.routines],
        hacks=[to_out(item) for item in payload.hacks],
        alternatives=[to_out(item) for item in payload.alternatives],
        profile_note=payload.profile_note,
    )
