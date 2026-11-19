"""SQLite schema migrations."""

from __future__ import annotations

import sqlite3

from backend.app.storage.schema import SCHEMA_V1


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending migrations and return the resulting ``user_version``.

    Args:
        conn: The open SQLite connection.

    Returns:
        The ``PRAGMA user_version`` value after migrating.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version < 1:
        conn.executescript(SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
    conn.commit()
    return int(conn.execute("PRAGMA user_version").fetchone()[0])
