"""Profile request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """Payload accepted by ``PUT /profile``."""

    city: str = Field(
        min_length=1,
        max_length=80,
        description="Known Indian city name, e.g. `Delhi`.",
        examples=["Delhi"],
    )
    climate_zone: str = Field(
        max_length=40,
        description="Climate zone, e.g. `north`.",
        examples=["north"],
    )
    children: bool = Field(
        default=False,
        description="Children in the household.",
        examples=[True],
    )
    elderly: bool = Field(
        default=False,
        description="Elderly in the household.",
        examples=[False],
    )
    respiratory: bool = Field(
        default=False,
        description="Any respiratory condition in the household.",
        examples=[True],
    )
    commute_mode: str = Field(
        max_length=40,
        description="Primary commute mode, e.g. `car`, `metro`, `walk`.",
        examples=["car"],
    )
    commute_km: float = Field(
        ge=0,
        le=200,
        description="One-way commute distance in km.",
        examples=[10.0],
    )
    cooking_fuel: str = Field(
        max_length=40,
        description="Cooking fuel, e.g. `lpg`, `wood`, `electric`.",
        examples=["wood"],
    )
    heating_type: str = Field(
        max_length=40,
        description="Heating type, e.g. `none`, `electric`, `wood`.",
        examples=["none"],
    )
    budget_level: str = Field(
        max_length=40,
        description="Budget level: `low`, `medium` or `high`.",
        examples=["low"],
    )


class ProfileResponse(BaseModel):
    """Payload returned by ``GET /profile``."""

    user_id: str = Field(description="Owner user id.", examples=["user-0001"])
    city: str = Field(description="Saved city name.", examples=["Delhi"])
    climate_zone: str = Field(description="Saved climate zone.", examples=["north"])
    children: bool = Field(description="Children in the household.", examples=[True])
    elderly: bool = Field(description="Elderly in the household.", examples=[False])
    respiratory: bool = Field(
        description="Respiratory condition in the household.", examples=[True]
    )
    commute_mode: str = Field(description="Saved commute mode.", examples=["car"])
    commute_km: float = Field(
        description="Saved one-way commute distance (km).", examples=[10.0]
    )
    cooking_fuel: str = Field(description="Saved cooking fuel.", examples=["wood"])
    heating_type: str = Field(description="Saved heating type.", examples=["none"])
    budget_level: str = Field(description="Saved budget level.", examples=["low"])
    updated_at: str = Field(
        description="ISO-8601 last update timestamp (UTC).",
        examples=["2026-01-02T03:04:05+00:00"],
    )
