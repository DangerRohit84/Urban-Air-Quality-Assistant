"""Air quality routes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app import cities
from backend.app.air.openweather import OpenWeatherProvider
from backend.app.air.provider import LiveAqiReading
from backend.app.auth.dependencies import require_user_id
from backend.app.config import settings
from backend.app.models import AqiContext
from backend.app.schemas.air import (
    AirContextIn,
    AirContextResponse,
    AirLiveResponse,
)
from backend.app.storage.store import get_repo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["air"])

NOT_CONFIGURED = "not_configured"
OFFLINE = "offline"


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601."""
    return datetime.now(UTC).isoformat()


def get_live_reading(city: cities.City) -> LiveAqiReading | None:
    """Fetch a live reading, or None when unconfigured or failed."""
    if not settings.aqi_api_key:
        return None
    try:
        return OpenWeatherProvider(settings.aqi_api_key).fetch(city)
    except Exception as exc:  # noqa: BLE001 - any failure degrades offline
        logger.warning(
            "live AQI provider failed (%s); serving the fallback",
            type(exc).__name__,
        )
        return None


def _fallback(city: cities.City, user_id: str, source: str) -> AirLiveResponse:
    """Build the saved-context or empty fallback response."""
    ctx = get_repo().get_aqi_context(user_id)
    if ctx is not None and ctx.city.strip().casefold() == city.name.casefold():
        note = (
            "live AQI provider unavailable"
            if source == OFFLINE
            else "live AQI not configured"
        )
        return AirLiveResponse(
            city=city.name,
            source=source,
            band=ctx.band,
            value=ctx.value,
            pm25=ctx.pm25,
            pm10=ctx.pm10,
            fallback=f"{note}; showing your saved band",
        )
    fallback = (
        "live AQI provider unavailable; POST /air/context with your band"
        if source == OFFLINE
        else "set AQI_API_KEY or POST /air/context with your band"
    )
    return AirLiveResponse(
        city=city.name,
        source=source,
        band="",
        value=None,
        pm25=None,
        pm10=None,
        fallback=fallback,
    )


@router.post("/air/context", response_model=AirContextResponse)
def save_context(
    payload: AirContextIn,
    user_id: Annotated[str, Depends(require_user_id)],
) -> AirContextResponse:
    """Store the caller's air-quality context."""
    city = cities.resolve_city(payload.city)
    if city is None:
        raise HTTPException(status_code=422, detail="unknown city")
    ctx = AqiContext(
        user_id=user_id,
        city=city.name,
        band=payload.band,
        value=payload.value,
        pm25=payload.pm25,
        pm10=payload.pm10,
        season=payload.season,
        observed_at=_now(),
        source="user",
    )
    saved = get_repo().save_aqi_context(ctx)
    return AirContextResponse(**saved.to_dict())


@router.get("/air", response_model=AirLiveResponse)
def get_air(
    q: str,
    user_id: Annotated[str, Depends(require_user_id)],
) -> AirLiveResponse:
    """Return live AQI, else the caller's saved context."""
    city = cities.resolve_city(q)
    if city is None:
        raise HTTPException(status_code=404, detail="unknown city")
    live = get_live_reading(city)
    if live is not None:
        return AirLiveResponse(
            city=city.name,
            source="live",
            band=live.band.name,
            value=live.value,
            pm25=live.pm25,
            pm10=live.pm10,
            fallback="",
            native_index=live.native_index,
        )
    source = OFFLINE if settings.aqi_api_key else NOT_CONFIGURED
    return _fallback(city, user_id, source)
