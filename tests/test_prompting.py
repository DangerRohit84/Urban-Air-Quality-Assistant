"""Tests for prompt construction and shared refusal copy."""

from __future__ import annotations

from backend.app.models import AqiContext, Profile
from backend.app.prompting import (
    CANNOT_DETERMINE,
    DISCLAIMER,
    OUT_OF_DOMAIN,
    PLAIN_LANGUAGE,
    build_prompt,
)


def _profile() -> Profile:
    """Build a profile for prompt tests."""
    return Profile(
        user_id="u1",
        city="Delhi",
        climate_zone="north",
        children=True,
        elderly=False,
        respiratory=True,
        commute_mode="car",
        commute_km=10.0,
        cooking_fuel="wood",
        heating_type="none",
        budget_level="low",
        updated_at="t",
    )


def test_build_prompt_contains_question_profile_context_and_hits() -> None:
    """The prompt carries every grounding element."""
    context = AqiContext(
        user_id="u1",
        city="Delhi",
        band="Poor",
        value=250,
        pm25=120.0,
        pm10=200.0,
        season="winter",
        observed_at="t",
        source="user",
    )
    hits = [
        {
            "id": "seed-001",
            "title": "Purifiers",
            "text": "Use a HEPA purifier.",
            "score": 0.5,
            "source": "seed",
        },
        {
            "id": "seed-002",
            "title": "Ventilation",
            "text": "Ventilate at night.",
            "score": 0.4,
            "source": "seed",
        },
    ]

    prompt = build_prompt("Which purifier should I buy?", _profile(), context, hits)

    assert "Which purifier should I buy?" in prompt
    assert "Delhi" in prompt
    assert "Poor" in prompt
    assert "seed-001" in prompt
    assert "seed-002" in prompt
    assert DISCLAIMER in prompt


def test_plain_mode_adds_instruction() -> None:
    """Plain mode appends the plain-language instruction."""
    prompt = build_prompt("Question", _profile(), None, [], plain_language=True)

    assert PLAIN_LANGUAGE in prompt


def test_standard_mode_omits_plain_instruction() -> None:
    """Standard mode does not carry the plain-language instruction."""
    prompt = build_prompt("Question", _profile(), None, [])

    assert PLAIN_LANGUAGE not in prompt


def test_refusal_constants_are_non_empty() -> None:
    """The shared copy constants are populated."""
    assert DISCLAIMER.strip()
    assert CANNOT_DETERMINE.strip()
    assert OUT_OF_DOMAIN.strip()
