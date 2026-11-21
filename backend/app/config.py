"""Application configuration parsed from environment variables."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    """Load a ``.env`` file into the process environment.

    Existing environment variables always win over the file, so a real
    environment (Render, Docker, CI) is never overridden by a checked-out
    ``.env``. The search starts at this module's directory and walks up, so
    the repository-root ``.env`` created by ``cp .env.example .env`` is found.

    Returns:
        Nothing; the process environment is updated in place.
    """
    load_dotenv()


def _env_str(name: str, default: str) -> str:
    """Read a string environment variable, falling back to ``default``.

    Args:
        name: The environment variable name.
        default: The value used when the variable is unset or empty.

    Returns:
        The variable value or the default.
    """
    value = os.getenv(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``.

    Args:
        name: The environment variable name.
        default: The value used when the variable is unset or empty.

    Returns:
        The parsed integer or the default.
    """
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        warnings.warn(
            f"{name}={value!r} is not an integer; falling back to {default}",
            stacklevel=2,
        )
        return default


@dataclass
class Settings:
    """Runtime settings derived from the process environment."""

    llm_provider: str = field(
        default_factory=lambda: _env_str("LLM_PROVIDER", "local_synth")
    )
    gemini_api_key: str = field(default_factory=lambda: _env_str("GEMINI_API_KEY", ""))
    gemini_model: str = field(
        default_factory=lambda: _env_str("GEMINI_MODEL", "gemini-2.0-flash")
    )
    openai_api_key: str = field(default_factory=lambda: _env_str("OPENAI_API_KEY", ""))
    openai_base_url: str = field(
        default_factory=lambda: _env_str(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
    )
    openai_model: str = field(
        default_factory=lambda: _env_str("OPENAI_MODEL", "gpt-4o-mini")
    )
    aqi_api_key: str = field(default_factory=lambda: _env_str("AQI_API_KEY", ""))
    store_backend: str = field(
        default_factory=lambda: _env_str("STORE_BACKEND", "sqlite")
    )
    database_url: str = field(
        default_factory=lambda: _env_str("DATABASE_URL", "sqlite:///./data/air.db")
    )
    auth_secret: str = field(default_factory=lambda: _env_str("AUTH_SECRET", ""))
    frontend_origin: str = field(
        default_factory=lambda: _env_str("FRONTEND_ORIGIN", "http://localhost:8000")
    )
    rate_limit_per_min: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_PER_MIN", 200)
    )
    max_rate_buckets: int = field(
        default_factory=lambda: _env_int("MAX_RATE_BUCKETS", 10000)
    )
    trust_proxy: bool = field(
        default_factory=lambda: _env_str("TRUST_PROXY", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    trusted_proxy_hops: int = field(
        default_factory=lambda: _env_int("TRUSTED_PROXY_HOPS", 1)
    )
    max_upload_bytes: int = field(
        default_factory=lambda: _env_int("MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
    )
    max_documents: int = field(default_factory=lambda: _env_int("MAX_DOCUMENTS", 10))
    port: int = field(default_factory=lambda: _env_int("PORT", 8000))
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "info"))

    @property
    def db_path(self) -> Path:
        """Resolve the SQLite database path from ``database_url``.

        Returns:
            The filesystem path of the SQLite database.
        """
        url = self.database_url
        for prefix in ("sqlite:///", "sqlite://"):
            if url.startswith(prefix):
                return Path(url[len(prefix) :])
        return Path(url)

    @property
    def allowed_origins(self) -> list[str]:
        """Return the CORS allowlist, dropping wildcards and malformed entries.

        Returns:
            The validated origin strings.
        """
        raw = _env_str("ALLOWED_ORIGINS", self.frontend_origin)
        origins: list[str] = []
        for item in raw.split(","):
            candidate = item.strip()
            if not candidate or candidate == "*":
                continue
            if not candidate.startswith(("http://", "https://")):
                continue
            origins.append(candidate)
        return origins


load_environment()

settings = Settings()
