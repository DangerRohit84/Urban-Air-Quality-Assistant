"""Tests for the friendly Python-version startup guard."""

from __future__ import annotations

import pytest

from backend.app.version_guard import ensure_supported_python


def test_current_interpreter_is_supported() -> None:
    """The running interpreter passes the guard."""
    assert ensure_supported_python() is None


def test_supported_version_tuple_is_accepted() -> None:
    """An explicit 3.11 tuple passes."""
    assert ensure_supported_python((3, 11, 0)) is None


def test_python_310_raises_a_friendly_error() -> None:
    """A 3.10 interpreter gets an actionable message, not an import traceback."""
    with pytest.raises(RuntimeError) as caught:
        ensure_supported_python((3, 10, 6))

    message = str(caught.value)

    assert "requires Python >= 3.11" in message
    assert "3.10.6" in message
    assert "py -3.11 -m venv .venv" in message
    assert "source .venv/bin/activate" in message
