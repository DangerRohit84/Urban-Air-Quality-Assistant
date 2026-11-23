"""Structured security event logging.

Every event is a single JSON line on the ``security`` logger so a log
collector can index fields without parsing prose. Callers pass only
non-secret context: never tokens, passwords, API keys, raw bodies or
extracted document text. ``default=str`` keeps the emitter total so a stray
non-JSON value cannot raise inside an error path.
"""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "security"

_logger = logging.getLogger(LOGGER_NAME)


def log_event(event: str, **fields: Any) -> None:
    """Emit one structured security event at warning level.

    Args:
        event: The event name, for example ``auth_failure``.
        **fields: Non-secret context such as the route path and a reason code.
    """
    payload = {"event": event, **fields}
    _logger.warning(json.dumps(payload, sort_keys=True, default=str))
