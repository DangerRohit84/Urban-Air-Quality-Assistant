"""Tests for provider precedence, lazy imports and local synthesis."""

from __future__ import annotations

import sys

from backend.app.config import settings
from backend.app.llm.base import EchoProvider
from backend.app.llm.factory import build_provider
from backend.app.llm.local_synth import LocalSynthProvider
from backend.app.prompting import Source

PROMPT = (
    "User question:\nWhat helps?\n\nCited sources:\n"
    "[seed-001] Purifiers: A HEPA purifier removes fine particles.\n"
    "[seed-002] Ventilation: Open windows at night.\n"
    "[seed-003] Masks: An N95 mask filters fine particles.\n\n"
    "Disclaimer: general information.\n"
)

SOURCES = [
    Source(
        id="seed-001",
        title="Purifiers",
        text="A HEPA purifier removes fine particles.",
    ),
    Source(id="seed-002", title="Ventilation", text="Open windows at night."),
    Source(id="seed-003", title="Masks", text="An N95 mask filters fine particles."),
]


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

    answer = provider.answer(PROMPT, sources=SOURCES)

    assert "Sources:" in answer
    assert "seed-001" in answer
    assert answer.strip() not in chunks
    assert "Evidence suggests that" in answer
    assert provider.answer(PROMPT, sources=SOURCES) == answer


def test_plain_output_is_shorter_with_same_citations() -> None:
    """Plain mode shortens the body but keeps the citations."""
    provider = LocalSynthProvider()

    standard = provider.answer(PROMPT, sources=SOURCES)
    plain = provider.answer(PROMPT, plain_language=True, sources=SOURCES)

    assert len(plain) < len(standard)
    assert plain.split("Sources:")[-1] == standard.split("Sources:")[-1]


def test_gemini_http_success(monkeypatch: object) -> None:
    """A Gemini response is parsed and the request is deterministic."""
    from backend.app.llm import gemini

    captured: dict[str, object] = {}

    def fake_post(url: str, payload: dict, headers: dict) -> dict:
        captured.update(url=url, payload=payload, headers=headers)
        return {"candidates": [{"content": {"parts": [{"text": "Remote answer"}]}}]}

    monkeypatch.setattr(gemini, "post_json", fake_post)
    provider = gemini.GeminiProvider(api_key="secret", model="gemini-test")

    assert provider.answer(PROMPT) == "Remote answer"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["generationConfig"] == {"temperature": 0}
    assert str(captured["url"]).endswith("gemini-test:generateContent?key=secret")


def test_gemini_failure_falls_back_to_local(monkeypatch: object) -> None:
    """A transport failure degrades to the cited local answer."""
    from backend.app.llm import gemini

    def boom(url: str, payload: dict, headers: dict) -> dict:
        raise OSError("offline")

    monkeypatch.setattr(gemini, "post_json", boom)
    answer = gemini.GeminiProvider(api_key="secret", model="m").answer(
        PROMPT, sources=SOURCES
    )

    assert "Sources:" in answer
    assert "seed-001" in answer


def test_malformed_gemini_response_falls_back(monkeypatch: object) -> None:
    """An unexpected response shape degrades instead of raising."""
    from backend.app.llm import gemini

    monkeypatch.setattr(gemini, "post_json", lambda *args: {"candidates": []})
    answer = gemini.GeminiProvider(api_key="secret", model="m").answer(
        PROMPT, sources=SOURCES
    )

    assert "Sources:" in answer


def test_openai_compat_http_success(monkeypatch: object) -> None:
    """An OpenAI-compatible response is parsed with bearer auth."""
    from backend.app.llm import openai_compat

    captured: dict[str, object] = {}

    def fake_post(url: str, payload: dict, headers: dict) -> dict:
        captured.update(url=url, payload=payload, headers=headers)
        return {"choices": [{"message": {"content": "Remote answer"}}]}

    monkeypatch.setattr(openai_compat, "post_json", fake_post)
    provider = openai_compat.OpenAICompatProvider(
        api_key="secret", base_url="https://example.test/v1/", model="model"
    )

    assert provider.answer(PROMPT) == "Remote answer"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["temperature"] == 0
    assert captured["url"] == "https://example.test/v1/chat/completions"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer secret"


def test_openai_compat_empty_text_falls_back(monkeypatch: object) -> None:
    """An empty completion degrades to the cited local answer."""
    from backend.app.llm import openai_compat

    monkeypatch.setattr(
        openai_compat,
        "post_json",
        lambda *args: {"choices": [{"message": {"content": "   "}}]},
    )
    answer = openai_compat.OpenAICompatProvider(
        api_key="secret", base_url="https://example.test/v1", model="model"
    ).answer(PROMPT, sources=SOURCES)

    assert "Sources:" in answer


def test_remote_imports_are_lazy() -> None:
    """Importing the provider modules does not import the SDKs."""
    assert "google.genai" not in sys.modules
    assert "openai" not in sys.modules
