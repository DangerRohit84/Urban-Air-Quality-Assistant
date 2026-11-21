"""Fail fast with an actionable error on unsupported Python interpreters."""

from __future__ import annotations

import sys

MINIMUM_PYTHON = (3, 11)
_MINIMUM_LABEL = ".".join(str(part) for part in MINIMUM_PYTHON)


def _format(version: tuple[int, ...]) -> str:
    """Render a version tuple as ``major.minor.micro``.

    Args:
        version: The version tuple.

    Returns:
        The dotted version string.
    """
    return ".".join(str(part) for part in version)


def ensure_supported_python(version: tuple[int, ...] | None = None) -> None:
    """Raise a friendly error when the interpreter predates Python 3.11.

    Args:
        version: The version tuple to check; defaults to ``sys.version_info``.

    Raises:
        RuntimeError: When the interpreter is older than ``MINIMUM_PYTHON``.
    """
    current = (
        (
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        )
        if version is None
        else tuple(version)
    )
    if current < MINIMUM_PYTHON:
        raise RuntimeError(
            f"Urban Air Quality Assistant requires Python >= {_MINIMUM_LABEL}; "
            f"this interpreter is {_format(current)}. Recreate the virtual "
            "environment with a 3.11+ interpreter - on Windows run "
            "'py -3.11 -m venv .venv' and '.venv\\Scripts\\activate'; on "
            "macOS/Linux run 'python3.11 -m venv .venv' and "
            "'source .venv/bin/activate' - then reinstall requirements.txt."
        )
