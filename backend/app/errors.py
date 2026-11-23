"""Application-wide exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.security_log import log_event


def log_unhandled_error(request: Request, exc: Exception) -> None:
    """Emit one metadata-only ``unhandled_error`` event per request.

    The middleware and the exception handler can both see the same failure,
    so the flag on ``request.state`` keeps the event single-shot. Only the
    path, method and exception class are recorded: never the message, body,
    token or document text.

    Args:
        request: The request that failed.
        exc: The exception that escaped the route.
    """
    if getattr(request.state, "unhandled_error_logged", False):
        return
    request.state.unhandled_error_logged = True
    log_event(
        "unhandled_error",
        path=request.url.path,
        method=request.method,
        error=type(exc).__name__,
    )


def install_error_handlers(app: FastAPI) -> None:
    """Install the application-wide exception handlers.

    Args:
        app: The FastAPI application to configure.
    """

    @app.exception_handler(ValueError)
    async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Render ``ValueError`` as a 400 with its message."""
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc) or "bad request"},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Render 422 errors without echoing the submitted input."""
        detail = [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Pass ``HTTPException`` through with its status code and detail."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Render any unhandled exception as a bare 500."""
        log_unhandled_error(request, exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
