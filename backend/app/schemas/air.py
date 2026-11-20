"""Air quality request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.app.aqi import CPCB_BANDS

BAND_NAMES = frozenset(band.name for band in CPCB_BANDS)
SEASONS = frozenset({"winter", "summer", "monsoon", "post_monsoon"})


class AirContextIn(BaseModel):
    """Payload accepted by ``POST /air/context``."""

    city: str = Field(min_length=1, max_length=80)
    band: str = Field(max_length=40)
    season: str = Field(max_length=40)
    value: int | None = Field(default=None, ge=0, le=1000)
    pm25: float | None = Field(default=None, ge=0, le=2000)
    pm10: float | None = Field(default=None, ge=0, le=2000)

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
    native_index: int | None = None
