"""CPCB AQI band table and conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Band:
    """One CPCB air-quality band."""

    name: str
    low: int
    high: int
    color: str
    advice: str


CPCB_BANDS: tuple[Band, ...] = (
    Band("Good", 0, 50, "#009933", "Enjoy outdoor activity."),
    Band(
        "Satisfactory",
        51,
        100,
        "#99cc33",
        "Sensitive groups should pace outdoor exertion.",
    ),
    Band(
        "Moderately Polluted",
        101,
        200,
        "#ffcc00",
        "Reduce prolonged outdoor exertion.",
    ),
    Band(
        "Poor",
        201,
        300,
        "#ff6600",
        "Avoid outdoor exertion for children and the elderly.",
    ),
    Band("Very Poor", 301, 400, "#cc0033", "Stay indoors and use a purifier."),
    Band("Severe", 401, 500, "#7e0023", "Avoid all outdoor activity."),
)

_PM25_BREAKS: tuple[tuple[float, Band], ...] = (
    (30.0, CPCB_BANDS[0]),
    (60.0, CPCB_BANDS[1]),
    (90.0, CPCB_BANDS[2]),
    (120.0, CPCB_BANDS[3]),
    (250.0, CPCB_BANDS[4]),
)

_INDEX_BANDS: dict[int, Band] = {
    1: CPCB_BANDS[0],
    2: CPCB_BANDS[1],
    3: CPCB_BANDS[2],
    4: CPCB_BANDS[3],
    5: CPCB_BANDS[4],
}


def band_for_value(value: int) -> Band:
    """Return the CPCB band for an AQI value.

    Args:
        value: The AQI value; values outside 0-500 are clamped.

    Returns:
        The matching band.
    """
    if value < 0:
        return CPCB_BANDS[0]
    for band in CPCB_BANDS:
        if band.low <= value <= band.high:
            return band
    return CPCB_BANDS[-1]


def band_from_pm25(pm25: float) -> Band:
    """Return the CPCB band for a 24-hour PM2.5 concentration.

    Args:
        pm25: The micrograms-per-cubic-metre reading.

    Returns:
        The matching band.
    """
    if pm25 < 0:
        return CPCB_BANDS[0]
    for limit, band in _PM25_BREAKS:
        if pm25 <= limit:
            return band
    return CPCB_BANDS[-1]


def band_from_openweather_index(index: int) -> Band:
    """Convert an OpenWeather 1-5 index into a CPCB band.

    Args:
        index: The native OpenWeather air-quality index.

    Returns:
        The matching band.

    Raises:
        ValueError: When the index is outside 1-5.
    """
    try:
        return _INDEX_BANDS[index]
    except KeyError as exc:
        raise ValueError("openweather index must be 1-5") from exc
