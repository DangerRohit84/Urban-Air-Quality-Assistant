# Urban Air Quality Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + vanilla-JS assistant that turns a user's city, household and lifestyle profile plus CPCB AQI context into personalized low-emission routines, indoor air hacks, sustainable alternatives, quantified impact, and grounded cited answers.

**Architecture:** Layered: `routes/` thin adapters depend on domain modules (`profile`, `aqi`, `impact`, `plans`, `prompting`, `retrieval`, `llm/`, `auth/`, `air/`), which depend on the `storage/` repository protocol; SQLite and the in-memory test double both implement that protocol (DIP). The LLM and live-AQI integrations sit behind provider protocols selected by `llm/factory.py` and `air/provider.py`, so offline local synthesis is the default and remote keys are optional. The frontend is static HTML/CSS/JS served by FastAPI and calls the JSON API with a Bearer token.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, SQLite (stdlib sqlite3), scikit-learn (TF-IDF), pypdf, vanilla HTML/CSS/JS, pytest, ruff, mypy, pip-audit.

**Spec:** docs/superpowers/specs/2026-11-18-urban-air-quality-assistant-design.md

## Global Constraints (exact values, verbatim from spec)

- Every backend module <150 lines, enforced by test (no exemptions except `__init__.py`; `main.py` stays <150 by composition).
- pytest runs with zero warnings (`filterwarnings = ["error", ...]`, with one documented third-party TestClient deprecation ignore).
- ruff and mypy clean.
- Coverage gate >=76% (target 85%+); 200+ tests; docs-claims tests.
- No new pip dependencies beyond the pinned set; stdlib for crypto (`hashlib`, `hmac`, `os.urandom`).
- CPCB AQI bands: 0–50 Good, 51–100 Satisfactory, 101–200 Moderately Polluted, 201–300 Poor, 301–400 Very Poor, 401–500 Severe.
- Owner-scoped data: profiles, AQI context, documents (`owner_id` on every row).
- Provider precedence: Gemini -> OpenAI-compat -> local synthesis -> echo (echo is tests-only, never the default).
- Offline-first live AQI: the user-entered band always works; live fetch only when `AQI_API_KEY` is set, with graceful fallback.
- HMAC-SHA256 bearer tokens (payload `sub` + `exp`, base64url, constant-time compare).
- PBKDF2-HMAC-SHA256, 120,000 iterations, 16-byte per-user salt.
- Generic 401s: `{"detail": "invalid credentials"}` for every auth failure (missing, malformed, tampered, expired, unknown user).
- Cross-user access returns 404 (never 403/401/200).
- `textContent`-only DOM writes (no `innerHTML`, `insertAdjacentHTML`, `outerHTML`).
- `/health` exposes provider, cache stats, store counts, uptime.

## Review Focus

Five input classes/failure modes the spec implies but tasks might not exercise. Each has a required behavior and a regression test; add the test in the named task.

1. **Empty profile** (registered user, no `PUT /profile` yet). `GET /profile` -> 404 `{"detail":"profile not found"}`. `GET /plans` and `POST /ask` must not 500: they call `load_profile_or_default(user_id)` (city `""`, `climate_zone="north"`, all household flags false, `commute_mode="bus"`, `commute_km=0.0`, `cooking_fuel="lpg"`, `heating_type="none"`, `budget_level="medium"`) and return 200 with a "set your profile" note. Test: `tests/test_profile.py::test_missing_profile_is_404_and_defaults_are_safe` (T7).
2. **Unknown city**. `GET /air?q=Atlantis` -> 404 `{"detail":"unknown city"}` with a `fallback` hint; `POST /air/context` with a city outside the coordinates table -> 422. Never 500. Test: `tests/test_air_api.py::test_unknown_city_is_404` (T8).
3. **Malformed / tampered / expired token**. Missing header, `Bearer` with no token, `Bearer garbage`, a valid payload with one flipped signature character, and an expired token all -> 401 `{"detail":"invalid credentials"}` with an identical body and no stack trace. Unknown-email login and wrong-password login return the same 401 body (no enumeration). Test: `tests/test_auth.py::test_token_failures_are_generic_401` (T5).
4. **Empty corpus search / out-of-domain question**. `search("the and of to")` -> `[]` (stop-word-only query has no signal). `POST /ask` whose retrieval returns no hits -> refusal text, `citations: []`, `grounded: false`; it must never emit a fabricated citation. Tests: `tests/test_retrieval.py::test_stop_word_query_returns_empty` (T11) and `tests/test_ask.py::test_out_of_domain_refuses_without_citations` (T13).
5. **Concurrent writes**. Two simultaneous `PUT /profile` (same user) and two `POST /documents` (different users) via `ThreadPoolExecutor` must never 500: SQLite runs in WAL mode with `busy_timeout=5000`, and the profile row uses `INSERT ... ON CONFLICT(user_id) DO UPDATE`. Owner isolation holds after the race, and the retrieval cache is invalidated by owner on every document change. Tests: `tests/test_storage.py::test_concurrent_writes_do_not_500` (T3) and `tests/test_documents_api.py::test_document_race_keeps_owner_isolation` (T12).

Pinned boundary codes: wrong PDF magic -> 400; oversize upload -> 413; rate limit -> 429 with `Retry-After`; duplicate register -> 409; unknown document -> 404.

## File Structure

Every file to create, with its one-line responsibility. The split is locked so the SRP test (`<=150` lines, `__init__.py` exempt) passes; `main.py` stays under 150 by moving middleware into `middleware.py`, metrics into `metrics.py`, and health into `routes/system.py`.

