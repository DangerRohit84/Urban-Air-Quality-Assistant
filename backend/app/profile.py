"""Profile defaults, enum validation and normalization."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.models import Profile

CLIMATE_ZONES = frozenset({"north", "south", "east", "west", "central", "hilly"})
COMMUTE_MODES = frozenset(
    {
        "walk",
        "cycle",
        "two_wheeler",
        "car",
        "bus",
        "metro",
        "train",
        "work_from_home",
    }
)
COOKING_FUELS = frozenset(
    {"lpg", "png", "electric", "biogas", "wood", "kerosene", "coal"}
)
HEATING_TYPES = frozenset(
    {
        "none",
        "electric_heater",
        "gas_heater",
        "blowers",
        "solar",
        "wood_burner",
    }
)
BUDGET_LEVELS = frozenset({"low", "medium", "high"})

DEFAULT_PROFILE = Profile(
    user_id="",
    city="",
    climate_zone="north",
    children=False,
    elderly=False,
    respiratory=False,
    commute_mode="bus",
    commute_km=0.0,
    cooking_fuel="lpg",
    heating_type="none",
    budget_level="medium",
    updated_at="",
)


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601.

    Returns:
        The formatted timestamp.
    """
    return datetime.now(UTC).isoformat()


def _enum(value: object, allowed: frozenset[str], label: str) -> str:
    """Validate ``value`` against ``allowed``.

    Args:
        value: The candidate value.
        allowed: The permitted strings.
        label: The field name used in the error message.

    Returns:
        The validated value.

    Raises:
        ValueError: When the value is not in the allowed set.
    """
    text = str(value).strip().lower()
    if text not in allowed:
        raise ValueError(f"{label} must be one of {sorted(allowed)}")
    return text


def normalize_profile(data: dict[str, object]) -> Profile:
    """Validate a raw mapping and return a ``Profile``.

    Args:
        data: The raw profile fields, including an optional ``user_id``.

    Returns:
        The validated profile.

    Raises:
        ValueError: When any field is missing or out of range.
    """
    city = str(data.get("city", "")).strip()
    if not 1 <= len(city) <= 80:
        raise ValueError("city must be 1-80 characters")
    commute_km = float(str(data.get("commute_km", 0.0)))
    if not 0 <= commute_km <= 200:
        raise ValueError("commute_km must be between 0 and 200")
    updated_at = str(data.get("updated_at") or _now())
    return Profile(
        user_id=str(data.get("user_id", "")),
        city=city,
        climate_zone=_enum(data.get("climate_zone"), CLIMATE_ZONES, "climate_zone"),
        children=bool(data.get("children", False)),
        elderly=bool(data.get("elderly", False)),
        respiratory=bool(data.get("respiratory", False)),
        commute_mode=_enum(data.get("commute_mode"), COMMUTE_MODES, "commute_mode"),
        commute_km=commute_km,
        cooking_fuel=_enum(data.get("cooking_fuel"), COOKING_FUELS, "cooking_fuel"),
        heating_type=_enum(data.get("heating_type"), HEATING_TYPES, "heating_type"),
        budget_level=_enum(data.get("budget_level"), BUDGET_LEVELS, "budget_level"),
        updated_at=updated_at,
    )
