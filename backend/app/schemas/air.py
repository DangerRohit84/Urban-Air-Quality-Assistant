"""Air quality request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.app.aqi import CPCB_BANDS

BAND_NAMES = frozenset(band.name for band in CPCB_BANDS)
SEASONS = frozenset({"winter", "summer", "monsoon", "post_monsoon"})


class AirContextIn(BaseModel):
    """Payload accepted by ``POST /air/context``."""

    city: str
    band: str
    season: str
    value: int | None = None
    pm25: float | None = None
    pm10: float | None = None

    @field_validator("band")
    @classmethod
    def _validate_band(cls, value: str) -> str:
        """Reject unknown band names.

        Args:
            value: The supplied band.

        Returns:
            The validated band.

        Raises:
            ValueError: When the band is not a CPCB band name.
        """
        if value not in BAND_NAMES:
            raise ValueError("unknown band")
        return value

    @field_validator("season")
    @classmethod
    def _validate_season(cls, value: str) -> str:
        """Reject unknown seasons.

        Args:
            value: The supplied season.

        Returns:
            The validated season.

        Raises:
            ValueError: When the season is not recognised.
        """
        if value not in SEASONS:
            raise ValueError("unknown season")
        return value


class AirContextResponse(BaseModel):
    """Payload returned by ``POST /air/context``."""

    user_id: str
    city: str
    band: str
    value: int | None
    pm25: float | None
    pm10: float | None
    season: str
    observed_at: str
    source: str


class AirLiveResponse(BaseModel):
    """Payload returned by ``GET /air``."""

    city: str
    source: str
    band: str
    value: int | None
    pm25: float | None
    pm10: float | None
    fallback: str
