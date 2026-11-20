"""Security headers and rate-limit enforcement middleware."""

from __future__ import annotations

import time

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from backend.app.config import settings
from backend.app.rate_limiter import client_key

RETRY_AFTER = "60"
EXEMPT_PATHS = frozenset({"/health"})

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cache-Control": "no-store",
}


def rate_limit(request: Request) -> None:
    """Enforce the per-client rate limit for the current request.

    Args:
        request: The incoming request.

    Raises:
        HTTPException: 429 when the client has exhausted its window.
    """
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return
    if request.url.path in EXEMPT_PATHS:
        request.state.rate_limit_remaining = limiter.limit
        request.state.rate_limit_reset = 0
        return
    key = client_key(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
        settings.trust_proxy,
    )
    allowed, remaining, reset = limiter.check(key, time.time())
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded",
            headers={"Retry-After": RETRY_AFTER},
        )


def _attach_headers(
    resp: Response,
    request: Request,
    limited: bool = False,
) -> Response:
    """Attach security and rate-limit headers to ``resp``.

    Args:
        resp: The response to decorate.
        request: The request that produced the response.
        limited: Whether the response is a rate-limit rejection.

    Returns:
        The decorated response.
    """
    for name, value in _SECURITY_HEADERS.items():
        resp.headers[name] = value
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        resp.headers["X-RateLimit-Limit"] = str(limiter.limit)
        remaining = getattr(request.state, "rate_limit_remaining", limiter.limit)
        reset = getattr(request.state, "rate_limit_reset", 0)
        resp.headers["X-RateLimit-Remaining"] = str(remaining)
        resp.headers["X-RateLimit-Reset"] = str(reset)
    if limited:
        resp.headers["Retry-After"] = RETRY_AFTER
    return resp


async def rate_limit_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """ASGI middleware enforcing the rate limit inside the CORS layer.

    Args:
        request: The incoming request.
        call_next: The next middleware/handler in the stack.

    Returns:
        The handler response, or a decorated 429 rejection.
    """
    try:
        rate_limit(request)
    except HTTPException as exc:
        rejected = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
        return _attach_headers(rejected, request, limited=True)
    return await call_next(request)


async def security_headers(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """ASGI middleware adding security headers to every response.

    Args:
        request: The incoming request.
        call_next: The next middleware/handler in the stack.

    Returns:
        The decorated response.
    """
    try:
        response: Response = await call_next(request)
    except Exception:  # noqa: BLE001 - the middleware must never leak crashes
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    return _attach_headers(response, request)
