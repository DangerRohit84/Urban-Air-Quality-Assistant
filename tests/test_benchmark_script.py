"""Tests for the benchmark script's pure helpers."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "benchmark.py"


def _load() -> ModuleType:
    """Load ``scripts/benchmark.py`` as a module.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("benchmark_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return module


def test_build_pdf_reaches_the_target_size_and_keeps_text() -> None:
    """A padded benchmark PDF still extracts its page text."""
    from backend.app.pdf_text import extract_pdf_text

    module = _load()
    pdf = module.build_pdf("HEPA purifier guidance", 250_000)

    assert len(pdf) >= 250_000
    assert b"%PDF-1.4" in pdf
    assert "HEPA purifier guidance" in extract_pdf_text(pdf)


def test_multipart_body_contains_the_pdf_and_boundary() -> None:
    """The upload body carries the file field and its boundary."""
    module = _load()
    body, content_type = module.multipart_pdf(b"%PDF-1.4 test")

    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="file"' in body
    assert b"%PDF-1.4 test" in body
    assert content_type.rsplit("=", 1)[1].encode() in body


def test_percentile_uses_nearest_rank() -> None:
    """Percentiles use the nearest-rank definition."""
    module = _load()
    values = [float(index) for index in range(1, 21)]

    assert module.percentile(values, 50) == 10.0
    assert module.percentile(values, 95) == 19.0
    assert module.percentile([3.0], 95) == 3.0


def test_sample_summary_reports_mean_p50_and_p95() -> None:
    """The summary reports count, mean, p50 and p95."""
    module = _load()
    sample = module.Sample("op")
    sample.values_ms.extend([1.0, 2.0, 3.0, 4.0])

    summary = sample.summary()

    assert summary["count"] == 4.0
    assert summary["mean_ms"] == 2.5
    assert summary["p50_ms"] == 2.0
    assert summary["p95_ms"] == 4.0


def test_help_flag_runs_without_starting_the_server() -> None:
    """``--help`` exits zero and documents the flags."""
    result = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [sys.executable, str(SCRIPT), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--iterations" in result.stdout
    assert "--json" in result.stdout
    assert "--skip-docker" in result.stdout


def test_docker_failure_reports_each_failure_mode() -> None:
    """Unavailable, build-failed and smoke-failed evidence is a failure."""
    module = _load()

    assert module.docker_failure({"docker": {"skipped": "opted out"}}) is None
    assert module.docker_failure(
        {"docker": {"available": False, "reason": "docker is not on PATH"}}
    )
    assert module.docker_failure(
        {"docker": {"available": True, "built": False, "reason": "boom"}}
    )
    assert module.docker_failure(
        {
            "docker": {
                "available": True,
                "built": True,
                "smoke_512m": "failed",
                "smoke_detail": "ask 500",
            }
        }
    )
    assert (
        module.docker_failure(
            {"docker": {"available": True, "built": True, "smoke_512m": "passed"}}
        )
        is None
    )


def test_main_exits_nonzero_when_docker_fails(monkeypatch) -> None:
    """A failed Docker build makes the default run exit nonzero."""
    module = _load()
    calls: list[bool] = []

    def fake_benchmark(iterations: int, with_docker: bool) -> dict[str, object]:
        calls.append(with_docker)
        return {"docker": {"available": True, "built": False, "reason": "boom"}}

    monkeypatch.setattr(module, "benchmark", fake_benchmark)
    monkeypatch.setattr(module, "print_report", lambda report: None)

    assert module.main(["--iterations", "1"]) == 1
    assert calls == [True]


def test_main_skip_docker_exits_zero(monkeypatch) -> None:
    """``--skip-docker`` opts out and returns zero even without evidence."""
    module = _load()
    calls: list[bool] = []

    def fake_benchmark(iterations: int, with_docker: bool) -> dict[str, object]:
        calls.append(with_docker)
        return {"docker": {"skipped": "disabled by --skip-docker"}}

    monkeypatch.setattr(module, "benchmark", fake_benchmark)
    monkeypatch.setattr(module, "print_report", lambda report: None)

    assert module.main(["--iterations", "1", "--skip-docker"]) == 0
    assert calls == [False]
