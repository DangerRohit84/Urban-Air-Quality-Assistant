"""Pure impact arithmetic over the cited factor table.

``co2e_kg_week`` is expressed as a reduction relative to the baseline, so a
positive value is always a benefit and ranking descending surfaces the
strongest recommendation first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.app.factors import FACTORS, Factor
from backend.app.models import AqiContext, Profile

if TYPE_CHECKING:
    from backend.app.models import Recommendation

_EXPOSURE_MULTIPLIERS: dict[str, float] = {
    "Good": 0.5,
    "Satisfactory": 0.75,
    "Moderately Polluted": 1.0,
    "Poor": 1.25,
    "Very Poor": 1.5,
    "Severe": 2.0,
}


@dataclass(slots=True)
class Impact:
    """The quantified effect of one recommendation."""

    co2e_kg_week: float
    exposure_reduction_pct: float
    cost_delta_inr_month: float


def _factor(key: str) -> Factor:
    """Return the factor for ``key``.

    Args:
        key: The factor key.

    Returns:
        The factor.

    Raises:
        ValueError: When the key is unknown.
    """
    factor = FACTORS.get(key)
    if factor is None:
        raise ValueError(f"unknown factor key: {key}")
    return factor


def _weekly_multiplier(key: str, profile: Profile) -> float:
    """Return the scaling factor that turns a unit rate into a week.

    Args:
        key: The factor key.
        profile: The user's profile.

    Returns:
        The multiplier for the key's category.
    """
    if key.startswith("commute."):
        return profile.commute_km * 2 * 5
    if key.startswith(("cooking.", "heating.")):
        return 7.0
    return 1.0


def exposure_multiplier(context: AqiContext | None) -> float:
    """Return the exposure multiplier for the context band.

    Args:
        context: The stored air-quality context, or None.

    Returns:
        The multiplier, defaulting to 1.0.
    """
    if context is None:
        return 1.0
    return _EXPOSURE_MULTIPLIERS.get(context.band, 1.0)


def compute_impact(
    profile: Profile,
    action_key: str,
    baseline_key: str,
    context: AqiContext | None = None,
) -> Impact:
    """Compute the weekly impact of ``action_key`` over ``baseline_key``.

    Args:
        profile: The user's profile.
        action_key: The recommended activity.
        baseline_key: The activity being replaced.
        context: The optional air-quality context.

    Returns:
        The impact, with ``co2e_kg_week`` positive for a reduction.

    Raises:
        ValueError: When either key is unknown.
    """
    action = _factor(action_key)
    baseline = _factor(baseline_key)
    multiplier = _weekly_multiplier(action_key, profile)
    return Impact(
        co2e_kg_week=round(
            (baseline.co2e_per_week_kg - action.co2e_per_week_kg) * multiplier,
            6,
        ),
        exposure_reduction_pct=round(
            (action.exposure_reduction_pct - baseline.exposure_reduction_pct)
            * exposure_multiplier(context),
            6,
        ),
        cost_delta_inr_month=round(
            action.cost_delta_inr_month - baseline.cost_delta_inr_month,
            6,
        ),
    )


def impact_for_recommendation(
    profile: Profile,
    recommendation: Recommendation,
    context: AqiContext | None,
) -> Impact:
    """Compute the impact recorded on a recommendation.

    Args:
        profile: The user's profile.
        recommendation: The recommendation carrying the factor keys.
        context: The optional air-quality context.

    Returns:
        The impact for the recommendation's action and baseline.
    """
    return compute_impact(
        profile,
        recommendation.action_key,
        recommendation.baseline_key,
        context,
    )
