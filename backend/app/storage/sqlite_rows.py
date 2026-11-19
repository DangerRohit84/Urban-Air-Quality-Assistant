"""Row-to-dataclass mappers for the SQLite backend."""

from __future__ import annotations

import json
import sqlite3

from backend.app.models import AqiContext, Document, Profile, User


def row_to_user(row: sqlite3.Row) -> User:
    """Convert a ``users`` row into a ``User``.

    Args:
        row: The database row.

    Returns:
        The domain object.
    """
    return User(row["id"], row["email"], row["password_hash"], row["created_at"])


def row_to_profile(row: sqlite3.Row) -> Profile:
    """Convert a ``profiles`` row into a ``Profile``.

    Args:
        row: The database row.

    Returns:
        The domain object.
    """
    return Profile(
        row["user_id"],
        row["city"],
        row["climate_zone"],
        bool(row["children"]),
        bool(row["elderly"]),
        bool(row["respiratory"]),
        row["commute_mode"],
        float(row["commute_km"]),
        row["cooking_fuel"],
        row["heating_type"],
        row["budget_level"],
        row["updated_at"],
    )


def row_to_document(row: sqlite3.Row) -> Document:
    """Convert a ``documents`` row into a ``Document``.

    Args:
        row: The database row.

    Returns:
        The domain object.
    """
    return Document(
        row["id"],
        row["owner_id"],
        row["kind"],
        row["title"],
        row["text"],
        json.loads(row["chunks"]),
        row["source"],
        row["created_at"],
    )


def row_to_context(row: sqlite3.Row) -> AqiContext:
    """Convert an ``aqi_context`` row into an ``AqiContext``.

    Args:
        row: The database row.

    Returns:
        The domain object.
    """
    return AqiContext(
        row["user_id"],
        row["city"],
        row["band"],
        row["value"],
        row["pm25"],
        row["pm10"],
        row["season"],
        row["observed_at"],
        row["source"],
    )