```
backend/app/
  __init__.py          — package marker.
  config.py            — Settings dataclass: env parsing, db_path, allowed_origins.
  errors.py            — install_error_handlers: ValueError -> 400/409, generic 500, HTTPException passthrough.
  middleware.py        — security headers + sliding-window LRU rate limiter + Retry-After + X-Process-Time.
  metrics.py           — provider name, cache stats, store counts, uptime for /health.
  models.py            — User, Profile, Document, AqiContext dataclasses + serialization.
  profile.py           — Profile defaults, enum validation, normalize_profile.
  aqi.py               — CPCB band table, band_for_value, band_from_pm25, band_from_openweather_index.
  cities.py            — major-Indian-city coordinates table + resolve_city.
  factors.py           — impact Factor dataclass + FACTORS table (source-noted, approximate flags).
  impact.py            — Impact dataclass + compute_impact / impact_for_recommendation / exposure_multiplier.
  routines.py          — low-emission daily routine recommendations.
  hacks.py             — indoor air-quality hacks.
  alternatives.py      — sustainable alternatives to common activities.
  plans.py             — Recommendation/PlansPayload types + build_plans orchestration + ranking.
  prompting.py         — DISCLAIMER, CANNOT_DETERMINE, OUT_OF_DOMAIN, build_prompt.
  chunking.py          — chunk_text with bounded overlap.
  corpus.py            — load_seed_corpus + assemble_corpus (seed + owner docs only).
  retrieval.py         — search() orchestration, top_k clamp, signal guard.
  retrieval_index.py   — cached TF-IDF index (fit once per corpus, cache stats).
  retrieval_fallback.py— zero-dependency stop-word + token-overlap ranker.
  upload_guard.py      — PDF magic bytes, size cap, content-type allowlist.
  security.py          — sanitize_text, sanitize_filename.
  main.py              — create_app() composition root (<150 lines) + static frontend mount.
  auth/
    __init__.py        — package marker.
    passwords.py       — PBKDF2 hash/verify, email/password validation, dummy_hash.
    tokens.py          — HMAC-SHA256 sign/verify with exp, get_secret.
    service.py         — register_user / authenticate with generic errors.
    dependencies.py    — bearer_token, require_user_id, current_user, load_profile_or_default.
  llm/
    __init__.py        — package marker.
    base.py            — LLMProvider protocol + EchoProvider (tests only).
    gemini.py          — GeminiProvider (lazy google-genai import).
    openai_compat.py   — OpenAICompatProvider (lazy openai import).
    local_synth.py     — LocalSynthProvider deterministic composer.
    factory.py         — build_provider precedence.
  air/
    __init__.py        — package marker.
    provider.py        — LiveAqiProvider protocol + LiveAqiReading + City.
    openweather.py     — OpenWeather Air Pollution adapter.
  storage/
    __init__.py        — re-exports.
    protocol.py        — Repository Protocol.
    schema.py          — SCHEMA_V1 DDL + table list.
    migrations.py      — apply_migrations (PRAGMA user_version 0 -> 1).
    sqlite_base.py     — connect() with WAL, foreign_keys, busy_timeout.
    memory.py          — InMemoryRepo.
    sqlite_store.py    — SQLiteRepo.
    store.py           — build_repo / get_repo / reset_repo.
  routes/
    __init__.py        — merge routers.
    system.py          — GET /health.
    auth.py            — POST /auth/register, POST /auth/login, GET /auth/me.
    profile.py         — GET/PUT /profile.
    air.py             — GET /air, POST /air/context.
    plans.py           — GET /plans.
    ask.py             — POST /ask.
    documents.py       — POST/GET/DELETE /documents, POST /documents/upload.
    export.py          — GET /export?format=md|json.
  schemas/
    __init__.py        — re-exports.
    auth.py            — RegisterRequest, LoginRequest, TokenResponse.
    profile.py         — ProfileResponse, ProfileUpdate.
    air.py             — AirContextIn, AirContextResponse, AirLiveResponse.
    documents.py       — DocumentIn, DocumentResponse.
    ask.py             — AskIn, AskResponse.
    plans.py           — RecommendationOut, PlansResponse.
    health.py          — HealthResponse.
frontend/
  index.html           — app shell: auth card, profile form, AQI panel, plan sections, impact panel, ask box, document library, live regions.
  styles.css           — layout + documented WCAG AA contrast + 44px targets + prefers-reduced-motion.
  app.js               — API client, rendering, event wiring (textContent-only).
tests/
  conftest.py          — env setup, repo reset, authed client fixture.
  test_scaffold.py, test_config.py, test_health.py, test_middleware.py, test_errors.py,
  test_storage.py, test_passwords.py, test_tokens.py, test_auth.py, test_boundaries.py,
  test_profile.py, test_aqi.py, test_air_api.py, test_impact.py, test_plans.py,
  test_retrieval.py, test_documents_api.py, test_prompting.py, test_llm_providers.py,
  test_ask.py, test_frontend_a11y.py, test_frontend_features.py, test_code_quality.py,
  test_docs_claims.py, test_quality_gates.py, test_efficiency.py, test_export.py, test_security.py.
scripts/
  check_quality.py     — ruff + mypy + pytest + coverage gate runner.
  smoke.py             — live smoke matrix against a base URL.
backend/data/
  seed_corpus.json     — >=8 cited seed documents.
data/                  — runtime SQLite (gitignored).
docs/
  NARRATIVE.md, DEPLOYMENT.md, VIDEO_SCRIPT.md.
pyproject.toml, requirements.txt, .env.example, .gitignore, Dockerfile, README.md, render.yaml.
```

## Tasks

### Phase 0 — Foundation

#### T1 — Project scaffold

**Files:** `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`, `Dockerfile`, `scripts/check_quality.py`, `README.md` (skeleton), `backend/app/__init__.py`, `tests/__init__.py`.

**Interfaces:**
- `scripts/check_quality.py`: `read_coverage_floor(pyproject: Path = PYPROJECT) -> float`, `run(step: str, command: list[str]) -> tuple[bool, str]`, `parse_total_coverage(output: str) -> float | None`, `main() -> int`.
- `pyproject.toml` keys: `[tool.pytest.ini_options] testpaths=["tests"]`, `addopts="--strict-markers --strict-config"`, `filterwarnings=["error", ...]`; `[tool.coverage.report] fail_under=76`; `[tool.ruff] line-length=88`; `[tool.mypy] files=["backend/app"]`, `disallow_untyped_defs=true`.

