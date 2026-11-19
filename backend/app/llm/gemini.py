"""Gemini provider with a lazy SDK import."""

from __future__ import annotations

from backend.app.config import settings


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
        """Answer via Gemini.

        Args:
            prompt: The grounded prompt.
            plain_language: Whether to request plain language.

        Returns:
            The generated text.
        """
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(temperature=0)
        response = client.models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return response.text or ""
