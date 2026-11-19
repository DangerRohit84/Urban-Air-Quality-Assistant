"""Low-emission daily routine recommendations."""

from __future__ import annotations

from backend.app.factors import FACTORS
from backend.app.impact import compute_impact
from backend.app.models import AqiContext, Profile, Recommendation

COMMUTE_KEYS: tuple[str, ...] = (
    "commute.walk",
    "commute.cycle",
    "commute.metro",
    "commute.train",
    "commute.bus",
    "commute.work_from_home",
    "commute.two_wheeler",
)

_TITLES: dict[str, str] = {
    "commute.walk": "Walk short trips",
    "commute.cycle": "Cycle to work",
    "commute.metro": "Take the metro",
    "commute.train": "Take the train",
    "commute.bus": "Take the bus",
    "commute.work_from_home": "Work from home",
    "commute.two_wheeler": "Ride a two-wheeler",
}


def _citations(hits: list[dict]) -> list[str]:
    """Return up to two citation ids from ``hits``.

    Args:
        hits: The retrieved documents.

    Returns:
        The citation ids, or a fallback source note.
    """
    return [str(hit["id"]) for hit in hits[:2]] or ["CPCB"]


def build_routines(
    profile: Profile, context: AqiContext | None, hits: list[dict]
) -> list[Recommendation]:
    """Build commute-focused routine recommendations.

    Args:
        profile: The user's profile.
        context: The optional air-quality context.
        hits: The retrieved documents.

    Returns:
        Up to three ranked recommendations.
    """
    baseline = f"commute.{profile.commute_mode}"
    if baseline not in FACTORS:
        baseline = "commute.bus"
    candidates = [key for key in COMMUTE_KEYS if key != baseline]
    candidates.sort(key=lambda key: FACTORS[key].co2e_per_week_kg)
    citations = _citations(hits)
    current = profile.commute_mode.replace("_", " ")
    recommendations: list[Recommendation] = []
    for key in candidates[:3]:
        factor = FACTORS[key]
        label = key.split(".", 1)[1].replace("_", " ")
        recommendations.append(
            Recommendation(
                key=key,
                area="routines",
                title=_TITLES.get(key, label.title()),
                detail=(
                    f"Replace {current} commutes with {label} to cut "
                    "weekly emissions."
                ),
                action_key=key,
                baseline_key=baseline,
                impact=compute_impact(profile, key, baseline, context),
                citations=list(citations),
                approximate=factor.approximate,
            )
        )
    return recommendations
