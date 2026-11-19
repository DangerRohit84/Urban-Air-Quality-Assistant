"""System routes: the public health check and the frontend shell."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.app.metrics import health_snapshot
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


@router.get("/")
def index() -> FileResponse:
    """Serve the frontend shell.

    Returns:
        The ``index.html`` document.
    """
    return FileResponse(FRONTEND_DIR / "index.html")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the service health snapshot.

    Returns:
        The provider, cache, store and uptime snapshot.
    """
    return HealthResponse.model_validate({"status": "ok", **health_snapshot()})
