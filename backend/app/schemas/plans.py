"""Plans response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.models import Recommendation
from backend.app.plans import PlansPayload

_EXAMPLE_IMPACT = {
    "co2e_kg_week": 15.0,
    "exposure_reduction_pct": 8.0,
    "cost_delta_inr_month": -300.0,
}
_EXAMPLE_RECOMMENDATION = {
    "key": "commute.bus",
    "area": "routines",
    "title": "Switch to the bus",
    "detail": "Replace the car commute with the bus on weekdays.",
    "action_key": "commute.bus",
    "baseline_key": "commute.car",
    "impact": _EXAMPLE_IMPACT,
    "citations": ["seed-001"],
    "approximate": True,
}


class ImpactOut(BaseModel):
    """Impact projection returned to clients."""

    co2e_kg_week: float = Field(
        description="Estimated CO2e saved per week (kg).", examples=[15.0]
    )
    exposure_reduction_pct: float = Field(
        description="Estimated exposure reduction (percent).", examples=[8.0]
    )
    cost_delta_inr_month: float = Field(
        description="Monthly cost change in INR; negative saves money.",
        examples=[-300.0],
    )


class RecommendationOut(BaseModel):
    """A single recommendation returned to clients."""

    key: str = Field(description="Stable recommendation key.", examples=["commute.bus"])
    area: str = Field(
        description="Section: routines, hacks or alternatives.", examples=["routines"]
    )
    title: str = Field(
        description="Short action title.", examples=["Switch to the bus"]
    )
    detail: str = Field(
        description="One-line explanation of the action.",
        examples=["Replace the car commute with the bus on weekdays."],
    )
    action_key: str = Field(
        description="Action identifier used by clients.", examples=["commute.bus"]
    )
    baseline_key: str = Field(
        description="Baseline habit being replaced.", examples=["commute.car"]
    )
    impact: ImpactOut = Field(
        description="Projected impact of the action.", examples=[_EXAMPLE_IMPACT]
    )
    citations: list[str] = Field(
        description="Supporting corpus document ids.", examples=[["seed-001"]]
    )
    approximate: bool = Field(
        description="True when numbers are estimates, not exact.", examples=[True]
    )


class PlansResponse(BaseModel):
    """The plans payload returned to clients."""

    routines: list[RecommendationOut] = Field(
        description="Daily routines for the saved context.",
        examples=[[_EXAMPLE_RECOMMENDATION]],
    )
    hacks: list[RecommendationOut] = Field(
        description="Indoor-air hacks.", examples=[[_EXAMPLE_RECOMMENDATION]]
    )
    alternatives: list[RecommendationOut] = Field(
        description="Lower-emission alternatives.",
        examples=[[_EXAMPLE_RECOMMENDATION]],
    )
    profile_note: str = Field(
        description="Personalization note; empty when set.",
        examples=["Set your profile for personalized numbers."],
    )


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
