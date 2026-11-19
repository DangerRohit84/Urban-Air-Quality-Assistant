# Deployment

## Environment variables

Every variable read by `backend/app/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `local_synth` | Provider name; one of `gemini`, `openai-compat`, `local_synth`, `echo`. |
| `GEMINI_API_KEY` | empty | Enables the Gemini provider when set. |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name. |
| `OPENAI_API_KEY` | empty | Enables the OpenAI-compatible provider when set. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint. |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI-compatible model name. |
| `AQI_API_KEY` | empty | Enables live AQI; when empty the user-entered band is authoritative. |
| `STORE_BACKEND` | `sqlite` | `sqlite` or `memory`. |
| `DATABASE_URL` | `sqlite:///./data/air.db` | SQLite location. |
| `AUTH_SECRET` | per-boot random | HMAC token secret; set explicitly in production. |
| `FRONTEND_ORIGIN` | `http://localhost:8000` | CORS origin. |
| `ALLOWED_ORIGINS` | `FRONTEND_ORIGIN` | Comma-separated CORS allowlist. |
| `RATE_LIMIT_PER_MIN` | `200` | Per-client request budget per 60 seconds. |
| `MAX_RATE_BUCKETS` | `10000` | LRU bucket bound. |
| `MAX_UPLOAD_BYTES` | `10485760` | Upload cap in bytes (10 MiB). |
| `MAX_DOCUMENTS` | `10` | Documents per owner. |
| `PORT` | `8000` | Uvicorn port. |
| `LOG_LEVEL` | `info` | Log level. |

## Local verification

```bash
python -m pytest -q               # full suite
python scripts/check_quality.py   # ruff + mypy + pytest + coverage gate
python scripts/smoke.py http://127.0.0.1:8000
```

Build and run the container, then point the smoke script at it:

```bash
docker build -t urban-air-quality-assistant .
docker run --rm -p 8000:8000 urban-air-quality-assistant
python scripts/smoke.py http://127.0.0.1:8000
```

## Render

1. Push the branch and create a new Blueprint from the repository blueprint
   file.
2. Render builds the Docker image and runs `uvicorn` on `$PORT`.
3. The blueprint generates `AUTH_SECRET`; set `AQI_API_KEY` only if live AQI is
   required.
4. Verify the deployment with `python scripts/smoke.py https://<your-render-url>`.

## Production hardening

- Set a strong `AUTH_SECRET`; the per-boot random secret is a development
  fallback only.
- Keep `AQI_API_KEY` empty for an offline-first deployment.
- Front the service with TLS; the security middleware already sends HSTS.
- Restrict `ALLOWED_ORIGINS` to the public origin in production.
- The free tier uses ephemeral storage, so SQLite data does not survive a
  restart.
