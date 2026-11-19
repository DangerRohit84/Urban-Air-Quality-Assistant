"""Scaffold assertions: configuration files and the quality-gate runner exist."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
REQUIREMENTS = ROOT / "requirements.txt"
ENV_EXAMPLE = ROOT / ".env.example"
GITIGNORE = ROOT / ".gitignore"
DOCKERFILE = ROOT / "Dockerfile"
CHECK_QUALITY = ROOT / "scripts" / "check_quality.py"


def _load_check_quality() -> object:
    """Load scripts/check_quality.py without requiring it to be a package."""
    spec = importlib.util.spec_from_file_location("check_quality", CHECK_QUALITY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pyproject_declares_coverage_floor_and_strict_warnings() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    ini_options = data["tool"]["pytest"]["ini_options"]
    coverage_report = data["tool"]["coverage"]["report"]

    assert coverage_report["fail_under"] == 76
    assert "error" in ini_options["filterwarnings"]


def test_requirements_pin_the_audited_set() -> None:
    text = REQUIREMENTS.read_text(encoding="utf-8")

    for prefix in (
        "fastapi==",
        "pypdf==",
        "scikit-learn==",
        "pytest==",
        "ruff==",
        "mypy==",
    ):
        assert prefix in text


def test_env_example_documents_required_settings() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    for key in ("AUTH_SECRET=", "AQI_API_KEY=", "LLM_PROVIDER="):
        assert key in text


def test_gitignore_covers_env_data_and_venv() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")

    for entry in (".env", "data/", ".venv"):
        assert entry in text


def test_dockerfile_has_healthcheck() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in text
    assert "/health" in text


def test_check_quality_runner_exists_and_reads_floor() -> None:
    assert CHECK_QUALITY.exists()
    module = _load_check_quality()

    assert module.read_coverage_floor() == 76.0  # type: ignore[attr-defined]
