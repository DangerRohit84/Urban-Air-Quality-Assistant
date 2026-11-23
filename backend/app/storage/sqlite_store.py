"""SQLite implementation of the Repository protocol."""

from __future__ import annotations

from pathlib import Path

from backend.app.storage.migrations import apply_migrations
from backend.app.storage.revocations import SQLiteRevocations
from backend.app.storage.sqlite_content import SQLiteContent
from backend.app.storage.sqlite_users import SQLiteUsers


class SQLiteRepo(SQLiteUsers, SQLiteContent, SQLiteRevocations):
    """A SQLite implementation of the Repository protocol."""

    def __init__(self, db_path: Path) -> None:
        """Open the database and apply migrations."""
        super().__init__(db_path)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Apply pending schema migrations."""
        with self._lock:
            apply_migrations(self._conn)
