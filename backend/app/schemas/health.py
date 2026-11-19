"""Health response schema."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Payload returned by ``GET /health``."""

    status: str
    provider: str
    cache: dict[str, int]
    store: dict[str, int]
    uptime_seconds: float
