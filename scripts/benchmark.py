#!/usr/bin/env python
"""Measure the Urban Air Quality Assistant end to end and record evidence.

Usage::

    python scripts/benchmark.py [--iterations 30] [--json PATH] [--skip-docker]

The script starts the real server with uvicorn against a temporary SQLite
database, exercises the documented API over HTTP, and reports nearest-rank
p50/p95 latency, means, cold-import time and, unless ``--skip-docker`` is
given, the image size plus a 512 MiB container smoke test. Docker build or
smoke failures exit nonzero so CI cannot silently pass without the evidence;
``--skip-docker`` (or the legacy ``--no-docker`` alias) opts out and exits
zero. Only the standard library is used, so it runs in the same environment
as the app without extra installs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "urban-air-quality-assistant:benchmark"
PASSWORD = "BenchPass123"
GROUNDED_QUESTION = "Which indoor air purifier should I use?"
REFUSAL_QUESTION = "What is the best pizza in Naples?"
HEALTH_TIMEOUT = 30.0
REQUEST_TIMEOUT = 30.0
PDF_TARGET_BYTES = 1_000_000
PDF_TEXT = "HEPA purifier guidance: run it in the bedroom at night."


def percentile(values: list[float], pct: float) -> float:
    """Return the nearest-rank percentile of ascending ``values``.

    Args:
        values: The ascending samples.
        pct: The percentile in ``(0, 100]``.

    Returns:
        The nearest-rank value.
    """
    rank = max(1, math.ceil(pct / 100 * len(values)))
    return values[rank - 1]


@dataclass
class Sample:
    """Latency samples for one operation."""

    name: str
    values_ms: list[float] = field(default_factory=list)

    def record(self, start_ns: int) -> None:
        """Record the elapsed time since ``start_ns``.

        Args:
            start_ns: The ``perf_counter_ns`` value taken before the call.
        """
        self.values_ms.append((time.perf_counter_ns() - start_ns) / 1_000_000)

    def summary(self) -> dict[str, float]:
        """Summarise the samples with mean, p50, p95, min and max.

        Returns:
            The rounded statistics in milliseconds.
        """
        ordered = sorted(self.values_ms)
        return {
            "count": float(len(ordered)),
            "mean_ms": round(statistics.fmean(ordered), 2),
            "p50_ms": round(percentile(ordered, 50), 2),
            "p95_ms": round(percentile(ordered, 95), 2),
            "min_ms": round(ordered[0], 2),
            "max_ms": round(ordered[-1], 2),
        }


class Api:
    """A tiny JSON client for the benchmarked server."""

    def __init__(self, base_url: str) -> None:
        """Store the server base URL.

        Args:
            base_url: The origin, for example ``http://127.0.0.1:8000``.
        """
        self.base_url = base_url

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, bytes]:
        """Send one HTTP request and return ``(status, body)``.

        Args:
            method: The HTTP method.
            path: The path with query string.
            payload: An optional JSON body.
            headers: Optional request headers.
            body: An optional raw body.
            content_type: An optional ``Content-Type`` override.

        Returns:
            The status code and the raw response body.
        """
        data = body
        request_headers = dict(headers or {})
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if content_type:
            request_headers["Content-Type"] = content_type
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Send a request and decode a JSON object response.

        Args:
            method: The HTTP method.
            path: The path with query string.
            payload: An optional JSON body.
            headers: Optional request headers.
            body: An optional raw body.
            content_type: An optional ``Content-Type`` override.

        Returns:
            The status code and the decoded object (empty when no body).
        """
        status, raw = self.request(
            method,
            path,
            payload=payload,
            headers=headers,
            body=body,
            content_type=content_type,
        )
        return status, json.loads(raw) if raw else {}


def free_port() -> int:
    """Return an unused local TCP port.

    Returns:
        The port number.
    """
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _assemble(objects: list[bytes]) -> bytes:
    """Assemble PDF objects with a valid xref table.

    Args:
        objects: The object bodies in object-number order.

    Returns:
        The complete PDF bytes.
    """
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return bytes(out)


def build_pdf(text: str, target_bytes: int = PDF_TARGET_BYTES) -> bytes:
    """Build a PDF that is ``target_bytes`` long and extracts ``text``.

    The file is padded with a trailing comment after ``%%EOF``; PDF readers
    ignore trailing data, so the extracted text stays identical while the
    upload exercises the real 1 MB body path.

    Args:
        text: The text to draw on the page.
        target_bytes: The minimum file size.

    Returns:
        The complete PDF bytes.
    """
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = _assemble(objects)
    if len(pdf) >= target_bytes:
        return pdf
    padding = target_bytes - len(pdf) - len(b"\n%")
    return pdf + b"\n%" + b"P" * max(0, padding)


