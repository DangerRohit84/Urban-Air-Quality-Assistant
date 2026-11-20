# Narrative - Urban Air Quality Assistant

## Problem

Winter smog on the Indo-Gangetic plain creates repeated, acute exposure events.
Families need guidance that reflects their city, household and budget, not a
generic list of tips that ignores where they live and what they can afford.

## Why this is better than a general AI answer

The assistant computes recommendations from a cited factor table and the user's
own profile, then quantifies the expected weekly CO2e reduction, exposure
reduction and monthly cost delta. Answers are grounded in a seeded, cited
corpus and the user's own documents; when nothing supports a question, the
assistant refuses instead of inventing a citation. Every recommendation carries
an `approximate` flag and a source note, so the numbers are transparent rather
than oracular.

## Trust design

- Real authentication and owner-scoped data; cross-user access returns 404.
- Generic 401s that never reveal whether an account exists.
- Passwords use PBKDF2-HMAC-SHA256 (600,000 iterations, 16-byte salt); bearer
  tokens are HMAC-SHA256 with an expiry. Unknown-email logins verify against a
  cached dummy hash so timing does not reveal account existence.
- Request bodies are capped at 1 MiB (uploads get the configured cap plus
  multipart headroom), validation errors never echo submitted input, and
  retrieved sources are escaped inside `<source>` delimiters.
- `/health` is exempt from rate limiting, and `TRUST_PROXY` enables
  first-hop-aware buckets behind a trusted proxy.
- Disclaimer: This guidance is general information, not medical advice.

## Gen AI usage

Provider precedence is Gemini, then an OpenAI-compatible endpoint, then a
deterministic local synthesis composer, with an echo provider used only by
tests. The local composer re-expresses cited sources, appends a `Sources:` list
and never fabricates citations. Plain-language mode shortens the answer while
keeping the same citations.

## What changed

The assistant ships a profile form, an AQI panel with live enrichment when a
key is configured, three ranked plan sections, an impact panel, a grounded ask
box with a plain-language toggle, and a document library with PDF upload. The
backend is layered around a repository port and provider ports, so the storage
backend and the model provider can be swapped without touching the routes.

## Tests

The suite collects **291 tests** (`pytest --collect-only`), including
accessibility, security-boundary, efficiency and docs-claims tests.

## What to link

- `README.md` - quickstart, architecture and API table.
- `docs/DEPLOYMENT.md` - environment variables and deployment.
- `docs/VIDEO_SCRIPT.md` - a two-minute walkthrough.
- `docs/superpowers/specs/2026-11-18-urban-air-quality-assistant-design.md` -
  the approved design.
