"""Minimal JSON-over-HTTP helper for remote LLM providers."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

TIMEOUT_SECONDS = 10.0


def post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    """POST ``payload`` as JSON and decode a JSON-object response.

    Args:
        url: The endpoint URL.
        payload: The JSON request body.
        headers: Extra request headers.

    Returns:
        The decoded response object.

    Raises:
        OSError: When the request fails or times out.
        ValueError: When the response is not a JSON object.
    """
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - caller passes a fixed https URL
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(  # noqa: S310 - caller passes a fixed https URL
        request, timeout=TIMEOUT_SECONDS
    ) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("LLM response is not a JSON object")
    return decoded
