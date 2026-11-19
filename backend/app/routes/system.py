"""System routes: the public health check."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.metrics import health_snapshot
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the service health snapshot.

    Returns:
        The provider, cache, store and uptime snapshot.
    """
    return HealthResponse.model_validate({"status": "ok", **health_snapshot()})
