# Contributing

Thanks for improving the Urban Air Quality Assistant. This project is a small,
fully offline-capable FastAPI service with a static frontend; the bar is high
and the toolchain is already wired up.

## Setup

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

On macOS or Linux use `python3.11 -m venv .venv`, `source .venv/bin/activate`
and `cp .env.example .env`. Never commit `.env`; every secret is optional and
the app degrades to local synthesis without provider keys.

## Commands

| Purpose | Command |
| --- | --- |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Types | `mypy backend/app` |
| Tests | `pytest -q` |
| Coverage | `pytest -q --cov=backend --cov-report=term-missing` |
| Full gate | `python scripts/check_quality.py` |

`python scripts/check_quality.py` is the authoritative gate: lint, format,
types, tests, test-count and coverage must all pass before a change is done.

## Rules

- **Keep backend modules under 150 lines.** `tests/test_boundaries.py` fails
  the build when a module grows past the limit; extract a helper module instead.
- **Type everything.** Public functions carry annotations and Google-style
  docstrings; `mypy` runs with `warn_return_any` and `warn_unused_ignores`.
- **Tests are hermetic.** Never call a live provider in tests; monkeypatch the
  settings/provider and assert the offline fallback. The suite asserts that
  provider keys are empty.
- **Security-sensitive paths** (auth, uploads, export, retrieval) need an
  explicit owner-scoping test and a regression test for the failure mode.
- **No new runtime dependencies** without a pinned version in
  `requirements.txt` and a note in `pyproject.toml`.
- **Frontend** is plain HTML/CSS/JS served by FastAPI; keep it accessible
  (labels, focus states, reduced-motion support) and free of build steps.

## Pull requests

1. Branch from `main`, keep commits focused and message them in the imperative
   mood (`Add upload guard`, not `added stuff`).
2. Run `python scripts/check_quality.py` and paste the summary in the PR.
3. Fill in the PR template: what changed, why, how it was verified, and any
   residual risk.
4. Update `CHANGELOG.md` under `Unreleased` for user-visible changes and
   `docs/` when behaviour or configuration changes.

## Reporting security issues

Do not open a public issue for a vulnerability. Follow `SECURITY.md`.

## Code of conduct

Participation is covered by `CODE_OF_CONDUCT.md`.
