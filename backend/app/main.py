"""Application composition root."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.errors import install_error_handlers
from backend.app.middleware import SlidingWindowRateLimiter, security_headers
from backend.app.routes import api_router

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        The configured application instance.
    """
    app = FastAPI(title="Urban Air Quality Assistant", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.rate_limiter = SlidingWindowRateLimiter(
        limit=settings.rate_limit_per_min,
        max_buckets=settings.max_rate_buckets,
    )
    app.middleware("http")(security_headers)
    install_error_handlers(app)
    app.include_router(api_router)
    if FRONTEND_DIR.is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=str(FRONTEND_DIR)),
            name="static",
        )
    return app


app = create_app()
