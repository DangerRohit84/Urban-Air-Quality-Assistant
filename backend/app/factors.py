"""Cited emission, exposure and cost factors per activity.

Every value is approximate and carries a source note; the table is the single
source of truth for the impact engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Factor:
    """One activity's weekly emissions, exposure and cost characteristics."""

    key: str
    category: str
    co2e_per_week_kg: float
    exposure_reduction_pct: float
    cost_delta_inr_month: float
    source: str
    approximate: bool


# key, category, kg CO2e per unit, exposure reduction %, INR/month, source
_ROWS: tuple[tuple[str, str, float, float, float, str], ...] = (
    ("commute.walk", "commute", 0.0, 5.0, 0.0, "WHO active travel; approx."),
    ("commute.cycle", "commute", 0.0, 8.0, -200.0, "CPCB transport; approx."),
    ("commute.two_wheeler", "commute", 0.09, 2.0, -300.0, "CPCB transport; approx."),
    ("commute.car", "commute", 0.20, 0.0, 0.0, "MoEFCC petrol CO2; approx."),
    ("commute.bus", "commute", 0.05, 3.0, -400.0, "CPCB public transport; approx."),
    ("commute.metro", "commute", 0.03, 3.5, -350.0, "Metro energy mix; approx."),
    ("commute.train", "commute", 0.04, 3.0, -300.0, "Rail energy mix; approx."),
    ("commute.work_from_home", "commute", 0.0, 10.0, -800.0, "Avoided commute; approx."),
    ("cooking.lpg", "cooking", 1.2, 1.0, 0.0, "CPCB LPG combustion; approx."),
    ("cooking.png", "cooking", 1.1, 1.2, -100.0, "PNG combustion; approx."),
    ("cooking.electric", "cooking", 0.8, 2.0, 200.0, "Grid electricity; approx."),
    ("cooking.biogas", "cooking", 0.6, 3.0, -150.0, "Biogas combustion; approx."),
    ("cooking.wood", "cooking", 2.5, 0.0, -50.0, "Biofuel combustion; approx."),
    ("cooking.kerosene", "cooking", 2.0, -1.0, -100.0, "Kerosene combustion; approx."),
    ("cooking.coal", "cooking", 3.0, -2.0, -80.0, "Coal combustion; approx."),
    ("heating.none", "heating", 0.0, 0.0, 0.0, "Baseline; approx."),
    ("heating.electric_heater", "heating", 1.2, -1.0, 800.0, "Grid electricity; approx."),
    ("heating.gas_heater", "heating", 1.5, -0.5, 600.0, "Gas combustion; approx."),
    ("heating.blowers", "heating", 0.8, -0.5, 500.0, "Grid electricity; approx."),
    ("heating.solar", "heating", 0.2, 1.0, 300.0, "Solar thermal; approx."),
    ("heating.wood_burner", "heating", 3.0, -3.0, -100.0, "Biofuel combustion; approx."),
    ("waste.burn", "waste", 1.0, -5.0, 0.0, "Open burning; approx."),
    ("waste.compost", "waste", 0.1, 2.0, -50.0, "Composting; approx."),
)

FACTORS: dict[str, Factor] = {
    key: Factor(key, category, co2e, exposure, cost, source, True)
    for key, category, co2e, exposure, cost, source in _ROWS
}