**Steps:**
- [ ] Write `tests/test_scaffold.py` asserting: `pyproject.toml` contains `fail_under = 76` and a `filterwarnings` list containing `error`; `requirements.txt` pins `fastapi==`, `pypdf==`, `scikit-learn==`, `pytest==`, `ruff==`, `mypy==`; `.env.example` contains `AUTH_SECRET=`, `AQI_API_KEY=`, `LLM_PROVIDER=`; `.gitignore` contains `.env`, `data/`, `.venv`; `Dockerfile` contains `HEALTHCHECK` and `/health`; `scripts/check_quality.py` exists; `read_coverage_floor()` returns `76.0`. Run `python -m pytest tests/test_scaffold.py -q` -> fail (files missing).
- [ ] Create `pyproject.toml` with pytest/ruff/mypy/coverage config. Use `filterwarnings = ["error", "ignore:Using `httpx` with `starlette\\.testclient` is deprecated:starlette.exceptions.StarletteDeprecationWarning"]` (the single documented third-party TestClient deprecation; no blanket suppression).
- [ ] Create `requirements.txt` (pinned freeze; versions carried from the sibling project's audited set), `.env.example` (`LLM_PROVIDER=local_synth`, `GEMINI_API_KEY=`, `OPENAI_API_KEY=`, `OPENAI_BASE_URL=`, `AQI_API_KEY=`, `STORE_BACKEND=sqlite`, `DATABASE_URL=sqlite:///./data/air.db`, `AUTH_SECRET=`, `FRONTEND_ORIGIN=http://localhost:8000`, `RATE_LIMIT_PER_MIN=200`, `MAX_RATE_BUCKETS=10000`, `MAX_UPLOAD_BYTES=10485760`, `MAX_DOCUMENTS=10`, `PORT=8000`, `LOG_LEVEL=info`), `.gitignore`, `Dockerfile` (python:3.11-slim, non-root `appuser`, `HEALTHCHECK ... /health`, `CMD uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}`), `backend/app/__init__.py`, `tests/__init__.py`.
- [ ] Create `scripts/check_quality.py` implementing ruff, mypy, pytest, and the coverage floor; when `backend/app` contains no `*.py` modules the coverage gate prints `skipped (no backend modules)` and does not fail.
- [ ] Create the `README.md` skeleton with the required headings (`Performance and resource bounds`, `Tests`, `Project layout`) and a placeholder test count that T17 replaces.
- [ ] Run `python -m pytest -q` -> pass; run `python scripts/check_quality.py` -> `QUALITY GATE PASSED`.
- [ ] Commit: `git add -A; git commit -m "chore: scaffold Urban Air Quality Assistant"`.

#### T2 — Config + app shell

**Files:** `backend/app/config.py`, `backend/app/errors.py`, `backend/app/middleware.py`, `backend/app/metrics.py`, `backend/app/routes/system.py`, `backend/app/schemas/health.py`, `backend/app/main.py`, `tests/test_config.py`, `tests/test_health.py`, `tests/test_middleware.py`, `tests/test_errors.py`.

**Interfaces:**
- `config.Settings` fields: `llm_provider: str`, `gemini_api_key: str`, `gemini_model: str`, `openai_api_key: str`, `openai_base_url: str`, `openai_model: str`, `aqi_api_key: str`, `store_backend: str`, `database_url: str`, `auth_secret: str`, `frontend_origin: str`, `rate_limit_per_min: int = 200`, `max_rate_buckets: int = 10000`, `max_upload_bytes: int = 10485760`, `max_documents: int = 10`, `port: int = 8000`, `log_level: str = "info"`; properties `db_path: Path`, `allowed_origins: list[str]`; module-level `settings = Settings()`.
- `errors.install_error_handlers(app: FastAPI) -> None`.
- `middleware.security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response`; `middleware.rate_limit(request: Request) -> None`; `middleware._attach_headers(resp: Response, request: Request, start: float, limited: bool = False) -> None`.
- `metrics.health_snapshot() -> dict[str, object]` -> `{"provider": str, "cache": {...}, "store": {...}, "uptime_seconds": float}`.
- `main.create_app() -> FastAPI`; `main.app = create_app()`.
- `GET /health` -> `200 {"status":"ok","provider":...,"cache":...,"store":...,"uptime_seconds":...}`.

**Steps:**
- [ ] Write `tests/test_config.py`: `settings.db_path` resolves `sqlite:///./data/air.db` to `data/air.db`; `allowed_origins` drops `*` and malformed entries; `rate_limit_per_min` parses an int env var with default 200; `aqi_api_key` defaults to `""`; `llm_provider` defaults to `local_synth`.
- [ ] Write `tests/test_health.py`: `GET /health` -> 200; body has `status == "ok"`, `provider` in `{"gemini","openai-compat","local_synth","echo"}`, `cache` has `hits`/`misses`/`size`, `store` has `users`/`profiles`/`documents`, `uptime_seconds >= 0`; response time < 1.0s.
- [ ] Write `tests/test_middleware.py`: every response (200/404/500) carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Content-Security-Policy`, `Permissions-Policy`, `Strict-Transport-Security`, `Cache-Control: no-store`, `X-Process-Time`; a 200 carries `X-RateLimit-Limit`/`Remaining`/`Reset`; after `RATE_LIMIT_PER_MIN+1` requests the next is 429 with `Retry-After: 60` and `X-RateLimit-Remaining: 0`; an unhandled exception yields a bare `500 {"detail":"Internal server error"}` that still carries the header set; rate-limit buckets are keyed on `request.client.host` (proxy headers ignored).
- [ ] Write `tests/test_errors.py`: unknown route -> 404 JSON; a handler raising `ValueError` -> 400; a handler raising `HTTPException(409)` -> 409; no traceback text in any error body.
- [ ] Run `python -m pytest tests/test_config.py tests/test_health.py tests/test_middleware.py tests/test_errors.py -q` -> fail (modules missing).
- [ ] Implement `config.py`, `errors.py`, `middleware.py` (sliding window, 60s window, LRU eviction at `max_rate_buckets`, `Retry-After: 60`), `metrics.py`, `routes/system.py`, `schemas/health.py`, and `main.py` (`create_app` wires CORS allowlist, error handlers, middleware, router, static mount; stays <150 lines).
- [ ] Run the four test modules -> pass; run `python -m pytest -q` -> pass.
- [ ] Commit: `feat: config, security middleware, health metrics, app shell`.

#### T3 — Storage layer

**Files:** `backend/app/storage/__init__.py`, `protocol.py`, `schema.py`, `migrations.py`, `sqlite_base.py`, `memory.py`, `sqlite_store.py`, `store.py`, `tests/test_storage.py`.

**Interfaces:**
- `protocol.Repository` (`typing.Protocol`) methods:
  - `ensure_schema() -> None`
  - `create_user(email: str, password_hash: str) -> User`
  - `get_user_by_email(email: str) -> User | None`
  - `get_user_by_id(user_id: str) -> User | None`
  - `save_profile(profile: Profile) -> Profile`
  - `get_profile(user_id: str) -> Profile | None`
  - `save_aqi_context(ctx: AqiContext) -> AqiContext`
  - `get_aqi_context(user_id: str) -> AqiContext | None`
  - `create_document(doc: Document) -> Document`
  - `list_documents(owner_id: str) -> list[Document]`
  - `get_document(doc_id: str) -> Document | None`
  - `delete_document(doc_id: str, owner_id: str) -> bool`
  - `count_documents(owner_id: str) -> int`
  - `close() -> None`
- `schema.SCHEMA_V1: str` (DDL for `users`, `profiles`, `documents`, `aqi_context`).
- `migrations.apply_migrations(conn: sqlite3.Connection) -> int` (returns the resulting `PRAGMA user_version`).
- `sqlite_base.connect(db_path: Path) -> sqlite3.Connection` (WAL, `foreign_keys=ON`, `busy_timeout=5000`).
- `memory.InMemoryRepo() -> Repository`; `sqlite_store.SQLiteRepo(db_path: Path) -> Repository`.
- `store.build_repo() -> Repository`; `store.get_repo() -> Repository`; `store.reset_repo(repo: Repository | None = None) -> None`.

**Steps:**
- [ ] Write `tests/test_storage.py`: schema v1 creates the four tables and sets `PRAGMA user_version == 1`; migrating a `user_version=0` database applies v1 exactly once (idempotent; a second call is a no-op); user round-trip (`create_user` -> `get_user_by_email` -> `get_user_by_id`); profile upsert (`save_profile` twice -> one row, latest wins); aqi_context round-trip; document create/list/get/delete with `owner_id` filtering; `delete_document` for another owner returns `False` and leaves the row; memory repo parity with the SQLite repo on the same operation script.
- [ ] Write `tests/test_storage.py::test_concurrent_writes_do_not_500`: a `ThreadPoolExecutor(4)` runs `save_profile` (same user) and `create_document` (two users) 20 times; assert no exception, the final profile is one of the written values, and per-owner document counts are exact.
- [ ] Run `python -m pytest tests/test_storage.py -q` -> fail.
- [ ] Implement `schema.py` with DDL:
  - `users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)`
  - `profiles(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, city TEXT NOT NULL DEFAULT '', climate_zone TEXT NOT NULL, children INTEGER NOT NULL DEFAULT 0, elderly INTEGER NOT NULL DEFAULT 0, respiratory INTEGER NOT NULL DEFAULT 0, commute_mode TEXT NOT NULL, commute_km REAL NOT NULL DEFAULT 0, cooking_fuel TEXT NOT NULL, heating_type TEXT NOT NULL, budget_level TEXT NOT NULL, updated_at TEXT NOT NULL)`
  - `documents(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, kind TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL, chunks TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL)`
  - `aqi_context(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, city TEXT NOT NULL, band TEXT NOT NULL, value INTEGER, pm25 REAL, pm10 REAL, season TEXT NOT NULL, observed_at TEXT NOT NULL, source TEXT NOT NULL)`
- [ ] Implement `migrations.py`, `sqlite_base.py`, `memory.py`, `sqlite_store.py`, `store.py`; `Repository` is a `Protocol` so both backends are substitutable (DIP).
- [ ] Run `python -m pytest tests/test_storage.py -q` -> pass; run the full suite -> pass.
- [ ] Commit: `feat: sqlite schema v1, repository protocol, memory + sqlite stores`.

### Phase 1 — Auth

#### T4 — Passwords + tokens

**Files:** `backend/app/auth/__init__.py`, `passwords.py`, `tokens.py`, `tests/test_passwords.py`, `tests/test_tokens.py`.

**Interfaces:**
- `passwords.normalize_email(email: str) -> str` (raises `ValueError("invalid email address")`).
- `passwords.validate_password(password: str) -> None` (raises `ValueError`; 8–128 chars, >=1 letter, >=1 digit).
- `passwords.hash_password(password: str) -> str` -> `"<32 hex salt>$<64 hex digest>"`.
- `passwords.verify_password(password: str, stored: str) -> bool` (constant-time; `False` on malformed stored).
- `passwords.dummy_hash() -> str`.
- `tokens.get_secret() -> str` (AUTH_SECRET, else a per-boot `secrets.token_urlsafe(32)` with one warning).
- `tokens.create_token(user_id: str, ttl_seconds: int = 86_400) -> str`.
- `tokens.verify_token(token: str) -> str | None`.

**Steps:**
- [ ] Write `tests/test_passwords.py`: `hash_password` output matches `^[0-9a-f]{32}\$[0-9a-f]{64}$`; two hashes of the same password differ; `verify_password(pw, hash_password(pw)) is True`; wrong password `False`; malformed stored `"nope"` -> `False`; `normalize_email(" A@B.COM ") == "a@b.com"`; bad email raises; `"short1"`, `"allletters"`, `"12345678"` raise; an 8-char alphanumeric password passes; the source contains `hmac.compare_digest` and `120_000`.
- [ ] Write `tests/test_tokens.py`: `create_token("u1")` -> `verify_token` returns `"u1"`; the token has exactly one `.`; flipping one signature character -> `None`; flipping one payload character -> `None`; `create_token("u1", ttl_seconds=-1)` -> `verify_token` `None`; `"garbage"`, `""`, `"a.b.c"` -> `None`; two tokens for the same user differ; `get_secret()` returns `AUTH_SECRET` when set.
- [ ] Run `python -m pytest tests/test_passwords.py tests/test_tokens.py -q` -> fail.
- [ ] Implement `passwords.py` (stdlib `hashlib.pbkdf2_hmac("sha256", ..., 120_000)`, `os.urandom(16)`, `hmac.compare_digest`) and `tokens.py` (base64url JSON `{"sub","exp"}`, HMAC-SHA256, `hmac.compare_digest`).
- [ ] Run the two modules -> pass; full suite -> pass.
- [ ] Commit: `feat: pbkdf2 password hashing and hmac bearer tokens`.

#### T5 — Auth service + routes

**Files:** `backend/app/auth/service.py`, `dependencies.py`, `backend/app/routes/auth.py`, `backend/app/schemas/auth.py`, `tests/test_auth.py`, `tests/conftest.py`.

**Interfaces:**
- `service.register_user(email: str, password: str) -> tuple[User, str]` (raises `ValueError` on bad email, weak password, or duplicate).
- `service.authenticate(email: str, password: str) -> tuple[User, str] | None`.
- `dependencies.bearer_token(request: Request) -> str` (raises `HTTPException(401, "invalid credentials")`).
- `dependencies.require_user_id(request: Request) -> str`.
- `dependencies.current_user(request: Request) -> User`.
- `POST /auth/register` body `{email, password}` -> `201 {"user":{"id","email","created_at"},"token"}`.
- `POST /auth/login` -> `200 {"user":{...},"token"}`.
- `GET /auth/me` (Bearer) -> `200 {"id","email","created_at"}`.

**Steps:**
- [ ] Write `tests/test_auth.py`: register -> 201 with a token; duplicate email -> 409; weak password -> 422; malformed email -> 422; login correct -> 200; login wrong password -> 401 `{"detail":"invalid credentials"}`; login unknown email -> 401 with the *same* body as wrong password (enumeration); `GET /auth/me` with token -> 200; without token -> 401; with `Bearer garbage` -> 401; with a tampered token -> 401; with an expired token -> 401; `/health` is public (200 without a token).
- [ ] Write `tests/conftest.py`: set `AUTH_SECRET` and `LLM_PROVIDER=local_synth` before importing the app; autouse fixtures reset the repo to `InMemoryRepo` and reset the retrieval cache; a `client` fixture returns `TestClient(app)`; an `auth_headers` fixture registers `test@example.com`/`TestPass123` and returns `{"Authorization": "Bearer <token>"}`.
- [ ] Run `python -m pytest tests/test_auth.py -q` -> fail.
- [ ] Implement `schemas/auth.py`, `service.py` (duplicate -> `ValueError("email already registered")`; unknown email runs `verify_password` against `dummy_hash()`), `dependencies.py`, and `routes/auth.py` (map `ValueError` to 409/422 via `errors.py`).
- [ ] Run `tests/test_auth.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: register/login/me with generic 401s and authed fixture`.

#### T6 — Protect data endpoints + authed test fixture; 401/404 semantics

**Files:** `backend/app/access.py`, `backend/app/routes/profile.py` (protected `GET /profile` -> 404 when absent), `backend/app/schemas/profile.py` (response type), `tests/test_boundaries.py`.

**Interfaces:**
- `access.owner_or_404(repo: Repository, resource: Owned, user_id: str) -> Owned` (raises `HTTPException(404, "not found")` when `resource.owner_id != user_id`).
- `access.get_owned_document(repo: Repository, doc_id: str, user_id: str) -> Document`.
- `access.get_owned_profile(repo: Repository, user_id: str) -> Profile | None`.
- `GET /profile` (Bearer) -> `200 ProfileResponse` or `404 {"detail":"profile not found"}`.

**Steps:**
- [ ] Write `tests/test_boundaries.py`: `GET /profile` without a token -> 401; with a token and no profile -> 404 `{"detail":"profile not found"}`; `access.owner_or_404` returns the resource for the owner and raises 404 for another user; `get_owned_document` returns 404 for another owner's document id; no response leaks another user's id.
- [ ] Run `python -m pytest tests/test_boundaries.py -q` -> fail.
- [ ] Implement `access.py`, the protected `GET /profile` route wired with `Depends(require_user_id)`, and the profile response schema.
- [ ] Run `tests/test_boundaries.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: ownership helper and protected profile read with 404 semantics`.

### Phase 2 — Domain + GenAI

#### T7 — Profile

**Files:** `backend/app/models.py` (Profile), `backend/app/profile.py`, `backend/app/schemas/profile.py` (add `ProfileUpdate`), `backend/app/routes/profile.py` (add PUT), `tests/test_profile.py`.

**Interfaces:**
- `models.Profile` dataclass: `user_id: str`, `city: str`, `climate_zone: str`, `children: bool`, `elderly: bool`, `respiratory: bool`, `commute_mode: str`, `commute_km: float`, `cooking_fuel: str`, `heating_type: str`, `budget_level: str`, `updated_at: str`.
- `profile.DEFAULT_PROFILE: Profile` (city `""`, `climate_zone="north"`, flags `False`, `commute_mode="bus"`, `commute_km=0.0`, `cooking_fuel="lpg"`, `heating_type="none"`, `budget_level="medium"`).
- `profile.normalize_profile(data: dict) -> Profile` (raises `ValueError`); enums: `climate_zone in {"north","south","east","west","central","hilly"}`, `commute_mode in {"walk","cycle","two_wheeler","car","bus","metro","train","work_from_home"}`, `cooking_fuel in {"lpg","png","electric","biogas","wood","kerosene","coal"}`, `heating_type in {"none","electric_heater","gas_heater","blowers","solar","wood_burner"}`, `budget_level in {"low","medium","high"}`; `city` 1–80 chars; `commute_km` 0–200.
- `dependencies.load_profile_or_default(repo: Repository, user_id: str) -> Profile`.
- `PUT /profile` body `ProfileUpdate` -> `200 ProfileResponse`; `GET /profile` -> `200` or `404`.

**Steps:**
- [ ] Write `tests/test_profile.py`: PUT a valid profile -> 200 and GET round-trips every field; `commute_mode="rocket"` -> 422; `commute_km=-1` -> 422; `commute_km=201` -> 422; empty `city` -> 422; `budget_level="gold"` -> 422; GET before PUT -> 404 `{"detail":"profile not found"}`; user A's profile is invisible to user B; `load_profile_or_default` returns the default for a user with no row; `GET /plans` and `POST /ask` with no profile -> 200 (no 500) and include a "set your profile" note.
- [ ] Run `python -m pytest tests/test_profile.py -q` -> fail.
- [ ] Implement `models.Profile`, `profile.py`, `schemas/profile.py`, `dependencies.load_profile_or_default`, and the `PUT /profile` route (`save_profile` upsert).
- [ ] Run `tests/test_profile.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: profile model, validation, GET/PUT /profile with owner scope`.

#### T8 — AQI

**Files:** `backend/app/aqi.py`, `cities.py`, `models.py` (AqiContext), `air/__init__.py`, `air/provider.py`, `air/openweather.py`, `schemas/air.py`, `routes/air.py`, `tests/test_aqi.py`, `tests/test_air_api.py`.

**Interfaces:**
- `aqi.Band` dataclass: `name: str`, `low: int`, `high: int`, `color: str`, `advice: str`.
- `aqi.CPCB_BANDS: tuple[Band, ...]` in order: Good(0,50), Satisfactory(51,100), Moderately Polluted(101,200), Poor(201,300), Very Poor(301,400), Severe(401,500).
- `aqi.band_for_value(value: int) -> Band` (clamps >500 to Severe, <0 to Good).
- `aqi.band_from_pm25(pm25: float) -> Band` (CPCB 24-h PM2.5 breakpoints: 0–30 Good, 31–60 Satisfactory, 61–90 Moderately Polluted, 91–120 Poor, 121–250 Very Poor, >250 Severe).
- `aqi.band_from_openweather_index(index: int) -> Band` (1->Good, 2->Satisfactory, 3->Moderately Polluted, 4->Poor, 5->Very Poor; out-of-range -> `ValueError`).
- `cities.resolve_city(name: str) -> City | None`; `City` dataclass `name: str, lat: float, lon: float`; table includes at least Delhi, Mumbai, Bengaluru, Chennai, Kolkata, Hyderabad, Pune, Ahmedabad, Jaipur, Lucknow, Chandigarh, Patna, Bhopal, Indore, Guwahati, Srinagar, Shimla, Kochi, Thiruvananthapuram, Bhubaneswar.
- `air.provider.LiveAqiProvider` Protocol: `fetch(city: City) -> LiveAqiReading`.
- `air.provider.LiveAqiReading` dataclass: `band: Band`, `value: int | None`, `pm25: float | None`, `pm10: float | None`, `source: str = "live"`.
- `air.openweather.OpenWeatherProvider(api_key: str, *, base_url: str = "https://api.openweathermap.org/data/2.5/air-pollution", client: object | None = None)`.
- `routes.air.get_live_reading(city: City) -> LiveAqiReading | None` (None when `AQI_API_KEY` is unset or the fetch raises).
- `POST /air/context` body `AirContextIn` -> `200 AirContextResponse` (owner-scoped).
- `GET /air?q=<city>` -> `200 {"city","source":"live"|"not_configured","band","value","pm25","pm10","fallback"}` or `404 {"detail":"unknown city"}`.

**Steps:**
- [ ] Write `tests/test_aqi.py`: band boundaries `0,50 -> Good`, `51,100 -> Satisfactory`, `101,200 -> Moderately Polluted`, `201,300 -> Poor`, `301,400 -> Very Poor`, `401,500 -> Severe`, `501 -> Severe`, `-5 -> Good`; `band_from_pm25` boundaries `30,31,60,61,90,91,120,121,250,251`; `band_from_openweather_index` mapping; invalid index raises; `resolve_city("delhi")` and `resolve_city("Delhi ")` hit, `resolve_city("Atlantis")` is None.
- [ ] Write `tests/test_air_api.py`: POST `/air/context` with a valid band -> 200 and `GET /air?q=<city>` reflects it; `GET /air?q=Delhi` with no `AQI_API_KEY` -> 200 `source == "not_configured"` and a non-empty `fallback`; with `AQI_API_KEY` set and a mocked provider returning index 4 / pm25 150 -> `source == "live"`, `band == "Poor"`; provider raising -> graceful `not_configured` (never 500); unknown city -> 404; context is owner-scoped (user B's `GET /air?q=` returns B's context or not_configured, never A's band); invalid band -> 422; invalid season -> 422.
- [ ] Run `python -m pytest tests/test_aqi.py tests/test_air_api.py -q` -> fail.
- [ ] Implement `aqi.py`, `cities.py`, `air/provider.py`, `air/openweather.py` (5s timeout, parse `list[0].main.a` and `components`), `schemas/air.py`, `routes/air.py`.
- [ ] Run the two modules -> pass; full suite -> pass.
- [ ] Commit: `feat: CPCB bands, city table, live AQI provider with offline fallback`.

#### T9 — Impact engine

**Files:** `backend/app/factors.py`, `backend/app/impact.py`, `tests/test_impact.py`.

**Interfaces:**
- `factors.Factor` dataclass: `key: str`, `category: str`, `co2e_per_week_kg: float`, `exposure_reduction_pct: float`, `cost_delta_inr_month: float`, `source: str`, `approximate: bool`.
- `factors.FACTORS: dict[str, Factor]` with at least `commute.walk`, `commute.cycle`, `commute.two_wheeler`, `commute.car`, `commute.bus`, `commute.metro`, `commute.train`, `commute.work_from_home`, `cooking.lpg`, `cooking.png`, `cooking.electric`, `cooking.biogas`, `cooking.wood`, `cooking.kerosene`, `cooking.coal`, `heating.none`, `heating.electric_heater`, `heating.gas_heater`, `heating.blowers`, `heating.solar`, `heating.wood_burner`, `waste.burn`, `waste.compost`.
- `impact.Impact` dataclass: `co2e_kg_week: float`, `exposure_reduction_pct: float`, `cost_delta_inr_month: float`.
- `impact.compute_impact(profile: Profile, action_key: str, baseline_key: str, context: AqiContext | None = None) -> Impact` (delta = action factor − baseline factor; raises `ValueError` on unknown key).
- `impact.impact_for_recommendation(profile: Profile, recommendation: Recommendation, context: AqiContext | None) -> Impact`.
- `impact.exposure_multiplier(context: AqiContext | None) -> float` (Good 0.5, Satisfactory 0.75, Moderately Polluted 1.0, Poor 1.25, Very Poor 1.5, Severe 2.0; default 1.0).

**Steps:**
- [ ] Write `tests/test_impact.py` with exact arithmetic: `compute_impact(profile{car, 10 km}, "commute.bus", "commute.car")` -> `co2e_kg_week == (0.20 - 0.05) * 10 * 2 * 5 == 15.0`; `compute_impact(profile{wood}, "cooking.lpg", "cooking.wood")` -> `co2e_kg_week == (1.2 - 2.5) * 7 == -9.1`; `cost_delta_inr_month` and `exposure_reduction_pct` match the table exactly; unknown key raises `ValueError`; every `Factor` has a non-empty `source` and `approximate is True`; `exposure_multiplier` returns the band table; `impact_for_recommendation` uses the recommendation's action/baseline keys.
- [ ] Run `python -m pytest tests/test_impact.py -q` -> fail.
- [ ] Implement `factors.py` (per-km commute factors: car 0.20, two_wheeler 0.09, bus 0.05, metro 0.03, train 0.04, walk/cycle/work_from_home 0.0; per-day cooking factors: wood 2.5, coal 3.0, kerosene 2.0, lpg 1.2, png 1.1, electric 0.8, biogas 0.6; per-day heating factors: wood_burner 3.0, gas_heater 1.5, electric_heater 1.2, blowers 0.8, solar 0.2, none 0.0; each `approximate=True` with a source note) and `impact.py` (pure functions, no I/O).
- [ ] Run `tests/test_impact.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: cited impact factor table and exact impact arithmetic`.

#### T10 — Plans engine

**Files:** `backend/app/plans.py`, `routines.py`, `hacks.py`, `alternatives.py`, `schemas/plans.py`, `routes/plans.py`, `routes/export.py`, `tests/test_plans.py`, `tests/test_export.py`.

**Interfaces:**
- `plans.Recommendation` dataclass: `key: str`, `area: str`, `title: str`, `detail: str`, `action_key: str`, `baseline_key: str`, `impact: Impact`, `citations: list[str]`, `approximate: bool`.
- `plans.PlansPayload` dataclass: `routines: list[Recommendation]`, `hacks: list[Recommendation]`, `alternatives: list[Recommendation]`, `profile_note: str`.
- `routines.build_routines(profile: Profile, context: AqiContext | None, hits: list[dict]) -> list[Recommendation]`.
- `hacks.build_hacks(profile: Profile, context: AqiContext | None, hits: list[dict]) -> list[Recommendation]`.
- `alternatives.build_alternatives(profile: Profile, context: AqiContext | None, hits: list[dict]) -> list[Recommendation]`.
- `plans.rank(items: list[Recommendation], profile: Profile) -> list[Recommendation]` (sort by `impact.co2e_kg_week` desc, then `exposure_reduction_pct` desc, then `key` asc; stable).
- `plans.build_plans(profile: Profile, context: AqiContext | None, hits: list[dict]) -> PlansPayload`.
- `GET /plans?area=routines|hacks|alternatives` (Bearer) -> `200 PlansResponse` (filtered when `area` is given).

**Steps:**
- [ ] Write `tests/test_plans.py`: a profile with `commute_mode="car"`, `children=True`, `respiratory=True`, `cooking_fuel="wood"`, `budget_level="low"` and a Poor-band context produces >=3 routines, >=3 hacks, >=3 alternatives; routines mention the commute mode; hacks mention children/respiratory; alternatives mention the cooking fuel; ranking is descending by `co2e_kg_week`; every recommendation has an `Impact` and >=1 citation; `build_plans` with a default/empty profile still returns a 200-shaped payload with a "set your profile" note; unknown `area` -> 422; `GET /plans` without a token -> 401; owner scope (A's plans differ from B's when profiles differ).
- [ ] Run `python -m pytest tests/test_plans.py -q` -> fail.
- [ ] Write `tests/test_export.py`: `GET /export?format=json` with a token returns the caller's plans payload (routines/hacks/alternatives present, owner-scoped); `format=md` contains the three section headings and the profile note; another user's export differs when profiles differ; no token -> 401; unknown format -> 422.
- [ ] Implement `routes/export.py`: `GET /export?format=md|json` (Bearer) reusing `build_plans` for the caller; json serializes `PlansPayload`, md renders headings + recommendations + citations.
- [ ] Implement `routines.py`, `hacks.py`, `alternatives.py` (each selects from `FACTORS` and `hits`, and sets each recommendation's `action_key`/`baseline_key` from `FACTORS`), `plans.py` (orchestration + ranking), `schemas/plans.py`, `routes/plans.py`.
- [ ] Run `tests/test_plans.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: personalized routines, hacks, alternatives with ranking`.

#### T11 — Retrieval

**Files:** `backend/app/chunking.py`, `corpus.py`, `retrieval.py`, `retrieval_index.py`, `retrieval_fallback.py`, `backend/data/seed_corpus.json`, `tests/test_retrieval.py`.

**Interfaces:**
- `chunking.chunk_text(text: str, size: int = 400, overlap: int = 80) -> list[str]`.
- `corpus.load_seed_corpus() -> list[Document]`.
- `corpus.assemble_corpus(repo: Repository, owner_id: str) -> list[Document]` (seed docs + that owner's docs only).
- `retrieval.search(query: str, top_k: int = 5, owner_id: str | None = None) -> list[dict]` (each hit has `id`, `title`, `text`, `score`, `source`).
- `retrieval.get_cache_stats() -> dict` (`hits`, `misses`, `size`).
- `retrieval.reset_cache() -> None`.
- `retrieval_index._get_index(corpus: list[Document]) -> tuple[object, object, list[dict]]`.
- `retrieval_fallback._has_signal(query: str) -> bool`; `retrieval_fallback._rank_by_token_overlap(corpus: list[dict], query: str, top_k: int) -> list[dict]`.

**Steps:**
- [ ] Write `tests/test_retrieval.py`: the seed corpus loads >=8 cited documents; `chunk_text` produces overlapping chunks and never exceeds `size`; `search("indoor air purifier")` returns >=1 hit with `score` in (0,1]; `top_k` clamps to 1..10 (`search(q, top_k=100)` returns <=10); a stop-word-only query -> `[]`; an empty corpus -> `[]`; per-owner isolation (a document created by user A is retrievable by A and absent from B's results); cache stats increment on repeat queries and `reset_cache()` zeroes them; the fallback stop-word set matches `sklearn.feature_extraction.text.ENGLISH_STOP_WORDS`; the fallback ranks a token-overlap query above an unrelated one.
- [ ] Run `python -m pytest tests/test_retrieval.py -q` -> fail.
- [ ] Implement `chunking.py`, `corpus.py`, `retrieval_index.py` (fit `TfidfVectorizer(stop_words="english")` once per `(owner_id, corpus_hash)`, cache with stats), `retrieval_fallback.py` (zero-dep), and `retrieval.py` (signal guard -> assemble -> TF-IDF -> fallback).
- [ ] Add `backend/data/seed_corpus.json` with >=8 cited air-quality guidance documents.
- [ ] Run `tests/test_retrieval.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: TF-IDF retrieval with zero-dep fallback and per-owner cache`.

#### T12 — Documents API

**Files:** `backend/app/upload_guard.py`, `security.py`, `schemas/documents.py`, `routes/documents.py`, `tests/test_documents_api.py`.

**Interfaces:**
- `upload_guard.PDF_MAGIC = b"%PDF-"`; `upload_guard.ALLOWED_CONTENT_TYPES = {"application/pdf","application/octet-stream"}`.
- `upload_guard.validate_pdf_magic(raw: bytes | bytearray) -> bool` (raises `TypeError`/`ValueError`).
- `upload_guard.validate_pre_parse(filename: str, content_type: str, size: int, data: bytes) -> bool` (raises `ValueError`).
- `security.sanitize_text(value: object, max_len: int = 2000) -> str`; `security.sanitize_filename(raw: str) -> str`.
- `routes.documents.extract_pdf_text(data: bytes) -> str` (pypdf, bounded pages, runs in `asyncio.to_thread`).
- `POST /documents` body `{title, text}` -> `201 DocumentResponse`.
- `GET /documents` -> `200 list[DocumentResponse]`.
- `DELETE /documents/{id}` -> `204`; another owner -> `404`.
- `POST /documents/upload` multipart `file` -> `201 DocumentResponse`.

**Steps:**
- [ ] Write `tests/test_documents_api.py`: create -> 201 with chunks; list returns only the owner's docs; delete own -> 204 and it disappears; delete another owner's -> 404; create with empty title/text -> 422; upload a valid small PDF -> 201 and extracted text is searchable; upload non-PDF magic -> 400; upload > `max_upload_bytes` -> 413; upload with a `.txt` name -> 400; exceeding `MAX_DOCUMENTS` -> 409; after create/delete the owner's retrieval cache is invalidated (search reflects the change); concurrent uploads by two users keep owner isolation.
- [ ] Run `python -m pytest tests/test_documents_api.py -q` -> fail.
- [ ] Implement `upload_guard.py`, `security.py`, `schemas/documents.py`, `routes/documents.py` (bounded read of `max_upload_bytes + 1`, `asyncio.to_thread(extract_pdf_text)`, re-index via per-owner cache invalidation).
- [ ] Run `tests/test_documents_api.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: owner-scoped document API with PDF upload and re-index`.

#### T13 — Prompting + LLM

**Files:** `backend/app/prompting.py`, `llm/__init__.py`, `base.py`, `gemini.py`, `openai_compat.py`, `local_synth.py`, `factory.py`, `schemas/ask.py`, `routes/ask.py`, `tests/test_prompting.py`, `tests/test_llm_providers.py`, `tests/test_ask.py`.

**Interfaces:**
- `prompting.DISCLAIMER: str`; `prompting.CANNOT_DETERMINE: str`; `prompting.OUT_OF_DOMAIN: str`.
- `prompting.build_prompt(question: str, profile: Profile, context: AqiContext | None, hits: list[dict], plain_language: bool = False) -> str`.
- `llm.base.LLMProvider` Protocol: `answer(prompt: str, *, plain_language: bool = False) -> str`.
- `llm.base.EchoProvider` (tests only).
- `llm.gemini.GeminiProvider()`, `llm.openai_compat.OpenAICompatProvider()`, `llm.local_synth.LocalSynthProvider()`.
- `llm.factory.build_provider(provider: str | None = None) -> LLMProvider` (explicit `echo` -> Echo; `gemini` when `GEMINI_API_KEY`; `openai-compat` when `OPENAI_API_KEY`; else `LocalSynthProvider`).
- `POST /ask` body `{question: str, plain_language: bool = False}` -> `200 {"answer": str, "citations": list[str], "mode": "standard"|"plain", "grounded": bool}`.

**Steps:**
- [ ] Write `tests/test_prompting.py`: `build_prompt` contains the question, the profile city, the context band, every hit id, and `DISCLAIMER`; plain mode adds the plain-language instruction.
- [ ] Write `tests/test_llm_providers.py`: `build_provider("echo")` is `EchoProvider`; with `GEMINI_API_KEY` set -> `GeminiProvider`; else with `OPENAI_API_KEY` -> `OpenAICompatProvider`; else -> `LocalSynthProvider`; `LocalSynthProvider().answer(prompt)` returns text that is not a verbatim copy of any chunk, contains `Sources:`, and is deterministic across two calls; plain output is shorter than standard with identical citations; both remote providers pin `temperature=0`; imports are lazy.
- [ ] Write `tests/test_ask.py`: `/ask` without a token -> 401; with a grounded question -> 200, `citations` non-empty, `grounded is True`, the answer contains a citation id; `plain_language=true` -> `mode == "plain"` and the answer is shorter; an out-of-domain question with no hits -> refusal, `citations == []`, `grounded is False`; empty question -> 422; owner scope (A's documents do not ground B's answer).
- [ ] Run `python -m pytest tests/test_prompting.py tests/test_llm_providers.py tests/test_ask.py -q` -> fail.
- [ ] Implement `prompting.py`, `llm/base.py`, `llm/local_synth.py` (deterministic composer: dedupe, select top-3, re-express with hedging, append `Sources: [id, ...]`), `llm/gemini.py`, `llm/openai_compat.py`, `llm/factory.py`, `schemas/ask.py`, `routes/ask.py`.
- [ ] Run the three modules -> pass; full suite -> pass.
- [ ] Commit: `feat: grounded prompting, provider precedence, /ask with citations and refusal`.

### Phase 3 — Frontend + Ship

#### T14 — Frontend shell

**Files:** `frontend/index.html`, `frontend/styles.css`, `frontend/app.js` (scaffold), `tests/test_frontend_a11y.py`.

**Interfaces:**
- DOM ids: `auth-card`, `register-form`, `login-form`, `profile-form`, `status`, `errors`, `aqi-band`, `fetch-live`, `plans`, `impact`, `ask-form`, `q`, `plain`, `answer`, `answerMode`, `citations`, `documents`, `docfile`, `uploadBtn`, `uploadStatus`.
- `app.js` scaffold defines `apiFetch(path, options)`, `showStatus(msg)`, `showError(msg)`, `focusErrors()`; no `innerHTML`/`insertAdjacentHTML`/`outerHTML`; uses `textContent`/`createElement`.

**Steps:**
- [ ] Write `tests/test_frontend_a11y.py`: every `input`/`select`/`textarea` has an `id` and a `<label for>`; every control has `aria-describedby` pointing at an existing id; `#status` has `role="status"` and `aria-live="polite"`; `#errors` has `role="alert"`, `aria-live="assertive"`, `tabindex="-1"`; `#answer` has `aria-live="polite"`; skip link `href="#main"`; landmarks `banner`/`main`/`contentinfo`; `<noscript>`; CSS documents `CONTRAST RATIOS` with `4.5:1` and `3:1`, `--border-strong`, `min-height: 44px`/`min-width: 44px` for interactive elements, and a `@media (prefers-reduced-motion: reduce)` block; `app.js` has no `innerHTML`/`insertAdjacentHTML`/`outerHTML` and does use `textContent`.
- [ ] Run `python -m pytest tests/test_frontend_a11y.py -q` -> fail.
- [ ] Implement `index.html` (auth card gating the app, profile form, AQI panel, three plan sections, impact panel, ask box with plain toggle, document library, live regions), `styles.css` (layout, AA contrast, 44px targets, reduced motion), and the `app.js` scaffold with `apiFetch`, status/error helpers, and focus management.
- [ ] Run `tests/test_frontend_a11y.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: accessible frontend shell with auth card and profile form`.

