"""SQLite implementation of the Repository protocol."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from backend.app.models import AqiContext, Document, Profile, User
from backend.app.storage.migrations import apply_migrations
from backend.app.storage.sqlite_base import SQLiteBackend
from backend.app.storage.sqlite_rows import (
    row_to_context,
    row_to_document,
    row_to_profile,
    row_to_user,
)

_PROFILE_COLUMNS = ("user_id", "city", "climate_zone", "children", "elderly", "respiratory", "commute_mode", "commute_km", "cooking_fuel", "heating_type", "budget_level", "updated_at")
_CONTEXT_COLUMNS = ("user_id", "city", "band", "value", "pm25", "pm10", "season", "observed_at", "source")


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601."""
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    """Return a fresh hex identifier."""
    return uuid.uuid4().hex


class SQLiteRepo(SQLiteBackend):
    """A SQLite implementation of the Repository protocol."""

    def __init__(self, db_path: Path) -> None:
        """Open the database and apply migrations."""
        super().__init__(db_path)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Apply pending schema migrations."""
        with self._lock:
            apply_migrations(self._conn)

    def create_user(self, email: str, password_hash: str) -> User:
        """Insert a user, rejecting a duplicate email.

        Raises:
            ValueError: When ``email`` is already registered.
        """
        user = User(_new_id(), email, password_hash, _now())
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
        self.run("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))

    def save_profile(self, profile: Profile) -> Profile:
        """Insert or update the profile for ``profile.user_id``."""
        self.upsert(
            "profiles",
            _PROFILE_COLUMNS,
            (profile.user_id, profile.city, profile.climate_zone, int(profile.children), int(profile.elderly), int(profile.respiratory), profile.commute_mode, profile.commute_km, profile.cooking_fuel, profile.heating_type, profile.budget_level, profile.updated_at),
        )
        return profile

    def get_profile(self, user_id: str) -> Profile | None:
        """Return the profile for ``user_id``, or None."""
        row = self.one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        return row_to_profile(row) if row else None

    def save_aqi_context(self, ctx: AqiContext) -> AqiContext:
        """Insert or update the AQI context for ``ctx.user_id``."""
        self.upsert(
            "aqi_context",
            _CONTEXT_COLUMNS,
            (ctx.user_id, ctx.city, ctx.band, ctx.value, ctx.pm25, ctx.pm10, ctx.season, ctx.observed_at, ctx.source),
        )
        return ctx

    def get_aqi_context(self, user_id: str) -> AqiContext | None:
        """Return the AQI context for ``user_id``, or None."""
        row = self.one("SELECT * FROM aqi_context WHERE user_id = ?", (user_id,))
        return row_to_context(row) if row else None

    def create_document(self, doc: Document) -> Document:
        """Insert a document and return it with a generated id."""
        stored = replace(doc, id=doc.id or _new_id(), created_at=doc.created_at or _now())
        self.run(
            "INSERT INTO documents (id, owner_id, kind, title, text, chunks, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (stored.id, stored.owner_id, stored.kind, stored.title, stored.text, json.dumps(stored.chunks), stored.source, stored.created_at),
        )
        return stored

    def list_documents(self, owner_id: str) -> list[Document]:
        """Return every document owned by ``owner_id``."""
        rows = self.all(
            "SELECT * FROM documents WHERE owner_id = ? ORDER BY created_at ASC",
            (owner_id,),
        )
        return [row_to_document(row) for row in rows]

    def get_document(self, doc_id: str) -> Document | None:
        """Return the document with ``doc_id``, or None."""
        row = self.one("SELECT * FROM documents WHERE id = ?", (doc_id,))
        return row_to_document(row) if row else None

    def delete_document(self, doc_id: str, owner_id: str) -> bool:
        """Delete ``doc_id`` when owned by ``owner_id``."""
        sql = "DELETE FROM documents WHERE id = ? AND owner_id = ?"
        return self.delete(sql, (doc_id, owner_id)) > 0

    def count_documents(self, owner_id: str) -> int:
        """Return the number of documents owned by ``owner_id``."""
        return self.count("SELECT COUNT(*) FROM documents WHERE owner_id = ?", (owner_id,))

    def count_users(self) -> int:
        """Return the total number of users."""
        return self.count("SELECT COUNT(*) FROM users")

    def count_profiles(self) -> int:
        """Return the total number of profiles."""
        return self.count("SELECT COUNT(*) FROM profiles")

    def count_all_documents(self) -> int:
        """Return the total number of documents across owners."""
        return self.count("SELECT COUNT(*) FROM documents")
