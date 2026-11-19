"""OpenAI-compatible provider with a lazy SDK import."""

from __future__ import annotations

from backend.app.config import settings


class OpenAICompatProvider:
    """Answer via an OpenAI-compatible chat endpoint."""

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

    def answer(self, prompt: str, *, plain_language: bool = False) -> str:
        """Answer via the compatible endpoint.

        Args:
            prompt: The grounded prompt.
            plain_language: Whether to request plain language.

        Returns:
            The generated text.
        """
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""