#### T15 — Frontend features

**Files:** `frontend/app.js` (wiring), `frontend/index.html` (feature markup), `frontend/styles.css`, `tests/test_frontend_features.py`.

**Interfaces:**
- `app.js` functions: `loadProfile()`, `saveProfile()`, `loadAir()`, `fetchLiveAqi()`, `loadPlans(area)`, `renderPlans(data)`, `renderImpact(impact)`, `askQuestion()`, `loadDocuments()`, `uploadDocument()`.
- `index.html` ids: `plans-routines`, `plans-hacks`, `plans-alternatives`, `impact-co2e`, `impact-exposure`, `impact-cost`, `docs-list`, `askBtn`, `exportBtn`.

**Steps:**
- [ ] Write `tests/test_frontend_features.py` (stdlib `HTMLParser`): `aqi-band` is a `<select>` with the six CPCB band names as `<option>`s; `fetch-live` exists and its handler calls `/air?q=`; `renderPlans` populates all three sections from the `/plans` payload; `renderImpact` writes `impact-co2e`, `impact-exposure`, `impact-cost` via `textContent`; `askQuestion` sends `{question, plain_language}` and reads `#plain`.checked; `loadDocuments`/`uploadDocument` target `/documents` and `/documents/upload`; `exportBtn` targets `/export?format=md`; no `innerHTML` anywhere; every dynamic region has a live region.
- [ ] Run `python -m pytest tests/test_frontend_features.py -q` -> fail.
- [ ] Implement the wiring in `app.js` (fetch with the Bearer token from `sessionStorage`, render with `createElement`/`textContent`, announce via `#status`, focus `#errors` on failure), and add the feature markup/CSS.
- [ ] Run `tests/test_frontend_features.py` and `tests/test_frontend_a11y.py` -> pass; full suite -> pass.
- [ ] Commit: `feat: AQI panel, plan sections, impact panel, ask box, document library wiring`.