def multipart_pdf(pdf: bytes, filename: str = "bench.pdf") -> tuple[bytes, str]:
    """Wrap ``pdf`` in a multipart/form-data body.

    Args:
        pdf: The PDF bytes.
        filename: The uploaded file name.

    Returns:
        The encoded body and its ``Content-Type`` header value.
    """
    boundary = "----uaqa" + uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("ascii")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    return head + pdf + tail, f"multipart/form-data; boundary={boundary}"


def start_server(port: int, db_path: Path, log_path: Path) -> subprocess.Popen[bytes]:
    """Start uvicorn against a temporary SQLite database.

    Args:
        port: The local port to bind.
        db_path: The SQLite file path.
        log_path: The file that receives the server output.

    Returns:
        The running server process.
    """
    env = os.environ.copy()
    env.update(
        {
            "STORE_BACKEND": "sqlite",
            "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
            "AUTH_SECRET": "benchmark-secret-" + uuid.uuid4().hex,
            "LLM_PROVIDER": "local_synth",
            "AQI_API_KEY": "",
            "RATE_LIMIT_PER_MIN": "100000",
            "MAX_UPLOAD_BYTES": str(8 * 1024 * 1024),
        }
    )
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-proxy-headers",
    ]
    log = log_path.open("wb")
    return subprocess.Popen(
        command,
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def wait_healthy(
    api: Api, process: subprocess.Popen[bytes], log_path: Path
) -> None:
    """Wait until ``GET /health`` answers 200.

    Args:
        api: The client bound to the server.
        process: The running server process.
        log_path: The server log, read on failure.

    Raises:
        RuntimeError: When the server exits or misses the deadline.
    """
    deadline = time.monotonic() + HEALTH_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"server exited early:\n{tail}")
        try:
            status, _ = api.request("GET", "/health")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(0.1)
    raise RuntimeError("server did not become healthy in time")


def timed(
    samples: dict[str, Sample],
    name: str,
    call: Callable[[], tuple[int, dict[str, Any]]],
    expected: int,
) -> dict[str, Any]:
    """Time one call, assert its status and record the latency.

    Args:
        samples: The sample registry.
        name: The operation name.
        call: The request callable returning ``(status, body)``.
        expected: The expected status code.

    Returns:
        The decoded response body.

    Raises:
        RuntimeError: When the status differs from ``expected``.
    """
    start = time.perf_counter_ns()
    status, body = call()
    elapsed = time.perf_counter_ns() - start
    if status != expected:
        raise RuntimeError(f"{name}: expected {expected}, got {status}: {body}")
    samples[name].values_ms.append(elapsed / 1_000_000)
    return body


def run_iteration(
    api: Api,
    samples: dict[str, Sample],
    pdf_body: bytes,
    pdf_type: str,
) -> None:
    """Run one measured pass over every benchmarked operation.

    Args:
        api: The client bound to the server.
        samples: The sample registry.
        pdf_body: The multipart body carrying the ~1 MB PDF.
        pdf_type: The multipart ``Content-Type``.
    """
    email = f"bench-{uuid.uuid4().hex}@example.com"
    start = time.perf_counter_ns()
    status, registered = api.json(
        "POST",
        "/auth/register",
        payload={"email": email, "password": PASSWORD},
    )
    status2, logged_in = api.json(
        "POST",
        "/auth/login",
        payload={"email": email, "password": PASSWORD},
    )
    elapsed = time.perf_counter_ns() - start
    if status != 201 or status2 != 200:
        raise RuntimeError(f"register/login failed: {status}/{status2}")
    samples["register+login"].values_ms.append(elapsed / 1_000_000)
    headers = {"Authorization": "Bearer " + logged_in["token"]}

    timed(
        samples,
        "air offline",
        lambda: api.json("GET", "/air?q=Delhi", headers=headers),
        200,
    )
    grounded = timed(
        samples,
        "ask grounded",
        lambda: api.json(
            "POST", "/ask", payload={"question": GROUNDED_QUESTION}, headers=headers
        ),
        200,
    )
    if not grounded.get("grounded"):
        raise RuntimeError("seeded question unexpectedly refused")
    refused = timed(
        samples,
        "ask refusal",
        lambda: api.json(
            "POST", "/ask", payload={"question": REFUSAL_QUESTION}, headers=headers
        ),
        200,
    )
    if refused.get("grounded"):
        raise RuntimeError("out-of-domain question unexpectedly grounded")

    inline = timed(
        samples,
        "documents inline",
        lambda: api.json(
            "POST",
            "/documents",
            payload={
                "title": "Kitchen exhaust notes",
                "text": "Run the exhaust fan while cooking to cut indoor PM2.5.",
            },
            headers=headers,
        ),
        201,
    )
    uploaded = timed(
        samples,
        "documents upload ~1MB",
        lambda: api.json(
            "POST",
            "/documents/upload",
            body=pdf_body,
            content_type=pdf_type,
            headers=headers,
        ),
        201,
    )
    for doc_id in (inline["id"], uploaded["id"]):
        status, _ = api.request("DELETE", f"/documents/{doc_id}", headers=headers)
        if status != 204:
            raise RuntimeError(f"cleanup delete failed: {status}")


