"""Tests for CPCB band conversion and city resolution."""

from __future__ import annotations

import pytest

from backend.app.aqi import (
    CPCB_BANDS,
    band_for_value,
    band_from_openweather_index,
    band_from_pm25,
)
from backend.app.cities import City, resolve_city


@pytest.mark.parametrize(
    ("value", "name"),
    [
        (0, "Good"),
        (50, "Good"),
        (51, "Satisfactory"),
        (100, "Satisfactory"),
        (101, "Moderately Polluted"),
        (200, "Moderately Polluted"),
        (201, "Poor"),
        (300, "Poor"),
        (301, "Very Poor"),
        (400, "Very Poor"),
        (401, "Severe"),
        (500, "Severe"),
        (501, "Severe"),
        (-5, "Good"),
    ],
)
def test_band_for_value_boundaries(value: int, name: str) -> None:
    """Every CPCB boundary maps to the documented band."""
    assert band_for_value(value).name == name


def test_cpcb_bands_are_ordered() -> None:
    """The band table is complete and ordered."""
    assert [band.name for band in CPCB_BANDS] == [
        "Good",
        "Satisfactory",
        "Moderately Polluted",
        "Poor",
        "Very Poor",
        "Severe",
    ]
    assert all(band.color and band.advice for band in CPCB_BANDS)


@pytest.mark.parametrize(
    ("pm25", "name"),
    [
        (30, "Good"),
        (31, "Satisfactory"),
        (60, "Satisfactory"),
        (61, "Moderately Polluted"),
        (90, "Moderately Polluted"),
        (91, "Poor"),
        (120, "Poor"),
        (121, "Very Poor"),
        (250, "Very Poor"),
        (251, "Severe"),
    ],
)
def test_band_from_pm25_boundaries(pm25: float, name: str) -> None:
    """The 24-hour PM2.5 breakpoints follow CPCB."""
    assert band_from_pm25(pm25).name == name


@pytest.mark.parametrize(
    ("index", "name"),
    [
        (1, "Good"),
        (2, "Satisfactory"),
        (3, "Moderately Polluted"),
        (4, "Poor"),
        (5, "Very Poor"),
    ],
)
def test_band_from_openweather_index(index: int, name: str) -> None:
    """The OpenWeather 1-5 index maps onto CPCB bands."""
    assert band_from_openweather_index(index).name == name


@pytest.mark.parametrize("index", [0, 6, -1])
def test_band_from_openweather_index_invalid(index: int) -> None:
    """Out-of-range indices raise."""
    with pytest.raises(ValueError):
        band_from_openweather_index(index)


def test_resolve_city_is_case_and_space_insensitive() -> None:
    """City lookup normalizes case and surrounding space."""
    assert resolve_city("delhi") == City("Delhi", 28.6139, 77.209)
    assert resolve_city("Delhi ") == City("Delhi", 28.6139, 77.209)


def test_resolve_city_unknown_is_none() -> None:
    """An unknown city resolves to None."""
    assert resolve_city("Atlantis") is None


def test_city_table_covers_major_indian_cities() -> None:
    """The coordinates table holds every required city."""
    required = {
        "Delhi",
        "Mumbai",
        "Bengaluru",
        "Chennai",
        "Kolkata",
        "Hyderabad",
        "Pune",
        "Ahmedabad",
        "Jaipur",
        "Lucknow",
        "Chandigarh",
        "Patna",
        "Bhopal",
        "Indore",
        "Guwahati",
        "Srinagar",
        "Shimla",
        "Kochi",
        "Thiruvananthapuram",
        "Bhubaneswar",
    }
    for name in required:
        assert resolve_city(name) is not None, name
