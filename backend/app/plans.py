"""Plan orchestration, ranking and the plans payload."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.alternatives import build_alternatives
from backend.app.hacks import build_hacks
from backend.app.models import AqiContext, Profile, Recommendation
from backend.app.routines import build_routines

PROFILE_NOTE = "Set your profile to personalize these recommendations."
AREAS: tuple[str, ...] = ("routines", "hacks", "alternatives")


@dataclass(slots=True)
class PlansPayload:
    """The three recommendation sections plus a profile note."""

    routines: list[Recommendation]
    hacks: list[Recommendation]
    alternatives: list[Recommendation]
    profile_note: str


def rank(items: list[Recommendation], profile: Profile) -> list[Recommendation]:
    """Sort recommendations by impact, strongest first.

    Args:
        items: The recommendations to sort.
        profile: The user's profile (reserved for future tie-breaks).

    Returns:
        A new sorted list.
    """
    return sorted(
        items,
        key=lambda item: (
            -item.impact.co2e_kg_week,
            -item.impact.exposure_reduction_pct,
            item.key,
        ),
    )


def build_plans(
    profile: Profile, context: AqiContext | None, hits: list[dict]
) -> PlansPayload:
    """Build the full personalized plans payload.

    Args:
        profile: The user's profile.
        context: The optional air-quality context.
        hits: The retrieved documents.

    Returns:
        The ranked routines, hacks and alternatives.
    """
    note = "" if profile.city else PROFILE_NOTE
    return PlansPayload(
        routines=rank(build_routines(profile, context, hits), profile),
        hacks=rank(build_hacks(profile, context, hits), profile),
        alternatives=rank(build_alternatives(profile, context, hits), profile),
        profile_note=note,
    )
