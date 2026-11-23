# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  issue/PR templates, CODEOWNERS, Dependabot and CI/security workflows.
- `pre-commit` hooks and gitleaks configuration.
- Structured security-event logging (`security` logger) for auth failures,
  rate-limit rejections, upload rejections and unhandled errors.
- OpenAPI metadata: API description, contact, license and tag descriptions,
  a shared `ErrorResponse` schema for the declared 401/404/409/429/500
  responses (plus upload 400/413/503), a 413 body-limit response on every JSON
  body route, a declared 429 on `GET /`, a documented 500 on every operation,
  and examples on every public schema field.
- Upload rejection events now cover route validation failures, PDF parsing,
  the document limit and busy slots, emitting only the path and reason and
  never the filename or document text.
- CI lints and format-checks the frontend and runs the Playwright journey and
  axe suites against a fresh offline Uvicorn instance, keeping the report when
  the run fails.
- Compact `GET /documents` summary payload without full document text.
- Profile screenshot added to `docs/EVIDENCE.md` and the README.
- `SECURITY.md` privacy and threat-model coverage: data inventory, retention
  and deletion (including the account-deletion path), LLM/weather data sharing,
  data rights, STRIDE analysis, incident response and residual risks.

### Changed

- `/static` now serves only `styles.css` and `js/`; frontend manifests,
  lockfiles, lint/format configuration, dotfiles, `index.html` and
  `node_modules` are no longer reachable, and those tooling files are excluded
  from the Docker image.
- Packaging metadata in `pyproject.toml`: readme, license, authors, pinned
  runtime dependencies, `dev` extra and setuptools package-data for the seed
  corpus.
- `GET /export` documents `format` with a validated query pattern and declares
  both `text/markdown` and `application/json` 200 content types.
- Quality gate now also enforces `ruff format --check`, runs branch coverage
  through `coverage run` (avoiding mixed statement/branch parallel data) and
  raises the floor to 89%.
- Split the SQLite repository and the shared document-store helper into focused
  modules so every backend module stays under 150 lines.
- Tests force provider keys empty so the suite never calls a live provider.
- The gitleaks allowlist names the fake fixture values instead of ignoring the
  entire `tests/` tree.

### Fixed

- Unhandled route exceptions emit exactly one metadata-only `unhandled_error`
  security event (path, method and exception class only) and never double-log.
- Duplicate registration now raises a dedicated `DuplicateEmailError`, keeping
  the documented 409 even when two signups race the unique constraint.
- `mypy` `warn_return_any` violation in the SQLite base repository.
- Docker image now includes `backend/data/seed_corpus.json` (`.dockerignore`
  no longer excludes every `data` directory).

### Security

- Expanded CSP (`object-src 'none'`, `base-uri 'self'`, `form-action 'self'`)
  and added `Cross-Origin-Opener-Policy` / `Cross-Origin-Resource-Policy`.
- Security events are logged without secrets or document contents.

## [0.1.0] - 2026-11-22

### Added

- FastAPI backend with auth, profile, air context, plans, grounded ask,
  documents, PDF upload and export endpoints.
- Offline-first local synthesis with optional Gemini, OpenAI-compatible and
  OpenWeather providers, all behind ports with deterministic fallbacks.
- Static vanilla-JS frontend served by FastAPI, with accessible forms,
  responsive layout and a demo walkthrough.
- SQLite and in-memory repositories behind a single port; seeded corpus and
  owner-scoped retrieval.
- Test suite, quality-gate runner, benchmark and smoke scripts, Dockerfile,
  Render blueprint and documentation set.
