"""OpenAI-compatible provider using a dependency-free HTTP call."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from backend.app.config import settings
from backend.app.llm.http_json import post_json
from backend.app.llm.local_synth import LocalSynthProvider
from backend.app.prompting import Source

logger = logging.getLogger(__name__)


def _local(
    prompt: str,
    plain_language: bool,
    sources: Sequence[Source] | None,
) -> str:
    """Return the deterministic local answer.

    Args:
        prompt: The grounded prompt.
        plain_language: Whether to request plain language.
        sources: The retrieved sources.

    Returns:
        The local answer.
    """
    return LocalSynthProvider().answer(
        prompt, plain_language=plain_language, sources=sources
    )


class OpenAICompatProvider:
    """Answer via an OpenAI-compatible chat endpoint."""

    name = "openai-compat"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """Store the endpoint settings.

        Args:
            api_key: The API key.
            base_url: The compatible endpoint.
            model: The model name.
        """
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self.model = model or settings.openai_model

    def answer(
        self,
        prompt: str,
        *,
        plain_language: bool = False,
        sources: Sequence[Source] | None = None,
    ) -> str:
        """Answer via the compatible endpoint, or fall back to local synthesis.

        Args:
            prompt: The grounded prompt.
            plain_language: Whether to request plain language.
            sources: The retrieved sources for the local fallback.

        Returns:
            The generated text, or a cited local answer when the request fails.
        """
        if not self.api_key:
            return _local(prompt, plain_language, sources)
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            data = post_json(url, payload, headers)
            text = data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - remote failures degrade locally
            logger.warning(
                "OpenAI-compatible request failed (%s); using local synthesis",
                type(exc).__name__,
            )
            return _local(prompt, plain_language, sources)
        if not isinstance(text, str) or not text.strip():
            logger.warning(
                "OpenAI-compatible endpoint returned no text; using local synthesis"
            )
            return _local(prompt, plain_language, sources)
        return text
