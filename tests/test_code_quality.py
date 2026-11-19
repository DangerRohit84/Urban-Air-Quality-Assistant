"""Static quality gates: module size, docstrings, hygiene and DIP ports."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "app"
MODULE_LINE_CAP = 150

SECRET_PATTERN = re.compile(
    r"\b(?:secret|api_key|apikey|password|passwd|token)\b"
    r'\s*[:=]\s*["\'][^"\']{8,}["\']',
    re.IGNORECASE,
)
FORBIDDEN_MARKERS = re.compile(r"\b(?:TODO|FIXME|HACK)\b")
SECTION_HEADERS = ("Args:", "Returns:", "Raises:")


def _backend_modules() -> list[Path]:
    """Return every backend module except the package markers.

    Returns:
        The sortable module paths.
    """
    return sorted(
        path
        for path in BACKEND.rglob("*.py")
        if path.name != "__init__.py"
    )


def _functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return every function and method in ``tree``.

    Args:
        tree: The parsed module.

    Returns:
        The function definition nodes.
    """
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def test_every_module_is_small() -> None:
    """Every backend module except ``__init__.py`` stays at or under 150 lines."""
    oversized = [
        f"{path.relative_to(ROOT)}: {len(path.read_text(encoding='utf-8').splitlines())}"
        for path in _backend_modules()
        if len(path.read_text(encoding="utf-8").splitlines()) > MODULE_LINE_CAP
    ]

    assert not oversized, f"modules over {MODULE_LINE_CAP} lines: {oversized}"


def test_dip_port() -> None:
    """The LLM and storage ports live in their own modules."""
    base = (BACKEND / "llm" / "base.py").read_text(encoding="utf-8")
    factory = (BACKEND / "llm" / "factory.py").read_text(encoding="utf-8")
    protocol = (BACKEND / "storage" / "protocol.py").read_text(encoding="utf-8")

    assert "class LLMProvider" in base
    assert "def build_provider" in factory
    assert "class Repository" in protocol


def test_every_module_has_a_docstring() -> None:
    """Every backend module starts with a docstring."""
    missing = []
    for path in _backend_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if ast.get_docstring(tree) is None:
            missing.append(str(path.relative_to(ROOT)))

    assert not missing, f"modules without a docstring: {missing}"


def test_every_function_has_a_docstring() -> None:
    """Every function and method carries a non-empty docstring."""
    missing = []
    for path in _backend_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _functions(tree):
            if not ast.get_docstring(node):
                missing.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}")

    assert not missing, f"functions without a docstring: {missing}"


def test_multiline_docstrings_use_google_style_sections() -> None:
    """Multi-line docstrings document arguments, returns or raised errors."""
    offenders = []
    for path in _backend_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _functions(tree):
            doc = ast.get_docstring(node) or ""
            if "\n" in doc and not any(
                header in doc for header in SECTION_HEADERS
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}")

    assert not offenders, f"docstrings without a section header: {offenders}"


def test_no_print_todos_or_hardcoded_secrets() -> None:
    """The backend has no debug prints, leftover markers or literal secrets."""
    offenders = []
    for path in _backend_modules():
        text = path.read_text(encoding="utf-8")
        if "print(" in text:
            offenders.append(f"{path.relative_to(ROOT)}: print()")
        marker = FORBIDDEN_MARKERS.search(text)
        if marker:
            offenders.append(f"{path.relative_to(ROOT)}: {marker.group(0)}")
        for match in SECRET_PATTERN.finditer(text):
            offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")

    assert not offenders, f"hygiene violations: {offenders}"
