"""Tests for provider precedence, lazy imports and local synthesis."""

from __future__ import annotations

import inspect
import sys

from backend.app.config import settings
from backend.app.llm.base import EchoProvider
from backend.app.llm.factory import build_provider
from backend.app.llm.local_synth import LocalSynthProvider

PROMPT = (
    "User question:\nWhat helps?\n\nCited sources:\n"
    "[seed-001] Purifiers: A HEPA purifier removes fine particles.\n"
    "[seed-002] Ventilation: Open windows at night.\n"
    "[seed-003] Masks: An N95 mask filters fine particles.\n\n"
    "Disclaimer: general information.\n"
)


def test_explicit_echo_provider() -> None:
    """``echo`` always yields the echo provider."""
    assert isinstance(build_provider("echo"), EchoProvider)


def test_gemini_precedence_when_key_set(monkeypatch: object) -> None:
    """A Gemini key selects the Gemini provider."""
    from backend.app.llm.gemini import GeminiProvider

    monkeypatch.setattr(settings, "gemini_api_key", "key")
    monkeypatch.setattr(settings, "openai_api_key", "key")

    assert isinstance(build_provider(), GeminiProvider)


def test_openai_compat_precedence_when_no_gemini(monkeypatch: object) -> None:
    """Without a Gemini key, an OpenAI key selects the compat provider."""
    from backend.app.llm.openai_compat import OpenAICompatProvider

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "key")

    assert isinstance(build_provider(), OpenAICompatProvider)


def test_local_synth_is_the_default(monkeypatch: object) -> None:
    """With no keys the local synthesis provider is used."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")

    assert isinstance(build_provider(), LocalSynthProvider)


def test_provider_name_reports_the_resolved_provider(monkeypatch: object) -> None:
    """``provider_name`` mirrors what ``build_provider`` selects."""
    from backend.app.llm.factory import provider_name

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert provider_name() == "local_synth"

    monkeypatch.setattr(settings, "gemini_api_key", "key")
    assert provider_name() == "gemini"

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "key")
    assert provider_name() == "openai-compat"

    assert provider_name("echo") == "echo"


def test_local_synth_composes_new_text() -> None:
    """The composer re-expresses sources and cites them."""
    provider = LocalSynthProvider()
    chunks = {
        "A HEPA purifier removes fine particles.",
        "Open windows at night.",
        "An N95 mask filters fine particles.",
    }

    answer = provider.answer(PROMPT)

    assert "Sources:" in answer
    assert "seed-001" in answer
    assert answer.strip() not in chunks
    assert "Evidence suggests that" in answer
    assert provider.answer(PROMPT) == answer


def test_plain_output_is_shorter_with_same_citations() -> None:
    """Plain mode shortens the body but keeps the citations."""
    provider = LocalSynthProvider()

    standard = provider.answer(PROMPT)
    plain = provider.answer(PROMPT, plain_language=True)

    assert len(plain) < len(standard)
    assert plain.split("Sources:")[-1] == standard.split("Sources:")[-1]


def test_remote_providers_pin_temperature() -> None:
    """Both remote providers request deterministic output."""
    from backend.app.llm import gemini, openai_compat

    assert "temperature=0" in inspect.getsource(gemini.GeminiProvider.answer)
    assert "temperature=0" in inspect.getsource(
        openai_compat.OpenAICompatProvider.answer
    )


def test_remote_imports_are_lazy() -> None:
    """Importing the provider modules does not import the SDKs."""
    assert "google.genai" not in sys.modules
    assert "openai" not in sys.modules
