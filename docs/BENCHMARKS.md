# Benchmarks

Measured evidence for the Urban Air Quality Assistant, produced by
`scripts/benchmark.py` on 2026-11-21. The raw machine-readable report is
`docs/benchmark-results.json`.

## Environment

| Item | Value |
|---|---|
| Host | Windows 10 (10.0.26340) development laptop |
| Python | 3.11.9 |
| Logical CPUs | 20 |
| Server | Uvicorn on `127.0.0.1`, one worker, `--no-proxy-headers` |
| Storage | SQLite in a temporary file |
| LLM provider | `local_synth` (deterministic, no network) |
| AQI provider | unset, so `/air` answers offline from the saved band |

The script starts the real server, waits for `/health`, then runs 30 measured
passes. Each pass registers a fresh account, logs in, calls every benchmarked
endpoint, and deletes the documents it created. Latency is wall-clock time
around the HTTP call measured in the client process; the first pass is included
(warm-up is not discarded). Percentiles are nearest-rank, not interpolated.

Reproduce with:

```bash
python scripts/benchmark.py --iterations 30 --json docs/benchmark-results.json
```

Add `--no-docker` to skip the container evidence.

## Request latency (30 iterations)

| Operation | p50 | p95 | mean | min | max |
|---|---:|---:|---:|---:|---:|
| Register + login | 450.50 ms | 482.34 ms | 450.57 ms | 418.07 ms | 487.97 ms |
| `GET /air?q=Delhi` (offline) | 17.03 ms | 26.48 ms | 15.37 ms | 2.57 ms | 26.88 ms |
| `POST /ask` grounded | 17.84 ms | 22.89 ms | 14.90 ms | 4.16 ms | 27.75 ms |
| `POST /ask` refusal | 14.96 ms | 29.54 ms | 16.51 ms | 3.19 ms | 30.98 ms |
| `POST /documents` inline | 16.07 ms | 27.79 ms | 15.95 ms | 4.21 ms | 30.02 ms |
| `POST /documents/upload` (~1 MB PDF) | 306.46 ms | 340.34 ms | 311.18 ms | 287.97 ms | 345.99 ms |

The grounded pass also asserts the seeded question returns
`grounded: true`; the refusal pass asserts the out-of-domain question returns
`grounded: false`. A wrong verdict aborts the run instead of recording a
misleading number.

## Cold start

Three fresh `python -c "import backend.app.main"` processes, median
**2191.8 ms** (min 2165.6 ms, max 2218.8 ms). This includes interpreter
startup and importing the web, PDF and retrieval dependencies, not just the
application module.

## Docker evidence

| Item | Value |
|---|---|
| Image | `urban-air-quality-assistant:benchmark` |
| Image size | 171.5 MiB (179,786,524 bytes) |
| Memory cap | `docker run --memory 512m` |
| Smoke result | **passed** |

The smoke container starts from the built image under a 512 MiB cap, registers
an account, asks the seeded purifier question, and requires a grounded answer
before the run is considered successful. The container is removed afterwards.

## Interpretation

- Registration and login dominate the table because passwords are deliberately
  expensive: PBKDF2-HMAC-SHA256 with 600,000 iterations runs once to register
  and once to verify. That cost is the security feature, not server overhead.
- Warm API reads (`/air`, `/ask`, document inserts) land in the low tens of
  milliseconds at p95 on this host, including JSON encoding and SQLite I/O.
- The ~1 MB upload path is bounded by transferring the body and extracting the
  PDF text; p95 stays under 350 ms.
- These are laptop numbers for a single worker with the deterministic local
  provider. Remote LLM latency depends on the configured provider, and this is
  not a production capacity claim. The benchmark exists so the published
  numbers are reproducible rather than estimated.