#### T16 — Quality gates

**Files:** `tests/test_code_quality.py`, `tests/test_docs_claims.py`, `tests/test_quality_gates.py`, `scripts/check_quality.py` (extend), `tests/test_efficiency.py`.

**Interfaces:**
- `test_code_quality.py::test_every_module_is_small`: every `backend/app/**/*.py` except `__init__.py` has `<= 150` lines (no `main.py` exemption).
- `test_code_quality.py::test_dip_port`: `llm/base.py` defines `LLMProvider`; `llm/factory.py` defines `build_provider`; `storage/protocol.py` defines `Repository`.
- `test_docs_claims.py`: every backticked repo path exists; every env var read by `config.py` appears in `docs/DEPLOYMENT.md`; the coverage floor quoted in the README equals `fail_under`; the test count quoted in the README/NARRATIVE equals `pytest --collect-only`.
- `test_quality_gates.py::test_check_quality_script_passes`: run `scripts/check_quality.py` in a subprocess and assert exit 0.
- `test_efficiency.py`: `/health` < 1.0s; `search` < 1.0s; `top_k` clamped; oversize upload -> 413/400; `X-Process-Time` present.

**Steps:**
- [ ] Write `tests/test_code_quality.py`: module size cap <=150 (except `__init__.py`), every module has a docstring, every function has a docstring with Args/Returns/Raises sections, no `print(`, no `TODO`/`FIXME`/`HACK`, no hardcoded secrets, DIP ports present.
- [ ] Write `tests/test_docs_claims.py`: documented paths exist, documented env vars are read by `config.py`, the coverage floor matches, the test count matches, the disclaimer appears verbatim in README/NARRATIVE, both remote providers pin `temperature=0`, and plain rendering is shorter than standard.
- [ ] Write `tests/test_efficiency.py`: health/search latency, `top_k` clamp, bounded upload, `X-Process-Time`.
- [ ] Run `python -m pytest tests/test_code_quality.py tests/test_docs_claims.py tests/test_efficiency.py -q` -> fail (docs/counts not yet true).
- [ ] Fix any module over 150 lines by splitting (e.g., keep `main.py` under 150 by composition); update `scripts/check_quality.py` to fail when coverage < 76.
- [ ] Run `python scripts/check_quality.py` -> `QUALITY GATE PASSED`; run the full suite -> pass with zero warnings.
- [ ] Commit: `test: SRP <150, docs-claims, efficiency and coverage gates`.

