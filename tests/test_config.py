"""Tests for config.Settings environment parsing and derived properties."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.config import Settings

ROOT = Path(__file__).resolve().parents[1]
CONFIG_MODULE = ROOT / "backend" / "app" / "config.py"


def _run_isolated_config(
    tmp_path: Path, env_text: str, environ: dict[str, str]
) -> str:
    """Import a copied config module next to a local ``.env`` file.

    Args:
        tmp_path: The temporary directory.
        env_text: The ``.env`` contents.
        environ: Extra environment variables for the child process.

    Returns:
        The printed ``settings.auth_secret``.
    """
    package = tmp_path / "backend" / "app"
    package.mkdir(parents=True)
    (tmp_path / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy(CONFIG_MODULE, package / "config.py")
    (tmp_path / ".env").write_text(env_text, encoding="utf-8")
    child_env = {
        key: value for key, value in os.environ.items() if key != "AUTH_SECRET"
    }
    child_env.update(environ)
    child_env["PYTHONPATH"] = str(tmp_path)
    result = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [
            sys.executable,
            "-c",
            "import backend.app.config as c; print(c.settings.auth_secret)",
        ],
        cwd=str(tmp_path),
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


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


def test_malformed_int_env_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-integer ``PORT`` warns instead of crashing at import."""
    monkeypatch.setenv("PORT", "not-a-number")

    with pytest.warns(UserWarning, match="PORT"):
        parsed = Settings()

    assert parsed.port == 8000


def test_dotenv_file_is_discovered_and_feeds_settings(tmp_path: Path) -> None:
    """The repository-root ``.env`` is auto-discovered before ``Settings``."""
    value = _run_isolated_config(tmp_path, "AUTH_SECRET=from-dotenv\n", {})

    assert value == "from-dotenv"


def test_real_environment_wins_over_dotenv(tmp_path: Path) -> None:
    """An exported variable takes precedence over the ``.env`` value."""
    value = _run_isolated_config(
        tmp_path,
        "AUTH_SECRET=from-dotenv\n",
        {"AUTH_SECRET": "from-env"},
    )

    assert value == "from-env"
