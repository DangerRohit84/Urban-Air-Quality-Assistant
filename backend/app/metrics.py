"""Health metrics snapshot used by ``GET /health``."""

from __future__ import annotations

import importlib
import time

from backend.app.config import settings

_STARTED = time.monotonic()


def _cache_stats() -> dict[str, int]:
    """Return retrieval cache statistics, or zeros before retrieval exists.

    Returns:
        A ``hits``/``misses``/``size`` mapping.
    """
    try:
        module = importlib.import_module("backend.app.retrieval")
    except ImportError:
        return {"hits": 0, "misses": 0, "size": 0}
    getter = getattr(module, "get_cache_stats", None)
    if getter is None:
        return {"hits": 0, "misses": 0, "size": 0}
    return dict(getter())


def _store_counts() -> dict[str, int]:
    """Return store row counts, or zeros before storage exists.

    Returns:
        A ``users``/``profiles``/``documents`` mapping.
    """
    try:
        module = importlib.import_module("backend.app.storage.store")
    except ImportError:
        return {"users": 0, "profiles": 0, "documents": 0}
    getter = getattr(module, "store_counts", None)
    if getter is None:
        return {"users": 0, "profiles": 0, "documents": 0}
    return dict(getter())


def health_snapshot() -> dict[str, object]:
    """Return the provider, cache, store and uptime snapshot.

    Returns:
        A mapping with ``provider``, ``cache``, ``store`` and
        ``uptime_seconds`` keys.
    """
    return {
        "provider": settings.llm_provider,
        "cache": _cache_stats(),
        "store": _store_counts(),
        "uptime_seconds": round(time.monotonic() - _STARTED, 3),
    }