#### T17 — Docs

**Files:** `README.md`, `docs/NARRATIVE.md`, `docs/DEPLOYMENT.md`, `docs/VIDEO_SCRIPT.md`.

**Interfaces:** none (prose). Required README sections: architecture, project layout (every backend module and test module named), security/efficiency/accessibility, `Performance and resource bounds` with measured claims, tests (exact collected count + `TOTAL >= 76%`), API table, deploy.

**Steps:**
- [ ] Write `README.md`: architecture (layered, provider protocols), project layout listing every `backend/app` module and `tests/test_*.py`, security (PBKDF2 120k/16-byte salt, HMAC tokens, generic 401s, 404 on cross-user), efficiency (`/health` metrics, cached TF-IDF, bounded reads, LRU rate limit, `asyncio.to_thread`), accessibility (labels, aria-live, 44px, reduced motion, textContent-only), a `Performance and resource bounds` section with measured claims from `tests/test_efficiency.py` (health p50/p95, search latency, cache hit rate, upload cap, rate limit), the exact test count and `TOTAL >= 76%`, and deploy.
- [ ] Write `docs/NARRATIVE.md` (problem, why better than general AI, trust design, Gen AI usage, changes description, what to link), `docs/DEPLOYMENT.md` (Render steps, every env var read by `config.py` in a table, prod hardening), and `docs/VIDEO_SCRIPT.md` (2–3 min walkthrough + sample ask queries).
- [ ] Run `python -m pytest tests/test_docs_claims.py -q` -> pass; run `python scripts/check_quality.py` -> PASS.
- [ ] Commit: `docs: README, narrative, deployment guide, video script`.

