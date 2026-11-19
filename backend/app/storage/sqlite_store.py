"""SQLite implementation of the Repository protocol."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from backend.app.models import AqiContext, Document, Profile, User
from backend.app.storage.migrations import apply_migrations
from backend.app.storage.sqlite_base import connect


def _now() -> str:
    """Return the current UTC timestamp in ISO-8601."""
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    """Return a fresh hex identifier."""
    return uuid.uuid4().hex


def _row_to_user(row: sqlite3.Row) -> User:
    """Convert a ``users`` row into a ``User``."""
    return User(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


def _row_to_profile(row: sqlite3.Row) -> Profile:
    """Convert a ``profiles`` row into a ``Profile``."""
    return Profile(
        user_id=row["user_id"],
        city=row["city"],
        climate_zone=row["climate_zone"],
        children=bool(row["children"]),
        elderly=bool(row["elderly"]),
        respiratory=bool(row["respiratory"]),
        commute_mode=row["commute_mode"],
        commute_km=float(row["commute_km"]),
        cooking_fuel=row["cooking_fuel"],
        heating_type=row["heating_type"],
        budget_level=row["budget_level"],
        updated_at=row["updated_at"],
    )


def _row_to_document(row: sqlite3.Row) -> Document:
    """Convert a ``documents`` row into a ``Document``."""
    return Document(
        id=row["id"],
        owner_id=row["owner_id"],
        kind=row["kind"],
        title=row["title"],
        text=row["text"],
        chunks=json.loads(row["chunks"]),
        source=row["source"],
        created_at=row["created_at"],
    )


def _row_to_context(row: sqlite3.Row) -> AqiContext:
    """Convert an ``aqi_context`` row into an ``AqiContext``."""
    return AqiContext(
        user_id=row["user_id"],
        city=row["city"],
        band=row["band"],
        value=row["value"],
        pm25=row["pm25"],
        pm10=row["pm10"],
        season=row["season"],
        observed_at=row["observed_at"],
        source=row["source"],
    )


class SQLiteRepo:
    """A threaded SQLite implementation of the Repository protocol."""

    def __init__(self, db_path: Path) -> None:
        """Open the database and apply migrations.

        Args:
            db_path: Path of the SQLite database file.
        """
        self._conn = connect(db_path)
        self._lock = threading.RLock()
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Apply pending schema migrations."""
        with self._lock:
            apply_migrations(self._conn)

    def create_user(self, email: str, password_hash: str) -> User:
        """Insert a user and return it with a generated id."""
        user = User(
            id=_new_id(),
            email=email,
            password_hash=password_hash,
            created_at=_now(),
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user.id, user.email, user.password_hash, user.created_at),
            )
            self._conn.commit()
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Return the user with ``email``, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return _row_to_user(row) if row is not None else None

    def get_user_by_id(self, user_id: str) -> User | None:
        """Return the user with ``user_id``, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return _row_to_user(row) if row is not None else None

    def save_profile(self, profile: Profile) -> Profile:
        """Insert or update the profile for ``profile.user_id``."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO profiles ("
                "user_id, city, climate_zone, children, elderly, respiratory, "
                "commute_mode, commute_km, cooking_fuel, heating_type, "
                "budget_level, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "city=excluded.city, climate_zone=excluded.climate_zone, "
                "children=excluded.children, elderly=excluded.elderly, "
                "respiratory=excluded.respiratory, "
                "commute_mode=excluded.commute_mode, "
                "commute_km=excluded.commute_km, "
                "cooking_fuel=excluded.cooking_fuel, "
                "heating_type=excluded.heating_type, "
                "budget_level=excluded.budget_level, "
                "updated_at=excluded.updated_at",
                (
                    profile.user_id,
                    profile.city,
                    profile.climate_zone,
                    int(profile.children),
                    int(profile.elderly),
                    int(profile.respiratory),
                    profile.commute_mode,
                    profile.commute_km,
                    profile.cooking_fuel,
                    profile.heating_type,
                    profile.budget_level,
                    profile.updated_at,
                ),
            )
            self._conn.commit()
        return profile

    def get_profile(self, user_id: str) -> Profile | None:
        """Return the profile for ``user_id``, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        return _row_to_profile(row) if row is not None else None

    def save_aqi_context(self, ctx: AqiContext) -> AqiContext:
        """Insert or update the AQI context for ``ctx.user_id``."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO aqi_context ("
                "user_id, city, band, value, pm25, pm10, season, "
                "observed_at, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "city=excluded.city, band=excluded.band, value=excluded.value, "
                "pm25=excluded.pm25, pm10=excluded.pm10, "
                "season=excluded.season, observed_at=excluded.observed_at, "
                "source=excluded.source",
                (
                    ctx.user_id,
                    ctx.city,
                    ctx.band,
                    ctx.value,
                    ctx.pm25,
                    ctx.pm10,
                    ctx.season,
                    ctx.observed_at,
                    ctx.source,
                ),
            )
            self._conn.commit()
        return ctx

    def get_aqi_context(self, user_id: str) -> AqiContext | None:
        """Return the AQI context for ``user_id``, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM aqi_context WHERE user_id = ?", (user_id,)
            ).fetchone()
        return _row_to_context(row) if row is not None else None

    def create_document(self, doc: Document) -> Document:
        """Insert a document and return it with a generated id."""
        stored = replace(
            doc,
            id=doc.id or _new_id(),
            created_at=doc.created_at or _now(),
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents ("
                "id, owner_id, kind, title, text, chunks, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    stored.id,
                    stored.owner_id,
                    stored.kind,
                    stored.title,
                    stored.text,
                    json.dumps(stored.chunks),
                    stored.source,
                    stored.created_at,
                ),
            )
            self._conn.commit()
        return stored

    def list_documents(self, owner_id: str) -> list[Document]:
        """Return every document owned by ``owner_id``."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE owner_id = ? ORDER BY created_at ASC",
                (owner_id,),
            ).fetchall()
        return [_row_to_document(row) for row in rows]

    def get_document(self, doc_id: str) -> Document | None:
        """Return the document with ``doc_id``, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return _row_to_document(row) if row is not None else None

    def delete_document(self, doc_id: str, owner_id: str) -> bool:
        """Delete ``doc_id`` when owned by ``owner_id``."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM documents WHERE id = ? AND owner_id = ?",
                (doc_id, owner_id),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def count_documents(self, owner_id: str) -> int:
        """Return the number of documents owned by ``owner_id``."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM documents WHERE owner_id = ?", (owner_id,)
            ).fetchone()
        return int(row[0])

    def count_users(self) -> int:
        """Return the total number of users."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0])

    def count_profiles(self) -> int:
        """Return the total number of profiles."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM profiles").fetchone()
        return int(row[0])

    def count_all_documents(self) -> int:
        """Return the total number of documents across owners."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        return int(row[0])

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()
