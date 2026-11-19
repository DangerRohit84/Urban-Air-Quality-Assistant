# Narrative - Urban Air Quality Assistant

## Problem

Winter smog on the Indo-Gangetic plain creates repeated, acute exposure events.
Families need guidance that reflects their city, household and budget, not a
generic list of tips.

## Why this is better than a general AI answer

The assistant computes recommendations from a cited factor table and the user's
own profile, then quantifies the expected weekly CO2e reduction, exposure
reduction and monthly cost delta. Answers are grounded in a seeded, cited
corpus and the user's own documents; when nothing supports a question, the
assistant refuses instead of inventing a citation.

## Trust design

- Real authentication and owner-scoped data; cross-user access returns 404.
- Generic 401s that never reveal whether an account exists.
- Every recommendation carries an `approximate` flag and a source note.
- Disclaimer: This guidance is general information, not medical advice.

## Gen AI usage

Provider precedence is Gemini, then an OpenAI-compatible endpoint, then a
deterministic local synthesis composer, with an echo provider used only by
tests. The local composer re-expresses cited sources, appends a `Sources:` list
and never fabricates citations.

## What changed

The assistant ships a profile form, an AQI panel with live enrichment when a
key is configured, three ranked plan sections, an impact panel, a grounded ask
box with a plain-language toggle, and a document library with PDF upload.

## Tests

The suite collects **246 tests** (`pytest --collect-only`).

## What to link

- `README.md` - quickstart and architecture.
- `docs/DEPLOYMENT.md` - environment variables and deployment.
- `docs/superpowers/specs/2026-11-18-urban-air-quality-assistant-design.md` -
  the approved design.
