"""Thread-safe sliding-window rate limiter with LRU bucket eviction."""

from __future__ import annotations

import threading
from collections import OrderedDict

WINDOW_SECONDS = 60.0


def client_key(
    forwarded_for: str | None,
    peer_host: str | None,
    trust_proxy: bool,
) -> str:
    """Resolve the bucket key, honoring the first proxy hop when trusted.

    Args:
        forwarded_for: The raw ``X-Forwarded-For`` header, if present.
        peer_host: The direct socket peer address, if present.
        trust_proxy: Whether proxy-supplied forwarding headers are trusted.

    Returns:
        The client key used for rate-limit bucketing.
    """
    if trust_proxy and forwarded_for:
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    return peer_host or "unknown"


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window limiter with LRU bucket eviction."""

    def __init__(
        self,
        limit: int,
        window: float = WINDOW_SECONDS,
        max_buckets: int = 10000,
    ) -> None:
        """Store the budget and eviction bound.

        Args:
            limit: Maximum requests allowed per window.
            window: Window length in seconds.
            max_buckets: Maximum number of client buckets to retain.
        """
        self.limit = limit
        self.window = window
        self.max_buckets = max_buckets
        self._hits: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, now: float) -> tuple[bool, int, int]:
        """Record a hit and report whether it is allowed.

        Args:
            key: The client bucket key.
            now: The current timestamp in seconds.

        Returns:
            A ``(allowed, remaining, reset_seconds)`` triple.
        """
        with self._lock:
            timestamps = [
                stamp for stamp in self._hits.get(key, []) if now - stamp < self.window
            ]
            if len(timestamps) >= self.limit:
                self._hits[key] = timestamps
                self._hits.move_to_end(key)
                return False, 0, self._reset_for(timestamps, now)
            timestamps.append(now)
            self._hits[key] = timestamps
            self._hits.move_to_end(key)
            self._evict()
            return True, self.limit - len(timestamps), self._reset_for(timestamps, now)

    def _reset_for(self, timestamps: list[float], now: float) -> int:
        """Return the seconds until the oldest hit leaves the window.

        Args:
            timestamps: The recorded hits.
            now: The current timestamp.

        Returns:
            The number of seconds until the bucket resets.
        """
        if not timestamps:
            return int(self.window)
        return max(1, int(self.window - (now - timestamps[0])))

    def _evict(self) -> None:
        """Drop the least recently used buckets beyond ``max_buckets``."""
        while len(self._hits) > self.max_buckets:
            self._hits.popitem(last=False)
