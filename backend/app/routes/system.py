"""System routes: the public health check and the frontend shell."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.app.metrics import health_snapshot
from backend.app.routes.common import RATE_LIMIT_RESPONSE
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["system"])

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
FRONTEND_MISSING = {
    "service": "Urban Air Quality Assistant",
    "docs": "/docs",
    "health": "/health",
    "note": (
        "Frontend assets are not installed; "
        "run from source or the Docker image for the UI."
    ),
}


@router.get("/", responses=RATE_LIMIT_RESPONSE)
def index() -> Response:
    """Serve the frontend shell, or API pointers when it is not installed.

    A wheel-only install has no ``frontend/`` directory, so the shell cannot be
    served; the API itself stays usable and this route describes where to find
    the docs and health probe instead of failing with a 500.

    Returns:
        The ``index.html`` document, or a JSON description of the API.
    """
    index_html = FRONTEND_DIR / "index.html"
    if index_html.is_file():
        return FileResponse(index_html)
    return JSONResponse(status_code=200, content=FRONTEND_MISSING)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return the service health snapshot.

    Returns:
        The provider, cache, store and uptime snapshot.
    """
    return HealthResponse.model_validate({"status": "ok", **health_snapshot()})
