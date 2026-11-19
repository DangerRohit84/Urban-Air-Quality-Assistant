"""Sustainable alternatives to common household activities."""

from __future__ import annotations

from backend.app.factors import FACTORS
from backend.app.impact import compute_impact
from backend.app.models import AqiContext, Profile, Recommendation

COOKING_KEYS: tuple[str, ...] = (
    "cooking.biogas",
    "cooking.electric",
    "cooking.png",
    "cooking.lpg",
    "cooking.kerosene",
    "cooking.wood",
    "cooking.coal",
)


def _citations(hits: list[dict]) -> list[str]:
    """Return up to two citation ids from ``hits``.

    Args:
        hits: The retrieved documents.

    Returns:
        The citation ids, or a fallback source note.
    """
    return [str(hit["id"]) for hit in hits[:2]] or ["CPCB"]


def build_alternatives(
    profile: Profile, context: AqiContext | None, hits: list[dict]
) -> list[Recommendation]:
    """Build cooking-fuel alternative recommendations.

    Args:
        profile: The user's profile.
        context: The optional air-quality context.
        hits: The retrieved documents.

    Returns:
        Up to three recommendations.
    """
    baseline = f"cooking.{profile.cooking_fuel}"
    if baseline not in FACTORS:
        baseline = "cooking.lpg"
    candidates = [key for key in COOKING_KEYS if key != baseline]
    candidates.sort(key=lambda key: FACTORS[key].co2e_per_week_kg)
    citations = _citations(hits)
    current = profile.cooking_fuel.replace("_", " ")
    recommendations: list[Recommendation] = []
    for key in candidates[:3]:
        factor = FACTORS[key]
        label = key.split(".", 1)[1].replace("_", " ")
        recommendations.append(
            Recommendation(
                key=key,
                area="alternatives",
                title=f"Switch to {label}",
                detail=(
                    f"Switch from {current} to {label} to cut cooking "
                    "emissions and indoor smoke."
                ),
                action_key=key,
                baseline_key=baseline,
                impact=compute_impact(profile, key, baseline, context),
                citations=list(citations),
                approximate=factor.approximate,
            )
        )
    return recommendations
