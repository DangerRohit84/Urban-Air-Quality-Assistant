"""Application composition root."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.body_limit import UPLOAD_HEADROOM, BodyLimitMiddleware
from backend.app.config import settings
from backend.app.errors import install_error_handlers
from backend.app.middleware import rate_limit_middleware, security_headers
from backend.app.openapi_docs import DocumentedApp
from backend.app.rate_limiter import SlidingWindowRateLimiter
from backend.app.routes import api_router

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
PUBLIC_STYLES = FRONTEND_DIR / "styles.css"
PUBLIC_JS_DIR = FRONTEND_DIR / "js"

DESCRIPTION = """\
Offline-first personal air-quality assistant for Indian cities.

It combines a saved CPCB AQI context with a household profile to build
low-emission routines and indoor-air guidance, answers questions with
citations from a seeded corpus and the caller's own documents, and can
optionally blend a live provider reading when `AQI_API_KEY` is configured.
Without provider keys every endpoint still works from local data.
"""

OPENAPI_TAGS = [
    {"name": "system", "description": "Health and service metadata."},
    {"name": "auth", "description": "Register, log in, log out, current user."},
    {"name": "air", "description": "Saved AQI context and optional live reading."},
    {"name": "plans", "description": "Low-emission routines for the saved context."},
    {"name": "profile", "description": "Household and exposure personalization."},
    {"name": "documents", "description": "Inline text and PDF knowledge sources."},
    {"name": "ask", "description": "Grounded answers with citations and refusals."},
    {"name": "export", "description": "Download documents as Markdown or JSON."},
]


def _configure_logging() -> None:
    """Apply ``LOG_LEVEL`` to the root logger and the security logger."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("security").setLevel(level)


def _mount_public_assets(app: FastAPI) -> None:
    """Expose only the public frontend assets under ``/static``.

    The whole ``frontend`` directory must never be mounted: it also holds
    package manifests, lint/format configuration and dotfiles that are build
    tooling, not runtime assets. Only the fixed stylesheet and the ``js``
    directory are served; ``StaticFiles`` confines lookups to that directory,
    so a traversal request cannot reach the tooling files.

    Args:
        app: The application to extend.
    """
    if PUBLIC_STYLES.is_file():

        @app.get("/static/styles.css", include_in_schema=False)
        def styles() -> FileResponse:
            """Return the public stylesheet."""
            return FileResponse(PUBLIC_STYLES, media_type="text/css")

    if PUBLIC_JS_DIR.is_dir():
        app.mount(
            "/static/js",
            StaticFiles(directory=str(PUBLIC_JS_DIR)),
            name="static-js",
        )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        The configured application instance.
    """
    _configure_logging()
    app = DocumentedApp(
        title="Urban Air Quality Assistant",
        version="0.1.0",
        description=DESCRIPTION,
        contact={
            "name": "Rohit",
            "url": "https://github.com/DangerRohit84/Urban-Air-Quality-Assistant",
        },
        license_info={"name": "MIT"},
        openapi_tags=OPENAPI_TAGS,
    )
    app.state.rate_limiter = SlidingWindowRateLimiter(
        limit=settings.rate_limit_per_min,
        max_buckets=settings.max_rate_buckets,
    )
    # Starlette treats the last-added middleware as outermost. Security
    # headers wrap CORS, which wraps the rate limiter, so a 429 keeps both
    # its CORS origin and the security header set.
    app.add_middleware(
        BodyLimitMiddleware,
        upload_limit=settings.max_upload_bytes + UPLOAD_HEADROOM,
    )
    app.middleware("http")(rate_limit_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(security_headers)
    install_error_handlers(app)
    app.include_router(api_router)
    _mount_public_assets(app)
    return app


app = create_app()
