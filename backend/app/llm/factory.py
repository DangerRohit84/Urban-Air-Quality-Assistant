"""Provider selection precedence."""

from __future__ import annotations

from backend.app.config import settings
from backend.app.llm.base import EchoProvider, LLMProvider
from backend.app.llm.local_synth import LocalSynthProvider


def build_provider(provider: str | None = None) -> LLMProvider:
    """Build a provider from the name and configured keys.

    Precedence: an explicit ``echo``; the requested remote provider when its
    key is set; otherwise Gemini, then OpenAI-compatible, then local
    synthesis.

    Args:
        provider: An explicit provider name.

    Returns:
        The provider instance.
    """
    name = (provider or settings.llm_provider or "local_synth").strip().lower()
    if name == "echo":
        return EchoProvider()
    if name == "gemini":
        if settings.gemini_api_key:
            from backend.app.llm.gemini import GeminiProvider

            return GeminiProvider()
        return LocalSynthProvider()
    if name == "openai-compat":
        if settings.openai_api_key:
            from backend.app.llm.openai_compat import OpenAICompatProvider

            return OpenAICompatProvider()
        return LocalSynthProvider()
    if settings.gemini_api_key:
        from backend.app.llm.gemini import GeminiProvider

        return GeminiProvider()
    if settings.openai_api_key:
        from backend.app.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider()
    return LocalSynthProvider()


def provider_name(provider: str | None = None) -> str:
    """Return the name of the provider ``build_provider`` selects.

    Args:
        provider: An optional explicit provider name.

    Returns:
        The resolved provider name, taken from the same factory the routes use.
    """
    return build_provider(provider).name
