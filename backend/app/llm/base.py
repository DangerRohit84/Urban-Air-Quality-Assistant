"""LLM provider protocol and the tests-only echo provider."""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Port for answer providers."""

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Answer ``prompt``."""
        ...


class EchoProvider:
    """Return the prompt unchanged; used only by tests."""

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Return ``prompt``.

        Args:
            prompt: The prompt.
            plain_language: Ignored.

        Returns:
            The prompt.
        """
        return prompt
