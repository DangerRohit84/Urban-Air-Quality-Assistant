# Urban Air Quality Assistant — Design

Date: 2026-11-18
Status: approved-in-conversation, pending builder check

## Intent and why

Challenge #6 (Prompt Wars hackathon, pwvirtual1): a GenAI-powered assistant that helps families and communities navigate severe winter smog and urban air pollution. Required capabilities: (1) low-emission daily routines, (2) indoor air quality hacks, (3) sustainable alternatives to common activities, (4) clear explanation of the direct impact of each choice — tailored to the user's location and lifestyle.

Why now: winter smog episodes on the Indo-Gangetic plain create acute, repeated exposure events; families need personalized, actionable guidance, not generic lists. The AI evaluator (21-criterion analyzer + weighted synthesizer) rewards genuine computation (no facades), grounded and cited answers, complete implementation, strong tests, accessibility, real authentication, and explicit efficiency evidence. The sibling project (Celebration Event Planner) scored 96.87 with four fixable weaknesses: no authentication/ownership, an extractive-only default provider, a static corpus, and thin efficiency evidence. This design fixes all four by construction.

## Goals

- Full-stack app: FastAPI backend + vanilla HTML/CSS/JS frontend, SQLite persistence, zero new runtime dependencies beyond existing pins (stdlib crypto only).
- GenAI chain: Gemini (when key set) -> OpenAI-compatible (when key set) -> local synthesis (default, deterministic, genuinely composes new text) -> echo (tests only). Grounded answers with citations; out-of-domain refusal; plain-language mode (shorter, same citations).
- Personalization: user profile (city/climate zone; household: children, elderly, respiratory conditions; commute mode and distance; cooking fuel; heating; budget sensitivity) plus AQI context (band/value, season) producing tailored routines, indoor hacks, and alternatives.
- Impact engine: each recommendation carries quantified impact (kg CO2e per week, PM2.5 exposure reduction percent, monthly cost delta in INR) computed from a transparent, cited factor table.
- Live AQI: optional external provider (OpenWeather Air Pollution API) behind an env key; offline fallback is a user-entered AQI band. Approach C (offline-first, live enrichment).
- Authentication: email + password (PBKDF2-HMAC-SHA256, 120k iterations, per-user salt), HMAC-SHA256 signed bearer tokens (sub, exp; AUTH_SECRET env or per-boot secret with warning), constant-time comparison, generic 401s, owner-scoped data with 404 on cross-user access. Public: /health, static assets, register, login.
- Dynamic corpus: seeded knowledge base plus authenticated document management API (create/list/delete) and optional PDF upload into the corpus.
- Efficiency evidence: /health exposes cache stats, store counts, uptime; README carries a "Performance and resource bounds" section with measured claims; TF-IDF cached; bounded reads/parses; CPU-bound parse offloaded with asyncio.to_thread; LRU rate limiting.
- Quality bar: ruff and mypy clean, every backend module under 150 lines (enforced), pytest coverage gate at 76% (target 85%+), 200+ tests, docs-claims tests, zero warnings.

## Non-goals

- No mobile or native clients.
- No multi-tenant billing or SaaS features; single-instance demo deployment (Render free tier).
- No live AQI without a configured key (offline-first guarantee).
- No medical diagnosis; guidance is publicly sourced with a disclaimer.

## Anti-goals (failure even if it technically works)

- Hardcoded answers presented as computed (facade).
- Answers without grounding/citations.
- Authentication as a stub — ownership isolation must be real.
- UI that fails keyboard or screen-reader use.
- Documentation that drifts from the code.

## Constraints

- Python 3.11+, FastAPI, uvicorn; frontend served as static files.
- No new pip dependencies beyond the pinned set (stdlib for crypto) to keep pip-audit clean.
- Windows development environment (PowerShell); Linux deploy target (Render).
- Every backend module under 150 lines, enforced by test.
- pytest runs with zero warnings.

## Approaches considered

1. Air data — user-entered only (A): simplest, offline, no dependencies; trades away live authenticity.
2. Air data — live AQI API only (B): authentic but fragile (key, network, rate limits) and breaks the offline demo.
3. Air data — both, offline-first (C), CHOSEN: the user-entered band always works; when AQI_API_KEY is set the app fetches live AQI for the profile city and merges it. The provider sits behind a protocol with a mocked test. Rationale: the evaluator demo must never break, and the live path provides genuine external-integration evidence.
4. Stack — Next.js full-stack (heavier, new dependencies, slower to harden) and pure static site (no backend; fails GenAI/security criteria) were rejected. FastAPI + vanilla JS retained: it earned a perfect 21/21 analyzer score on the sibling project.

## Parts decided (the how)

