"""Deterministic local synthesis provider."""

from __future__ import annotations

import re

from backend.app.prompting import CANNOT_DETERMINE

_SOURCE_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.MULTILINE)


def _sources(prompt: str) -> list[tuple[str, str]]:
    """Extract cited sources from the prompt.

    Args:
        prompt: The prompt text.

    Returns:
        The (id, text) pairs.
    """
    section = prompt.split("Cited sources:", 1)[-1].split("Disclaimer:", 1)[0]
    pairs: list[tuple[str, str]] = []
    for match in _SOURCE_RE.finditer(section):
        text = match.group(2).strip()
        if ": " in text:
            text = text.split(": ", 1)[1]
        pairs.append((match.group(1), text))
    return pairs


def _first_sentence(text: str) -> str:
    """Return the first sentence of ``text``.

    Args:
        text: The raw text.

    Returns:
        The first sentence.
    """
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return parts[0] if parts else text.strip()


def _reexpress(text: str) -> str:
    """Re-express a source sentence with hedging.

    Args:
        text: The source sentence.

    Returns:
        The re-expressed sentence.
    """
    sentence = _first_sentence(text).rstrip(".")
    if not sentence:
        return ""
    return f"Evidence suggests that {sentence[0].lower()}{sentence[1:]}."


class LocalSynthProvider:
    """Compose deterministic, cited guidance from the prompt sources."""

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Compose an answer.

        Args:
            prompt: The grounded prompt.
            plain_language: Whether to shorten the answer.

        Returns:
            The composed answer.
        """
        unique: dict[str, str] = {}
        for source_id, text in _sources(prompt):
            unique.setdefault(source_id, text)
        selected = list(unique.items())[:3]
        if not selected:
            return CANNOT_DETERMINE
        if plain_language:
            body = " ".join(_first_sentence(_reexpress(text)) for _, text in selected[:1])
        else:
            body = " ".join(_reexpress(text) for _, text in selected)
        citations = ", ".join(source_id for source_id, _ in selected)
        return f"{body}\n\nSources: [{citations}]"
