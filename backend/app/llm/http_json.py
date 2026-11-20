"""Minimal JSON-over-HTTP helper for remote LLM providers."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 1_048_576
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so credentials stay on the configured origin."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        """Return ``None`` so urllib raises instead of following a redirect."""


def _opener() -> urllib.request.OpenerDirector:
    """Build an opener with TLS verification and redirects disabled."""
    context = ssl.create_default_context()
    return urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=context)
    )


def _validate_url(url: str) -> None:
    """Reject non-HTTP(S) endpoints before opening a connection."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.hostname:
        raise ValueError("LLM endpoint must be an http(s) URL")


def _declared_too_large(headers: Any) -> bool:
    """Return whether ``Content-Length`` exceeds the response cap."""
    declared = headers.get("Content-Length") if headers is not None else None
    try:
        return declared is not None and int(declared) > MAX_RESPONSE_BYTES
    except (TypeError, ValueError):
        return False


def post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    """POST ``payload`` as JSON and decode a bounded JSON-object response.

    Args:
        url: The endpoint URL.
        payload: The JSON request body.
        headers: Extra request headers.

    Returns:
        The decoded response object.

    Raises:
        OSError: When the request fails, times out or is redirected.
        ValueError: When the URL is unsupported, the body is too large or the
            response is not a JSON object.
    """
    _validate_url(url)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - scheme validated above
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        response = _opener().open(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise
    with response:
        if _declared_too_large(getattr(response, "headers", None)):
            raise ValueError("LLM response too large")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("LLM response too large")
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("LLM response is not a JSON object")
    return decoded