### Repository layout
backend/app/ with packages: routes/, schemas/, storage/, llm/, retrieval/, plus domain modules (profile, aqi, impact, plans, prompting, auth/, security, config, main). frontend/ (index.html, app.js, styles.css, fonts/). tests/. docs/. scripts/check_quality.py. pyproject.toml, requirements.txt, Dockerfile, .env.example, README.md, docs/NARRATIVE.md, docs/DEPLOYMENT.md, docs/VIDEO_SCRIPT.md.

### Domain model
- User: id, email, password hash, salt, created_at.
- Profile: user_id, city, climate_zone, household flags (children, elderly, respiratory), commute_mode, commute_km, cooking_fuel, heating_type, budget_level.
- Document: id, owner_id, kind (seed|corpus|upload), title, text, chunks, source, created_at.
- AQI context: city, band, value, pm25, pm10, season, observed_at, source (user|live).

### API surface
- GET /health — status, provider, cache stats, store counts, uptime (performance fields).
- POST /auth/register, POST /auth/login, GET /auth/me.
- GET/PUT /profile.
- GET /air?q=<city> — live AQI when key configured, else 409/404-style graceful "not configured" with fallback hint; POST /air/context — store user-entered context.
- GET /plans?area=routines|hacks|alternatives — personalized, computed from profile + AQI context + corpus.
- POST /ask — grounded GenAI answer with citations; plain_language flag; out-of-domain refusal.
- POST /documents, GET /documents, DELETE /documents/{id}, POST /documents/upload (PDF) — owner-scoped, re-index on change.
- GET /export?format=md|json — export the current plan (grounded, owner-scoped).

### Impact engine
factors.py holds a transparent table of emission/exposure/cost factors per activity (commute modes, cooking fuels, heating, waste, etc.), each with a source note and an "approximate" flag. impact.py computes per-recommendation deltas (kg CO2e/week, exposure percent, INR/month) from the profile. Tests verify the arithmetic exactly.

### Auth
passwords.py (PBKDF2), tokens.py (HMAC-SHA256 sign/verify with exp), service.py (register/login/verify, generic errors), dependencies.py (Bearer extraction, current_user), routes/auth.py. Storage: users table; owner_id on profiles and documents; migration path for existing databases.

### GenAI
llm/base.py (provider protocol), llm/gemini.py, llm/openai_compat.py, llm/local_synth.py (deterministic composer: selects and reorders ranked chunks into new multi-sentence guidance with hedging and citations), llm/factory.py (precedence + config). prompting.py builds the grounded prompt (profile + AQI context + retrieved chunks + disclaimer + citation format). retrieval.py (TF-IDF with sklearn, cached) + retrieval_fallback.py (token overlap, zero-dep).

### Frontend
Auth card (register/login) gating the app; profile form; AQI context panel (band select + "fetch live" button when available); three plan sections (routines, indoor hacks, alternatives); impact panel (CO2e, exposure, cost); ask box with plain-language toggle; document library. Accessibility: labels with for/id, aria-describedby hints, aria-live status regions, focus management on load/errors, documented WCAG AA contrast, prefers-reduced-motion, keyboard-operable controls, textContent-only DOM writes.

### Efficiency
README "Performance and resource bounds" section with measured claims; /health metrics; cached TF-IDF (fit once per N searches); bounded reads (upload cap), bounded parse, LRU rate limiter with Retry-After, asyncio.to_thread for parse.

### Testing
Unit (impact math, AQI bands, tokens, passwords, retrieval, local synth), API (auth, profile, plans, ask, documents, boundaries: 401/404/409/413/422/429), accessibility (DOM parsing), security (isolation, tamper, enumeration, ownership), quality gates (SRP <150, docs claims, coverage), and a live smoke script.

## What is left to the builder

- Exact module split and naming (respecting the <150-line rule).
- Factor table values from public sources, each marked approximate with a source note.
- UI copy and visual polish within the accessibility constraints.
- Seed corpus content (cited air-quality guidance documents).
- Final call on PDF upload scope (recommended: include, small).

## Evaluator alignment (the four prior weaknesses, fixed by design)

| Prior weakness | This design |
|---|---|
| No authentication / shared database | Real auth + ownership isolation from day one |
| Extractive-only default provider | Local synthesis provider as the default (generative) |
| Static corpus | Seeded corpus + dynamic document API (+ upload) |
| Thin efficiency evidence | /health metrics + README performance section + measured claims |

## Risks

- Gemini key absent during demo: the local synthesis default must be genuinely useful (explicitly tested).
- Live AQI provider failure modes: protocol + offline fallback + mocked tests.
- Scope size: phased plan to follow (writing-plans), with the vertical slice (auth -> profile -> plans -> ask -> documents) built first.
