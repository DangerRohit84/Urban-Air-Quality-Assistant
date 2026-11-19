"""Input sanitization helpers."""

from __future__ import annotations

import re

_UNSAFE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f<>\"'&]")


def sanitize_text(value: object, max_len: int = 2000) -> str:
    """Strip control characters and truncate ``value``.

    Args:
        value: The raw value.
        max_len: The maximum length.

    Returns:
        The sanitized text.
    """
    text = _UNSAFE.sub("", str(value))
    return text.strip()[:max_len]


def sanitize_filename(raw: str) -> str:
    """Reduce ``raw`` to a safe basename.

    Args:
        raw: The raw filename.

    Returns:
        The sanitized filename.
    """
    name = str(raw).replace("\\", "/").rsplit("/", 1)[-1]
    name = _UNSAFE.sub("", name).strip()[:120]
    return name or "upload.pdf"
