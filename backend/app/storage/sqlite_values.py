"""Identifier and timestamp helpers shared by the SQLite stores."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601."""
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    """Return a fresh hex identifier."""
    return uuid.uuid4().hex