def cold_import(runs: int = 3) -> dict[str, float]:
    """Measure a fresh ``import backend.app.main`` process.

    Args:
        runs: The number of fresh processes.

    Returns:
        The median, min and max cold-import milliseconds.
    """
    env = os.environ.copy()
    env.update({"AUTH_SECRET": "benchmark-secret", "LLM_PROVIDER": "local_synth"})
    values: list[float] = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        subprocess.run(
            [sys.executable, "-c", "import backend.app.main"],
            cwd=str(ROOT),
            env=env,
            check=True,
            capture_output=True,
        )
        values.append((time.perf_counter_ns() - start) / 1_000_000)
    return {
        "runs": float(runs),
        "median_ms": round(statistics.median(values), 1),
        "min_ms": round(min(values), 1),
        "max_ms": round(max(values), 1),
    }


def docker_evidence() -> dict[str, Any]:
    """Build the image and smoke-test it under a 512 MiB memory cap.

    Returns:
        The measured image size and smoke result, or a skip reason.
    """
    if shutil.which("docker") is None:
        return {"available": False, "reason": "docker is not on PATH"}
    info = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if info.returncode != 0:
        return {"available": False, "reason": "docker daemon unavailable"}
    build = subprocess.run(
        ["docker", "build", "-t", IMAGE, "."],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    if build.returncode != 0:
        return {
            "available": True,
            "built": False,
            "reason": (build.stderr or build.stdout)[-1000:],
        }
    inspect = subprocess.run(
        ["docker", "image", "inspect", "-f", "{{.Size}}", IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    size_bytes = int(inspect.stdout.strip() or 0)
    result: dict[str, Any] = {
        "available": True,
        "built": True,
        "image": IMAGE,
        "image_size_bytes": size_bytes,
        "image_size_mib": round(size_bytes / (1024 * 1024), 1),
    }
    result.update(_docker_smoke())
    return result


def _docker_smoke() -> dict[str, Any]:
    """Run the image with ``--memory=512m`` and hit the API.

    Returns:
        The smoke verdict, or the failure detail.
    """
    name = "uaqa-bench-" + uuid.uuid4().hex[:8]
    port = free_port()
    command = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "--memory",
        "512m",
        "-p",
        f"{port}:8000",
        "-e",
        "AUTH_SECRET=benchmark-secret",
        "-e",
        "STORE_BACKEND=sqlite",
        "-e",
        "DATABASE_URL=sqlite:////tmp/bench.db",
        "-e",
        "LLM_PROVIDER=local_synth",
        "-e",
        "RATE_LIMIT_PER_MIN=100000",
        IMAGE,
    ]
    started = subprocess.run(command, capture_output=True, text=True, check=False)
    if started.returncode != 0:
        return {"smoke_512m": "failed", "smoke_detail": started.stderr[-500:]}
    api = Api(f"http://127.0.0.1:{port}")
    try:
        _wait_container(api)
        status, registered = api.json(
            "POST",
            "/auth/register",
            payload={"email": f"container-{uuid.uuid4().hex}@example.com",
                     "password": PASSWORD},
        )
        if status != 201:
            return {"smoke_512m": "failed", "smoke_detail": f"register {status}"}
        headers = {"Authorization": "Bearer " + registered["token"]}
        status, answer = api.json(
            "POST", "/ask", payload={"question": GROUNDED_QUESTION}, headers=headers
        )
        if status != 200 or not answer.get("grounded"):
            return {
                "smoke_512m": "failed",
                "smoke_detail": f"ask {status} grounded={answer.get('grounded')}",
            }
        return {"smoke_512m": "passed", "smoke_memory_limit": "512 MiB"}
    except (OSError, RuntimeError, KeyError) as exc:
        return {"smoke_512m": "failed", "smoke_detail": str(exc)[:500]}
    finally:
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True,
            text=True,
            check=False,
        )


def _wait_container(api: Api) -> None:
    """Wait for the container health endpoint.

    Args:
        api: The client bound to the published port.

    Raises:
        RuntimeError: When the container misses the deadline.
    """
    deadline = time.monotonic() + HEALTH_TIMEOUT
    while time.monotonic() < deadline:
        try:
            status, _ = api.request("GET", "/health")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError("container did not become healthy")


def benchmark(iterations: int, with_docker: bool) -> dict[str, Any]:
    """Run the whole benchmark and return the measured report.

    Args:
        iterations: The number of measured passes.
        with_docker: Whether to build and smoke-test the image.

    Returns:
        The report mapping, including per-operation statistics.
    """
    names = [
        "register+login",
        "air offline",
        "ask grounded",
        "ask refusal",
        "documents inline",
        "documents upload ~1MB",
    ]
    samples = {name: Sample(name) for name in names}
    pdf = build_pdf(PDF_TEXT)
    pdf_body, pdf_type = multipart_pdf(pdf)
    with tempfile.TemporaryDirectory(
        prefix="uaqa-bench-", ignore_cleanup_errors=True
    ) as tmp:
        tmp_path = Path(tmp)
        port = free_port()
        log_path = tmp_path / "server.log"
        process = start_server(port, tmp_path / "bench.db", log_path)
        api = Api(f"http://127.0.0.1:{port}")
        try:
            wait_healthy(api, process, log_path)
            for _ in range(iterations):
                run_iteration(api, samples, pdf_body, pdf_type)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            # Windows can release the SQLite handle a moment after the
            # process exits; a short pause keeps temp cleanup quiet.
            time.sleep(0.3)

    report: dict[str, Any] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "iterations": iterations,
        "pdf_bytes": len(pdf),
        "latency": {name: samples[name].summary() for name in names},
        "cold_import": cold_import(),
    }
    report["docker"] = (
        docker_evidence()
        if with_docker
        else {"skipped": True, "reason": "disabled by --skip-docker"}
    )
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a readable benchmark table.

    Args:
        report: The report returned by :func:`benchmark`.
    """
    print(f"\nPlatform: {report['platform']} | Python {report['python']}")
    print(f"Iterations: {report['iterations']} | PDF: {report['pdf_bytes']} bytes")
    print("\nOperation                  p50 ms   p95 ms   mean ms   min ms   max ms")
    for name, stats in report["latency"].items():
        print(
            f"{name:<26} {stats['p50_ms']:>7.2f} {stats['p95_ms']:>8.2f} "
            f"{stats['mean_ms']:>9.2f} {stats['min_ms']:>8.2f} "
            f"{stats['max_ms']:>8.2f}"
        )
    cold = report["cold_import"]
    print(f"\nCold import: median {cold['median_ms']} ms "
          f"(min {cold['min_ms']}, max {cold['max_ms']})")
    docker = report["docker"]
    if docker.get("built"):
        print(f"Docker image: {docker['image_size_mib']} MiB | "
              f"512m smoke: {docker.get('smoke_512m', 'not run')}")
    else:
        print(f"Docker: skipped ({docker.get('reason', 'unavailable')})")


def docker_failure(report: dict[str, Any]) -> str | None:
    """Return why the Docker evidence failed, or None when it passed/skipped.

    Args:
        report: The report returned by :func:`benchmark`.

    Returns:
        A short failure description, or None when Docker was skipped or the
        build and 512 MiB smoke test both passed.
    """
    docker = report.get("docker", {})
    if docker.get("skipped"):
        return None
    if not docker.get("available"):
        return str(docker.get("reason", "docker is unavailable"))
    if not docker.get("built"):
        detail = str(docker.get("reason", "")).strip().splitlines()
        return "docker build failed" + (f": {detail[-1]}" if detail else "")
    if docker.get("smoke_512m") != "passed":
        detail = str(docker.get("smoke_detail", "")).strip()
        return "docker smoke test failed" + (f": {detail}" if detail else "")
    return None


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the benchmark and write the report.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        The process exit code: nonzero when Docker was requested but the
        build or smoke test failed.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--iterations", type=int, default=30, help="measured passes (default: 30)"
    )
    parser.add_argument(
        "--json", type=Path, default=None, help="write the report as JSON"
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="skip the Docker evidence and exit zero",
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    skip_docker = args.skip_docker or args.no_docker
    report = benchmark(args.iterations, with_docker=not skip_docker)
    print_report(report)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nReport written to {args.json}")
    if not skip_docker:
        failure = docker_failure(report)
        if failure is not None:
            print(f"\nDocker evidence failed: {failure}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