#### T18 — Deploy + verify

**Files:** `render.yaml`, `scripts/smoke.py`, `docs/DEPLOYMENT.md` (Render section), `README.md` (deploy URL).

**Interfaces:**
- `scripts/smoke.py`: `smoke(base_url: str) -> int`; checks `/health`, register, login, `GET /profile` 404, `PUT /profile`, `POST /air/context`, `GET /air?q=Delhi`, `GET /plans`, `POST /ask`, `POST /documents`, `GET /documents`, `DELETE /documents/{id}`, `GET /export?format=json`, 401 without a token, 404 cross-user.
- `render.yaml`: `services: - type: web, name: urban-air-quality-assistant, runtime: docker, plan: free, envVars: AUTH_SECRET (generateValue), AQI_API_KEY (optional)`.

**Steps:**
- [ ] Write `scripts/smoke.py` with the matrix above; run `python scripts/smoke.py http://127.0.0.1:8000` against a local uvicorn -> exit 0.
- [ ] Write `render.yaml`; build the Docker image and run it locally; re-run the smoke matrix against the container.
- [ ] Deploy to Render (manual step; requires explicit user approval) and run `python scripts/smoke.py https://<render-url>` -> exit 0.
- [ ] Run the final chain verification: `python scripts/check_quality.py` PASS, `python -m pytest -q` green, `python -m pip_audit -r requirements.txt` clean.
- [ ] Commit: `chore: render config, smoke matrix, deploy verification`.
