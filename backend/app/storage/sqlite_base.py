"""SQLite connection factory and thread-safe SQL primitives."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import cast


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a WAL-mode connection with foreign keys and a busy timeout.

    Args:
        db_path: Path of the SQLite database file.

    Returns:
        The configured connection.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        timeout=5.0,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


class SQLiteBackend:
    """Thread-safe connection plus the SQL primitives shared by stores."""

    def __init__(self, db_path: Path) -> None:
        """Open the connection and create the lock.

        Args:
            db_path: Path of the SQLite database file.
        """
        self._conn = connect(db_path)
        self._lock = threading.RLock()

    def one(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Row | None:
        """Return the first matching row, or None.

        Args:
            sql: The query text.
            params: The bound parameters.

        Returns:
            The first row, or None.
        """
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return cast("sqlite3.Row | None", row)

    def all(self, sql: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        """Return every matching row.

        Args:
            sql: The query text.
            params: The bound parameters.

        Returns:
            The matching rows.
        """
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def count(self, sql: str, params: tuple[object, ...] = ()) -> int:
        """Return a ``COUNT(*)`` result.

        Args:
            sql: The query text.
            params: The bound parameters.

        Returns:
            The count.
        """
        row = self.one(sql, params)
        return int(row[0]) if row else 0

    def run(self, sql: str, values: tuple[object, ...]) -> None:
        """Run a single write statement and commit.

        Args:
            sql: The statement text.
            values: The bound parameters.
        """
        with self._lock:
            self._conn.execute(sql, values)
            self._conn.commit()

    def delete(self, sql: str, values: tuple[object, ...]) -> int:
        """Run a DELETE and return the affected row count.

        Args:
            sql: The statement text.
            values: The bound parameters.

        Returns:
            The number of deleted rows.
        """
        with self._lock:
            cursor = self._conn.execute(sql, values)
            self._conn.commit()
            return cursor.rowcount

    def upsert(
        self,
        table: str,
        columns: tuple[str, ...],
        values: tuple[object, ...],
    ) -> None:
        """Insert or update a row by its primary key.

        Args:
            table: The target table (an internal constant).
            columns: The column list; the first is the conflict key.
            values: The bound parameters.
        """
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns[1:])
        self.run(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "  # noqa: S608 - identifiers are internal constants
            f"ON CONFLICT({columns[0]}) DO UPDATE SET {updates}",
            values,
        )

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()
