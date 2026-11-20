"""Deterministic local synthesis provider."""

from __future__ import annotations

import re
from collections.abc import Sequence

from backend.app.prompting import CANNOT_DETERMINE, Source


def _first_sentence(text: str) -> str:
    """Return the first sentence of ``text``.

    Args:
        text: The raw text.

    Returns:
        The first sentence.
    """
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return parts[0] if parts else text.strip()


def _preserves_case(token: str) -> bool:
    """Return True when a leading token should keep its casing.

    Args:
        token: The first token of a sentence.

    Returns:
        True for acronyms, tokens containing digits and the pronoun ``I``.
    """
    letters = [char for char in token if char.isalpha()]
    if any(char.isdigit() for char in token):
        return True
    if not letters or not all(char.isupper() for char in letters):
        return False
    return len(letters) > 1 or letters[0] == "I"


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
    token = sentence.split(maxsplit=1)[0]
    if _preserves_case(token):
        return f"Evidence suggests that {sentence}."
    return f"Evidence suggests that {sentence[0].lower()}{sentence[1:]}."


class LocalSynthProvider:
    """Compose deterministic, cited guidance from structured sources."""

    name = "local_synth"

    def answer(
        self,
        prompt: str,
        *,
        plain_language: bool = False,
        sources: Sequence[Source] | None = None,
    ) -> str:
        """Compose an answer from structured sources.

        Args:
            prompt: The grounded prompt (unused; ``sources`` carry the evidence).
            plain_language: Whether to shorten the answer.
            sources: The retrieved sources.

        Returns:
            The composed answer.
        """
        unique: dict[str, str] = {}
        for source in sources or ():
            if source.text:
                unique.setdefault(source.id, source.text)
        selected = list(unique.items())[:3]
        if not selected:
            return CANNOT_DETERMINE
        if plain_language:
            body = " ".join(
                _first_sentence(_reexpress(text)) for _, text in selected[:1]
            )
        else:
            body = " ".join(_reexpress(text) for _, text in selected)
        citations = ", ".join(source_id for source_id, _ in selected)
        return f"{body}\n\nSources: [{citations}]"
