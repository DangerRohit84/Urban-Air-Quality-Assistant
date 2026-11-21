"""Token revocation stores for the memory and SQLite repositories."""

from __future__ import annotations

import time
from typing import Any

from backend.app.storage.sqlite_base import SQLiteBackend


class MemoryRevocationsMixin:
    """Revoked-token methods for the in-memory repository.

    The host class provides ``_lock`` and the ``_revoked`` mapping.
    """

    _lock: Any
    _revoked: dict[str, int]

    def revoke_token(self, jti: str, expires_ns: int) -> None:
        """Record ``jti`` as revoked until ``expires_ns``.

        Args:
            jti: The unique token id.
            expires_ns: The token expiry in nanoseconds since the epoch.
        """
        now_ns = time.time_ns()
        with self._lock:
            self._revoked[jti] = expires_ns
            self._revoked = {
                key: exp for key, exp in self._revoked.items() if exp > now_ns
            }

    def is_token_revoked(self, jti: str) -> bool:
        """Return True when ``jti`` is revoked and unexpired.

        Args:
            jti: The unique token id.

        Returns:
            True when the token must be rejected.
        """
        with self._lock:
            expires = self._revoked.get(jti)
            if expires is None:
                return False
            if expires <= time.time_ns():
                del self._revoked[jti]
                return False
            return True

    def count_revoked_tokens(self) -> int:
        """Return the number of stored revocation records.

        Returns:
            The record count.
        """
        with self._lock:
            return len(self._revoked)


class SQLiteRevocations(SQLiteBackend):
    """SQLite backend extended with the revoked-token methods."""

    def revoke_token(self, jti: str, expires_ns: int) -> None:
        """Record ``jti`` as revoked until ``expires_ns``.

        Args:
            jti: The unique token id.
            expires_ns: The token expiry in nanoseconds since the epoch.
        """
        self.run(
            "INSERT INTO revoked_tokens (jti, expires_at) VALUES (?, ?) "
            "ON CONFLICT(jti) DO UPDATE SET expires_at = excluded.expires_at",
            (jti, expires_ns),
        )
        self.run(
            "DELETE FROM revoked_tokens WHERE expires_at <= ?",
            (time.time_ns(),),
        )

    def is_token_revoked(self, jti: str) -> bool:
        """Return True when ``jti`` is revoked and unexpired.

        Args:
            jti: The unique token id.

        Returns:
            True when the token must be rejected.
        """
        row = self.one("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,))
        return row is not None

    def count_revoked_tokens(self) -> int:
        """Return the number of stored revocation records.

        Returns:
            The record count.
        """
        return self.count("SELECT COUNT(*) FROM revoked_tokens")
