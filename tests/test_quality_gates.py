"""Tests for the quality-gate runner itself."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK_QUALITY = ROOT / "scripts" / "check_quality.py"
SUBPROCESS_FLAG = "QUALITY_GATE_SUBPROCESS"


def _load_runner() -> object:
    """Load ``scripts/check_quality.py`` as a module.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("check_quality", CHECK_QUALITY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remove_nested_coverage() -> None:
    """Remove nested coverage files, including pytest-cov parallel shards."""
    for path in ROOT.glob(".coverage.nested*"):
        path.unlink(missing_ok=True)


def test_coverage_floor_is_enforced() -> None:
    """The runner reads the declared floor and parses coverage output."""
    module = _load_runner()

    assert module.read_coverage_floor() == 89.0  # type: ignore[attr-defined]
    sample = "TOTAL 1603 87 95%"
    assert module.parse_total_coverage(sample) == 95.0  # type: ignore[attr-defined]


def test_check_quality_script_passes() -> None:
    """``scripts/check_quality.py`` exits 0 on the current tree."""
    if os.environ.get(SUBPROCESS_FLAG) == "1":
        pytest.skip("nested quality-gate run")

    env = dict(os.environ)
    env[SUBPROCESS_FLAG] = "1"
    env["COVERAGE_FILE"] = str(ROOT / ".coverage.nested")
    _remove_nested_coverage()
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
            [sys.executable, str(CHECK_QUALITY)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    finally:
        _remove_nested_coverage()

    assert result.returncode == 0, result.stdout + result.stderr
