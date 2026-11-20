"""Profile request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """Payload accepted by ``PUT /profile``."""

    city: str = Field(min_length=1, max_length=80)
    climate_zone: str = Field(max_length=40)
    children: bool = False
    elderly: bool = False
    respiratory: bool = False
    commute_mode: str = Field(max_length=40)
    commute_km: float = Field(ge=0, le=200)
    cooking_fuel: str = Field(max_length=40)
    heating_type: str = Field(max_length=40)
    budget_level: str = Field(max_length=40)


class ProfileResponse(BaseModel):
    """Payload returned by ``GET /profile``."""

    user_id: str
    city: str
    climate_zone: str
    children: bool
    elderly: bool
    respiratory: bool
    commute_mode: str
    commute_km: float
    cooking_fuel: str
    heating_type: str
    budget_level: str
    updated_at: str
