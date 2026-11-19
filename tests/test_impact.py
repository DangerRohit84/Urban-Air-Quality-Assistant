"""Tests for the cited factor table and exact impact arithmetic."""

from __future__ import annotations

import pytest

from backend.app.factors import FACTORS, Factor
from backend.app.impact import (
    Impact,
    compute_impact,
    exposure_multiplier,
    impact_for_recommendation,
)
from backend.app.models import AqiContext, Profile, Recommendation

REQUIRED_KEYS = (
    "commute.walk",
    "commute.cycle",
    "commute.two_wheeler",
    "commute.car",
    "commute.bus",
    "commute.metro",
    "commute.train",
    "commute.work_from_home",
    "cooking.lpg",
    "cooking.png",
    "cooking.electric",
    "cooking.biogas",
    "cooking.wood",
    "cooking.kerosene",
    "cooking.coal",
    "heating.none",
    "heating.electric_heater",
    "heating.gas_heater",
    "heating.blowers",
    "heating.solar",
    "heating.wood_burner",
    "waste.burn",
    "waste.compost",
)


def _profile(**overrides: object) -> Profile:
    """Build a profile with sensible defaults plus ``overrides``."""
    fields: dict[str, object] = {
        "user_id": "u1",
        "city": "Delhi",
        "climate_zone": "north",
        "children": False,
        "elderly": False,
        "respiratory": False,
        "commute_mode": "car",
        "commute_km": 10.0,
        "cooking_fuel": "wood",
        "heating_type": "none",
        "budget_level": "low",
        "updated_at": "t",
    }
    fields.update(overrides)
    return Profile(**fields)  # type: ignore[arg-type]


def _context(band: str) -> AqiContext:
    """Build an AQI context with ``band``."""
    return AqiContext(
        user_id="u1",
        city="Delhi",
        band=band,
        value=None,
        pm25=None,
        pm10=None,
        season="winter",
        observed_at="t",
        source="user",
    )


def test_factor_table_is_complete() -> None:
    """Every documented factor key is present."""
    for key in REQUIRED_KEYS:
        assert key in FACTORS, key
        assert isinstance(FACTORS[key], Factor)


def test_every_factor_is_cited_and_approximate() -> None:
    """Each factor carries a source note and the approximate flag."""
    for factor in FACTORS.values():
        assert factor.source.strip()
        assert factor.approximate is True


def test_commute_arithmetic_exact() -> None:
    """Switching a 10 km car commute to bus saves 15 kg/week."""
    impact = compute_impact(_profile(), "commute.bus", "commute.car")

    assert impact.co2e_kg_week == 15.0


def test_cooking_arithmetic_exact() -> None:
    """Switching from wood to LPG reduces 9.1 kg/week."""
    impact = compute_impact(_profile(), "cooking.lpg", "cooking.wood")

    assert impact.co2e_kg_week == 9.1


def test_cost_and_exposure_match_table_exactly() -> None:
    """Cost and exposure deltas come straight from the factor table."""
    impact = compute_impact(_profile(), "commute.bus", "commute.car")
    action = FACTORS["commute.bus"]
    baseline = FACTORS["commute.car"]

    assert impact.cost_delta_inr_month == (
        action.cost_delta_inr_month - baseline.cost_delta_inr_month
    )
    assert impact.exposure_reduction_pct == (
        action.exposure_reduction_pct - baseline.exposure_reduction_pct
    )


def test_unknown_action_key_raises() -> None:
    """An unknown action key is rejected."""
    with pytest.raises(ValueError):
        compute_impact(_profile(), "commute.rocket", "commute.car")


def test_unknown_baseline_key_raises() -> None:
    """An unknown baseline key is rejected."""
    with pytest.raises(ValueError):
        compute_impact(_profile(), "commute.bus", "commute.rocket")


@pytest.mark.parametrize(
    ("band", "multiplier"),
    [
        ("Good", 0.5),
        ("Satisfactory", 0.75),
        ("Moderately Polluted", 1.0),
        ("Poor", 1.25),
        ("Very Poor", 1.5),
        ("Severe", 2.0),
    ],
)
def test_exposure_multiplier_bands(band: str, multiplier: float) -> None:
    """The exposure multiplier follows the CPCB band table."""
    assert exposure_multiplier(_context(band)) == multiplier


def test_exposure_multiplier_default_is_one() -> None:
    """A missing context or band leaves the multiplier at 1.0."""
    assert exposure_multiplier(None) == 1.0
    assert exposure_multiplier(_context("Unknown")) == 1.0


def test_impact_for_recommendation_uses_keys() -> None:
    """The recommendation's action/baseline keys drive the impact."""
    recommendation = Recommendation(
        key="commute.bus",
        area="routines",
        title="Take the bus",
        detail="Replace car commutes with the bus.",
        action_key="commute.bus",
        baseline_key="commute.car",
        impact=Impact(0.0, 0.0, 0.0),
        citations=["seed-001"],
        approximate=True,
    )

    impact = impact_for_recommendation(_profile(), recommendation, None)

    assert impact.co2e_kg_week == 15.0


def test_context_scales_exposure_reduction() -> None:
    """Poor air magnifies the exposure benefit of a cleaner choice."""
    plain = compute_impact(_profile(), "commute.bus", "commute.car")
    poor = compute_impact(
        _profile(), "commute.bus", "commute.car", _context("Poor")
    )

    assert poor.exposure_reduction_pct == plain.exposure_reduction_pct * 1.25
    assert poor.co2e_kg_week == plain.co2e_kg_week
