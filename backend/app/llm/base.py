"""LLM provider protocol and the tests-only echo provider."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from backend.app.prompting import Source


class LLMProvider(Protocol):
    """Port for answer providers."""

    name: str

    def answer(
        self,
        prompt: str,
        *,
        plain_language: bool = False,
        sources: Sequence[Source] | None = None,
    ) -> str:
        """Answer ``prompt``."""
        ...


class EchoProvider:
    """Return the prompt unchanged; used only by tests."""

    name = "echo"

    def answer(
        self,
        prompt: str,
        *,
        plain_language: bool = False,
        sources: Sequence[Source] | None = None,
    ) -> str:
        """Return ``prompt``.

        Args:
            prompt: The prompt.
            plain_language: Ignored.
            sources: Ignored.

        Returns:
            The prompt.
        """
        return prompt
