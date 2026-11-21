"""Tests that the documentation describes the code truthfully.

Every backticked repository path must exist, every environment variable read by
``config.py`` must be documented, and the quoted coverage floor, test count,
disclaimer and provider settings must match the code.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

from backend.app.llm.local_synth import LocalSynthProvider
from backend.app.prompting import DISCLAIMER, Source

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
NARRATIVE = ROOT / "docs" / "NARRATIVE.md"
DEPLOYMENT = ROOT / "docs" / "DEPLOYMENT.md"
PYPROJECT = ROOT / "pyproject.toml"
CONFIG = ROOT / "backend" / "app" / "config.py"
GEMINI = ROOT / "backend" / "app" / "llm" / "gemini.py"
OPENAI = ROOT / "backend" / "app" / "llm" / "openai_compat.py"

BACKTICKED = re.compile(r"`([^`]+)`")
PATH_LIKE = re.compile(r"^[\w.-]+(?:/[\w.-]+)+$")
KNOWN_SUFFIXES = (
    ".py",
    ".md",
    ".css",
    ".js",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".html",
)
ROOT_FILES = {"Dockerfile", "render.yaml", ".env.example", ".gitignore"}
PROMPT = (
    "User question:\nWhat helps?\n\nCited sources:\n"
    "[seed-001] Purifiers: A HEPA purifier removes fine particles.\n"
    "[seed-002] Ventilation: Open windows at night.\n\n"
    "Disclaimer: general information.\n"
)
SOURCES = [
    Source(
        id="seed-001",
        title="Purifiers",
        text="A HEPA purifier removes fine particles.",
    ),
    Source(id="seed-002", title="Ventilation", text="Open windows at night."),
]


def _documented_paths(text: str) -> list[str]:
    """Extract backticked repository paths from ``text``.

    Args:
        text: The documentation text.

    Returns:
        The candidate repository paths.
    """
    paths: list[str] = []
    for token in BACKTICKED.findall(text):
        token = token.strip()
        if not token or token.startswith("/") or " " in token or "?" in token:
            continue
        if token.startswith(("GET ", "POST ", "PUT ", "DELETE ")):
            continue
        if (
            token in ROOT_FILES
            or token.endswith(KNOWN_SUFFIXES)
            or PATH_LIKE.match(token)
        ):
            paths.append(token)
    return paths


def _read_env_names() -> list[str]:
    """Return every environment variable read by ``config.py``.

    Returns:
        The variable names.
    """
    text = CONFIG.read_text(encoding="utf-8")
    names = set(re.findall(r'_env_(?:str|int)\("([A-Z0-9_]+)"', text))
    names.update(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', text))
    return sorted(names)


def _collected_test_count() -> int:
    """Return the number of tests pytest collects.

    Returns:
        The collected test count.

    Raises:
        AssertionError: When collection fails or reports no count.
    """
    result = subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    match = re.search(r"(\d+) tests collected", output)
    assert match, output
    return int(match.group(1))


def test_documented_paths_exist() -> None:
    """Every backticked repository path in the docs exists."""
    missing = []
    for document in (README, NARRATIVE, DEPLOYMENT):
        for path in _documented_paths(document.read_text(encoding="utf-8")):
            if not (ROOT / path).exists():
                missing.append(f"{document.name}: {path}")

    assert not missing, f"documented paths that do not exist: {missing}"


def test_documented_uvicorn_commands_disable_proxy_headers() -> None:
    """Every runnable uvicorn command keeps ``--no-proxy-headers``."""
    sources = (README, DEPLOYMENT, ROOT / "Dockerfile")
    commands = [
        (source.name, line)
        for source in sources
        for line in source.read_text(encoding="utf-8").splitlines()
        if "uvicorn backend.app.main:app" in line
    ]

    assert commands, "no documented uvicorn command found"
    for name, line in commands:
        assert "--no-proxy-headers" in line, f"{name}: {line}"


def test_readme_documents_python_311_and_cross_platform_setup() -> None:
    """The quickstart names Python 3.11+ and shell-correct copy commands."""
    readme = README.read_text(encoding="utf-8")
    bare_unix_copy = [
        line
        for line in readme.splitlines()
        if line.strip() == "cp .env.example .env"
    ]

    assert "Python 3.11" in readme
    assert "py -3.11 -m venv .venv" in readme
    assert "copy .env.example .env" in readme
    assert "Copy-Item .env.example .env" in readme
    assert "cp .env.example .env" in readme
    assert not bare_unix_copy


def test_every_config_env_var_is_documented() -> None:
    """Every environment variable read by ``config.py`` appears in the guide."""
    text = DEPLOYMENT.read_text(encoding="utf-8")
    missing = [name for name in _read_env_names() if name not in text]

    assert not missing, f"undocumented environment variables: {missing}"


def test_coverage_floor_matches_pyproject() -> None:
    """The coverage floor quoted in the README equals ``fail_under``."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    floor = float(data["tool"]["coverage"]["report"]["fail_under"])
    match = re.search(
        r"coverage[^\n]*?(\d+(?:\.\d+)?)%",
        README.read_text(encoding="utf-8"),
        re.IGNORECASE,
    )

    assert match, "the README quotes no coverage percentage"
    assert float(match.group(1)) == floor


def test_test_count_matches_collection() -> None:
    """The test count quoted in the README and narrative matches pytest."""
    count = _collected_test_count()
    readme = README.read_text(encoding="utf-8")
    narrative = NARRATIVE.read_text(encoding="utf-8")

    assert f"{count} tests" in readme
    assert f"{count} tests" in narrative


def test_disclaimer_appears_verbatim() -> None:
    """The medical disclaimer is reproduced verbatim in the docs."""
    assert DISCLAIMER.strip()
    assert DISCLAIMER in README.read_text(encoding="utf-8")
    assert DISCLAIMER in NARRATIVE.read_text(encoding="utf-8")


def test_remote_providers_pin_temperature_zero() -> None:
    """Both remote providers request deterministic output."""
    assert '"temperature": 0' in GEMINI.read_text(encoding="utf-8")
    assert '"temperature": 0' in OPENAI.read_text(encoding="utf-8")


def test_plain_rendering_is_shorter_than_standard() -> None:
    """The plain-language mode shortens the composed answer."""
    provider = LocalSynthProvider()
    standard = provider.answer(PROMPT, sources=SOURCES)
    plain = provider.answer(PROMPT, plain_language=True, sources=SOURCES)

    assert len(plain) < len(standard)
