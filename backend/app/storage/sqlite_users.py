"""SQLite user-account methods for the repository."""

from __future__ import annotations

import sqlite3

from backend.app.models import User
from backend.app.storage.sqlite_base import SQLiteBackend
from backend.app.storage.sqlite_rows import row_to_user
from backend.app.storage.sqlite_values import new_id, now_iso


class SQLiteUsers(SQLiteBackend):
    """SQLite backend extended with user-account methods."""

    def create_user(self, email: str, password_hash: str) -> User:
        """Insert a user, rejecting a duplicate email.

        Raises:
            ValueError: When ``email`` is already registered.
        """
        user = User(new_id(), email, password_hash, now_iso())
        try:
            self.run(
                "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user.id, user.email, user.password_hash, user.created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("email already registered") from exc
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Return the user with ``email``, or None."""
        row = self.one("SELECT * FROM users WHERE email = ?", (email,))
        return row_to_user(row) if row else None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Return the user with ``user_id``, or None."""
        row = self.one("SELECT * FROM users WHERE id = ?", (user_id,))
        return row_to_user(row) if row else None

    def update_user_password_hash(self, user_id: str, password_hash: str) -> None:
        """Replace the password hash for ``user_id`` when it exists."""
        self.run(
            "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
        )

    def count_users(self) -> int:
        """Return the total number of users."""
        return self.count("SELECT COUNT(*) FROM users")
