"""Indoor air-quality hack recommendations."""

from __future__ import annotations

from backend.app.factors import FACTORS
from backend.app.impact import compute_impact
from backend.app.models import AqiContext, Profile, Recommendation

_HACKS: tuple[tuple[str, str, str, str], ...] = (
    (
        "waste.compost",
        "waste.burn",
        "Compost green waste",
        "Compost garden waste instead of burning it to keep smoke out of "
        "your street.",
    ),
    (
        "heating.none",
        "heating.wood_burner",
        "Avoid wood burners",
        "Avoid wood-burning heaters and chimneys indoors; they add fine "
        "particles to every room.",
    ),
    (
        "cooking.electric",
        "cooking.wood",
        "Upgrade cooking",
        "Prefer electric, biogas or LPG cooking over wood and coal to cut "
        "kitchen smoke.",
    ),
)


def _citations(hits: list[dict]) -> list[str]:
    """Return up to two citation ids from ``hits``.

    Args:
        hits: The retrieved documents.

    Returns:
        The citation ids, or a fallback source note.
    """
    return [str(hit["id"]) for hit in hits[:2]] or ["CPCB"]


def build_hacks(
    profile: Profile, context: AqiContext | None, hits: list[dict]
) -> list[Recommendation]:
    """Build indoor air-quality recommendations.

    Args:
        profile: The user's profile.
        context: The optional air-quality context.
        hits: The retrieved documents.

    Returns:
        Up to three recommendations.
    """
    citations = _citations(hits)
    suffix = ""
    if profile.children or profile.respiratory:
        suffix = (
            " Children and people with respiratory conditions benefit most "
            "from cleaner indoor air."
        )
    recommendations: list[Recommendation] = []
    for action, baseline, title, detail in _HACKS:
        factor = FACTORS[action]
        recommendations.append(
            Recommendation(
                key=action,
                area="hacks",
                title=title,
                detail=detail + suffix,
                action_key=action,
                baseline_key=baseline,
                impact=compute_impact(profile, action, baseline, context),
                citations=list(citations),
                approximate=factor.approximate,
            )
        )
    return recommendations
