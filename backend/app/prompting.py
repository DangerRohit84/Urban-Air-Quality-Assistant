"""Grounded prompt construction and shared refusal copy."""

from __future__ import annotations

from backend.app.models import AqiContext, Profile

DISCLAIMER = "This guidance is general information, not medical advice."
CANNOT_DETERMINE = "I cannot determine a reliable answer from the available sources."
OUT_OF_DOMAIN = "This question is outside the air-quality guidance corpus."
PLAIN_LANGUAGE = "Use plain language: short sentences and no jargon."


def build_prompt(
    question: str,
    profile: Profile,
    context: AqiContext | None,
    hits: list[dict],
    plain_language: bool = False,
) -> str:
    """Build the grounded prompt for an answer provider.

    Args:
        question: The user's question.
        profile: The user's profile.
        context: The optional air-quality context.
        hits: The retrieved documents.
        plain_language: Whether to request plain language.

    Returns:
        The prompt text.
    """
    lines = [
        "User question:",
        question,
        "",
        "Profile:",
        f"- city: {profile.city or 'unknown'}",
        f"- climate zone: {profile.climate_zone}",
        f"- commute: {profile.commute_mode}",
        f"- cooking fuel: {profile.cooking_fuel}",
        "- household: "
        f"children={profile.children}, respiratory={profile.respiratory}",
        "",
        "Air quality:",
        f"- band: {context.band if context else 'unknown'}",
        f"- city: {context.city if context else 'unknown'}",
        "",
        "Cited sources:",
    ]
    for hit in hits:
        lines.append(f"[{hit['id']}] {hit.get('title', '')}: {hit.get('text', '')}")
    lines += ["", f"Disclaimer: {DISCLAIMER}"]
    if plain_language:
        lines += ["", PLAIN_LANGUAGE]
    return "\n".join(lines)
