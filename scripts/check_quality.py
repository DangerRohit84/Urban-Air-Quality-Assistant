#!/usr/bin/env python
"""Run the full quality gate for the Urban Air Quality Assistant.

Usage::

    python scripts/check_quality.py

The script exits with code 0 only when every gate passes:

1. ``ruff``    - no lint or format errors anywhere in the repository.
2. ``mypy``    - no type errors in ``backend/app``.
3. ``pytest``  - the whole suite passes.
4. ``coverage`` - the TOTAL percentage reaches the ``fail_under`` floor
   declared in ``pyproject.toml`` under ``[tool.coverage.report]``.

When ``backend/app`` contains no measurable Python modules the coverage gate
reports ``skipped (no backend modules)`` and does not fail; a lone
``__init__.py`` carries no statements, so it cannot produce a coverage report.
The configuration is read with a small regular-expression reader so the script
needs no third-party TOML parser.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
BACKEND_APP = ROOT / "backend" / "app"

# Mirrors the ``fail_under`` value in pyproject.toml; the test suite asserts
# the two stay in sync.
DEFAULT_COVERAGE_FLOOR = 89.0

# The plan's quality bar: at least 200 collected tests.
MINIMUM_TEST_COUNT = 200

_RESULTS: list[tuple[str, bool, str]] = []


def read_coverage_floor(pyproject: Path = PYPROJECT) -> float:
    """Read the coverage floor declared in ``pyproject.toml``.

    Args:
        pyproject: Path of the project configuration file.

    Returns:
        The declared ``fail_under`` floor, or the built-in default when the
        file does not declare one.
    """
    if not pyproject.exists():
        return DEFAULT_COVERAGE_FLOOR
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*fail_under\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$",
        text,
        re.MULTILINE,
    )
    if not match:
        return DEFAULT_COVERAGE_FLOOR
    return float(match.group(1))


def run(step: str, command: list[str]) -> tuple[bool, str]:
    """Run one gate command and capture its output.

    Args:
        step: Human-readable name of the gate.
        command: The command line to execute.

    Returns:
        A ``(passed, output)`` pair.
    """
    printable = " ".join(command)
    print(f"\n=== {step}: {printable} ===", flush=True)
    completed = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    sys.stdout.write(output)
    passed = completed.returncode == 0
    _RESULTS.append((step, passed, printable))
    return passed, output


def parse_total_coverage(output: str) -> float | None:
    """Extract the TOTAL coverage percentage from a coverage report.

    Args:
        output: The captured output of the pytest coverage run.

    Returns:
        The TOTAL percentage, or None when the report has no TOTAL row.
    """
    match = re.search(
        r"^TOTAL\s+.*?(\d+(?:\.\d+)?)%\s*$",
        output,
        re.MULTILINE,
    )
    return float(match.group(1)) if match else None


def parse_test_count(output: str) -> int | None:
    """Extract the passing test count from a pytest summary line.

    Args:
        output: The captured output of the pytest run.

    Returns:
        The number of passing tests, or None when no summary is present.
    """
    match = re.search(r"(\d+) passed", output)
    return int(match.group(1)) if match else None


def _has_backend_modules() -> bool:
    """Return True when ``backend/app`` holds a module coverage can measure.

    The package marker ``__init__.py`` is excluded: it is exempt from the
    module-size rule and normally holds no statements, so a tree containing
    only markers would yield "No data was collected" rather than a report.
    """
    if not BACKEND_APP.is_dir():
        return False
    return any(
        path.suffix == ".py" and path.name != "__init__.py"
        for path in BACKEND_APP.rglob("*.py")
    )


def main() -> int:
    """Run every quality gate and report the outcome.

    Returns:
        0 when every gate passes, 1 otherwise.
    """
    floor = read_coverage_floor()
    print(f"Quality gates: ruff, mypy, pytest, coverage >= {floor}%")

    run("lint", [sys.executable, "-m", "ruff", "check", "."])
    run("format", [sys.executable, "-m", "ruff", "format", "--check", "."])
    run("types", [sys.executable, "-m", "mypy", "backend/app"])

    measurable = _has_backend_modules()
    if measurable:
        # Use ``coverage run`` rather than pytest-cov: pytest-cov writes
        # parallel data files, and subprocesses started by tests can then
        # combine statement-only shards with branch-aware ones.
        coverage_file = Path(os.environ.get("COVERAGE_FILE", str(ROOT / ".coverage")))
        coverage_file.unlink(missing_ok=True)
        tests_passed, test_output = run(
            "tests",
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--branch",
                "--source=backend",
                "-m",
                "pytest",
                "-q",
            ],
        )
    else:
        tests_passed, test_output = run("tests", [sys.executable, "-m", "pytest", "-q"])

    test_count = parse_test_count(test_output)
    count_ok = test_count is not None and test_count >= MINIMUM_TEST_COUNT
    _RESULTS.append(
        (
            "test-count",
            count_ok,
            (
                f"{test_count} tests >= {MINIMUM_TEST_COUNT}"
                if test_count is not None
                else "no pytest summary"
            ),
        )
    )

    if measurable and tests_passed:
        _, report = run("coverage", [sys.executable, "-m", "coverage", "report"])
        total = parse_total_coverage(report)
        coverage_ok = total is not None and total >= floor
        detail = (
            f"TOTAL {total:.1f}% >= {floor:.1f}%"
            if total is not None
            else "no TOTAL row"
        )
    elif measurable:
        coverage_ok = False
        detail = "skipped (tests failed)"
    else:
        coverage_ok = True
        detail = "skipped (no backend modules)"
    _RESULTS.append(("coverage", coverage_ok, detail))

    print("\n=== summary ===")
    for step, passed, detail in _RESULTS:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {step}: {detail}")

    failed = [step for step, passed, _ in _RESULTS if not passed]
    if failed:
        print(f"\nQUALITY GATE FAILED: {', '.join(failed)}")
        return 1
    print("\nQUALITY GATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
