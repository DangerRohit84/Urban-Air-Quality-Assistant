"""Tests for config.Settings environment parsing and derived properties."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.config import Settings


def test_db_path_resolves_sqlite_url() -> None:
    """``sqlite:///./data/air.db`` resolves to ``data/air.db``."""
    settings = Settings(database_url="sqlite:///./data/air.db")

    assert settings.db_path == Path("data/air.db")


def test_allowed_origins_drops_wildcard_and_malformed_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CORS allowlist drops ``*`` and entries without an http(s) scheme."""
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,*,not-a-url,https://example.com",
    )

    settings = Settings()

    assert settings.allowed_origins == [
        "http://localhost:3000",
        "https://example.com",
    ]


def test_rate_limit_parses_int_env_with_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """``RATE_LIMIT_PER_MIN`` parses as an int and defaults to 200."""
    monkeypatch.delenv("RATE_LIMIT_PER_MIN", raising=False)
    assert Settings().rate_limit_per_min == 200

    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "42")
    assert Settings().rate_limit_per_min == 42


def test_aqi_api_key_defaults_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """``AQI_API_KEY`` defaults to the empty string (offline-first)."""
    monkeypatch.delenv("AQI_API_KEY", raising=False)

    assert Settings().aqi_api_key == ""


def test_llm_provider_defaults_to_local_synth(monkeypatch: pytest.MonkeyPatch) -> None:
    """``LLM_PROVIDER`` defaults to ``local_synth``."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    assert Settings().llm_provider == "local_synth"
