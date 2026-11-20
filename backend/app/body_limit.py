"""Path-aware ASGI request-body size limiting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException

JSON_BODY_LIMIT = 1024 * 1024
UPLOAD_HEADROOM = 1024 * 1024
UPLOAD_PATH = "/documents/upload"
TOO_LARGE = "request body too large"

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


async def _send_too_large(send: Send) -> None:
    """Send the generic 413 response without echoing request data."""
    body = b'{"detail": "request body too large"}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _content_length(scope: Scope) -> int | None:
    """Return the declared ``Content-Length``, if any."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodyLimitMiddleware:
    """Reject request bodies above a path-specific byte limit."""

    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        json_limit: int = JSON_BODY_LIMIT,
        upload_limit: int | None = None,
    ) -> None:
        """Store the next application and the two body limits.

        Args:
            app: The next ASGI application in the stack.
            json_limit: Maximum bytes for ordinary routes.
            upload_limit: Maximum bytes for the PDF upload route.
        """
        self.app = app
        self.json_limit = json_limit
        self.upload_limit = json_limit if upload_limit is None else upload_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce the body limit for HTTP requests.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = (
            self.upload_limit
            if scope.get("path") == UPLOAD_PATH
            else self.json_limit
        )
        declared = _content_length(scope)
        if declared is not None and declared > limit:
            await _send_too_large(send)
            return

        total = 0
        response_started = False

        async def limited_receive() -> Message:
            """Count body chunks and reject once the limit is crossed."""
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    raise HTTPException(status_code=413, detail=TOO_LARGE)
            return message

        async def limited_send(message: Message) -> None:
            """Track whether the response has started."""
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except HTTPException as exc:
            if exc.status_code != 413 or response_started:
                raise
            await _send_too_large(send)
