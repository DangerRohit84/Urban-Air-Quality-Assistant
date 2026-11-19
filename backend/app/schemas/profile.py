"""Profile request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    """Payload accepted by ``PUT /profile``."""

    city: str
    climate_zone: str
    children: bool = False
    elderly: bool = False
    respiratory: bool = False
    commute_mode: str
    commute_km: float
    cooking_fuel: str
    heating_type: str
    budget_level: str


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
