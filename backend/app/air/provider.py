"""Live AQI provider protocol and reading type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.app.aqi import Band
from backend.app.cities import City


@dataclass(frozen=True, slots=True)
class LiveAqiReading:
    """One live air-quality reading."""

    band: Band
    value: int | None
    pm25: float | None
    pm10: float | None
    source: str = "live"
    native_index: int | None = None


class LiveAqiProvider(Protocol):
    """Port for live air-quality providers."""

    def fetch(self, city: City) -> LiveAqiReading:
        """Fetch a reading for ``city``."""
        ...
