"""Schema DDL and the table list."""

from __future__ import annotations

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    city TEXT NOT NULL DEFAULT '',
    climate_zone TEXT NOT NULL,
    children INTEGER NOT NULL DEFAULT 0,
    elderly INTEGER NOT NULL DEFAULT 0,
    respiratory INTEGER NOT NULL DEFAULT 0,
    commute_mode TEXT NOT NULL,
    commute_km REAL NOT NULL DEFAULT 0,
    cooking_fuel TEXT NOT NULL,
    heating_type TEXT NOT NULL,
    budget_level TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    chunks TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aqi_context (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    city TEXT NOT NULL,
    band TEXT NOT NULL,
    value INTEGER,
    pm25 REAL,
    pm10 REAL,
    season TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL
);
"""

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);
"""

TABLES: tuple[str, ...] = (
    "users",
    "profiles",
    "documents",
    "aqi_context",
    "revoked_tokens",
)
