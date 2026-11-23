"""Shared OpenAPI response declarations for API routes."""

from __future__ import annotations

from typing import Any

from backend.app.body_limit import JSON_BODY_LIMIT
from backend.app.schemas.errors import ErrorResponse

INTERNAL_ERROR: dict[int | str, dict[str, Any]] = {
    500: {
        "model": ErrorResponse,
        "description": "Unhandled server error; the body never leaks internals.",
    },
}

RATE_LIMIT_RESPONSE: dict[int | str, dict[str, Any]] = {
    429: {
        "model": ErrorResponse,
        "description": "Per-client rate limit exceeded; honour Retry-After.",
    },
}

BODY_LIMIT_RESPONSE: dict[int | str, dict[str, Any]] = {
    413: {
        "model": ErrorResponse,
        "description": (
            f"Request body exceeds the {JSON_BODY_LIMIT}-byte JSON body limit."
        ),
    },
}

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "model": ErrorResponse,
        "description": "Missing, malformed, revoked or unknown bearer token.",
    },
    **RATE_LIMIT_RESPONSE,
    **INTERNAL_ERROR,
}
