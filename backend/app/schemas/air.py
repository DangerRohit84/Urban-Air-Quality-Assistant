"""Air quality request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.app.aqi import CPCB_BANDS

BAND_NAMES = frozenset(band.name for band in CPCB_BANDS)
SEASONS = frozenset({"winter", "summer", "monsoon", "post_monsoon"})


class AirContextIn(BaseModel):
    """Payload accepted by ``POST /air/context``."""

    city: str = Field(
        min_length=1,
        max_length=80,
        description="Known Indian city name, e.g. `Delhi`.",
        examples=["Delhi"],
    )
    band: str = Field(
        max_length=40,
        description="CPCB band name, e.g. `poor`.",
        examples=["poor"],
    )
    season: str = Field(
        max_length=40,
        description="One of winter, summer, monsoon, post_monsoon.",
        examples=["winter"],
    )
    value: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Optional CPCB AQI value (0-1000).",
        examples=[250],
    )
    pm25: float | None = Field(
        default=None,
        ge=0,
        le=2000,
        description="Optional PM2.5 concentration in ug/m3.",
        examples=[120.0],
    )
    pm10: float | None = Field(
        default=None,
        ge=0,
        le=2000,
        description="Optional PM10 concentration in ug/m3.",
        examples=[180.0],
    )

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

    user_id: str = Field(description="Owner user id.", examples=["user-0001"])
    city: str = Field(description="Resolved city name.", examples=["Delhi"])
    band: str = Field(description="Saved CPCB band name.", examples=["poor"])
    value: int | None = Field(
        description="Saved AQI value, when supplied.", examples=[250]
    )
    pm25: float | None = Field(
        description="Saved PM2.5, when supplied.", examples=[120.0]
    )
    pm10: float | None = Field(
        description="Saved PM10, when supplied.", examples=[180.0]
    )
    season: str = Field(description="Saved season.", examples=["winter"])
    observed_at: str = Field(
        description="ISO-8601 save timestamp (UTC).",
        examples=["2026-01-02T03:04:05+00:00"],
    )
    source: str = Field(description="Context origin, e.g. `user`.", examples=["user"])


class AirLiveResponse(BaseModel):
    """Payload returned by ``GET /air``."""

    city: str = Field(description="Resolved city name.", examples=["Delhi"])
    source: str = Field(
        description="`live`, `offline` or `not_configured`.",
        examples=["offline"],
    )
    band: str = Field(
        description="CPCB band name; empty when unknown.",
        examples=["poor"],
    )
    value: int | None = Field(description="AQI value, when known.", examples=[250])
    pm25: float | None = Field(
        description="PM2.5 in ug/m3, when known.", examples=[120.0]
    )
    pm10: float | None = Field(
        description="PM10 in ug/m3, when known.", examples=[180.0]
    )
    fallback: str = Field(
        description="Human-readable fallback explanation.",
        examples=["live AQI not configured"],
    )
    native_index: int | None = Field(
        default=None,
        description="Provider-native index, when reported.",
        examples=[4],
    )
