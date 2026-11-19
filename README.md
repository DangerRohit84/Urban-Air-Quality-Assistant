# Urban Air Quality Assistant

FastAPI + vanilla-JS assistant that turns a user's city, household and
lifestyle profile plus CPCB AQI context into personalized low-emission
routines, indoor air hacks, sustainable alternatives, quantified impact and
grounded cited answers.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

Then open http://localhost:8000.

## Performance and resource bounds

- Coverage gate: total line coverage >= 76% (target 85%+), enforced by
  `scripts/check_quality.py`.
- Every backend module stays under 150 lines (enforced by a test).
- Upload cap: 10 MiB (`MAX_UPLOAD_BYTES`); documents per owner: 10
  (`MAX_DOCUMENTS`).
- Rate limit: 200 requests/minute per client (`RATE_LIMIT_PER_MIN`), at most
  10,000 buckets (`MAX_RATE_BUCKETS`).

## Tests

Test suite: **0 tests** (placeholder - the final count is set by Task 17).

```bash
python -m pytest -q              # run the suite
python scripts/check_quality.py  # ruff + mypy + pytest + coverage gate
```

## Project layout

```
backend/app/   domain modules plus auth/, llm/, air/, storage/, routes/
frontend/      static HTML/CSS/JS served by FastAPI
scripts/       quality-gate runner and smoke checks
tests/         pytest suite
docs/          design, plan and deployment documentation
```
