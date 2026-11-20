"""Gemini provider using a dependency-free HTTP call."""

from __future__ import annotations

import logging
from urllib.parse import quote

from backend.app.config import settings
from backend.app.llm.http_json import post_json
from backend.app.llm.local_synth import LocalSynthProvider

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _local(prompt: str, plain_language: bool) -> str:
    """Return the deterministic local answer.

    Args:
        prompt: The grounded prompt.
        plain_language: Whether to request plain language.

    Returns:
        The local answer.
    """
    return LocalSynthProvider().answer(prompt, plain_language=plain_language)


class GeminiProvider:
    """Answer with Google Gemini when a key is configured."""

    name = "gemini"

    def __init__(
        self, api_key: str | None = None, model: str | None = None
    ) -> None:
        """Store the API key and model.

        Args:
            api_key: The Gemini API key.
            model: The model name.
        """
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Answer via Gemini, falling back to local synthesis on failure.

        Args:
            prompt: The grounded prompt.
            plain_language: Whether to request plain language.

        Returns:
            The generated text, or a cited local answer when the request fails.
        """
        if not self.api_key:
            return _local(prompt, plain_language)
        url = (
            f"{GEMINI_BASE_URL}/{quote(self.model, safe='')}"
            f":generateContent?key={quote(self.api_key, safe='')}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }
        try:
            data = post_json(url, payload, {})
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:  # noqa: BLE001 - remote failures degrade locally
            logger.warning(
                "Gemini request failed (%s); using local synthesis",
                type(exc).__name__,
            )
            return _local(prompt, plain_language)
        if not isinstance(text, str) or not text.strip():
            logger.warning("Gemini returned no text; using local synthesis")
            return _local(prompt, plain_language)
        return text
