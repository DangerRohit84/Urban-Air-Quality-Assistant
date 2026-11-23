# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting on this repository
(Security -> Advisories -> Report a vulnerability). Do not open a public issue,
and do not include live secrets in a report. Expect an acknowledgement within
72 hours and a remediation plan within 7 days for confirmed issues.

## Security design

- **Passwords:** PBKDF2-HMAC-SHA256, 600,000 iterations, 16-byte random salt,
  self-describing records with transparent rehash on login. Verification is
  constant-time and unknown-email logins run a dummy hash so response timing
  does not reveal account existence.
- **Tokens:** HMAC-SHA256 signed bearer tokens with a `jti` and expiry. Logout
  revokes the `jti` until expiry. A missing `AUTH_SECRET` falls back to a
  per-boot ephemeral secret and logs a warning; production must set one.
- **Authorization:** every document, profile, plan, ask and export path is
  owner-scoped; cross-owner access returns 404/401, never data.
- **Transport and browser hardening:** `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, a restrictive CSP (`default-src 'self'`,
  `frame-ancestors 'none'`, `object-src 'none'`), COOP/CORP `same-origin`,
  `Referrer-Policy`, `Permissions-Policy`, HSTS and `Cache-Control: no-store`.
- **Abuse limits:** per-client sliding-window rate limiting (proxy-aware only
  when `TRUST_PROXY=true`), a 1 MiB JSON body cap, a 5 MiB upload cap, and a
  single-flight PDF parse slot that answers 503 + `Retry-After` instead of
  queueing work.
- **Uploads:** extension/MIME/magic-byte checks, a pre-parse structure guard,
  a page/character budget, sanitized filenames, and a 10-document cap per owner.
- **Logging:** security events (auth failures, rate-limit rejections, upload
  rejections, unhandled errors) are emitted as single-line JSON on the
  `security` logger with no credentials, tokens, document text or secrets.
- **No telemetry:** the app sends no analytics; outbound calls happen only to a
  provider the operator explicitly configured.

## Privacy and data protection

### Data inventory

The app stores only the data needed for an account and the features the user
requests. There is no analytics, tracking pixel or third-party script, and no
cookie is set.

| Data | Purpose | Where it lives | Retention | Third-party sharing |
| --- | --- | --- | --- | --- |
| Email + PBKDF2 hash | Sign-in, account identity, logout | `users` table in SQLite (`data/air.db`) | Until account deletion | Never sent to LLM or weather providers |
| Household profile: city, climate zone, children, elderly, respiratory, commute mode/distance, cooking fuel, heating type, budget | Personalize plans and answers | `profiles` table | Until overwritten via `PUT /profile` or account deletion | Subset in the `/ask` prompt when a remote LLM is configured (see below) |
| Question text | Answer the current request | Request-scoped memory only; not persisted | Discarded with the response | Remote LLM only, when configured |
| Documents: sanitized title, text, chunks, source, timestamps | Retrieval and cited answers | `documents` table (raw upload bytes and PDFs are not stored) | Until `DELETE /documents/{id}` or account deletion | Retrieved excerpts in the `/ask` prompt when a remote LLM is configured |
| AQI context: city, band, value, PM2.5, PM10, season, observed time, source | Ground plans and answers | `aqi_context` table | Until replaced by a new saved context or account deletion | City and band only, in the `/ask` prompt when a remote LLM is configured |
| Revoked token `jti` + expiry | Reject logged-out tokens | `revoked_tokens` table | Until token expiry; pruned opportunistically on the next revocation | Never shared |
| Security events: path, method, reason, exception class | Abuse detection and operations | `security` logger → stdout / hosting log stream | Controlled by the hosting provider, not the app | Hosting provider's log pipeline |

### Health-adjacent data

`children`, `elderly` and `respiratory` are household-context booleans used to
pick exposure guidance. They are not a diagnosis, treatment record or medical
history, and the app does not collect symptoms, medication or insurance data.
Do not enter real medical details: the assistant provides general
environmental guidance, not medical advice. Only `children`, `respiratory`,
`city`, `climate_zone`, `commute_mode` and `cooking_fuel` are currently placed
in a remote `/ask` prompt; `elderly`, `budget_level`, `heating_type` and
`commute_km` are used locally by the planner and are not sent to an LLM.

### Retention and deletion

- **Documents:** `DELETE /documents/{id}` removes the row and invalidates the
  owner's in-process retrieval cache immediately. Uploaded bytes exist only
  during the bounded request/parse and are never persisted.
- **Profile:** `PUT /profile` overwrites the saved values, so a user can
  minimize or correct data at any time.
- **Sessions:** `POST /auth/logout` inserts the token's `jti` into
  `revoked_tokens`; expired rows are deleted opportunistically when the next
  logout occurs. Tokens themselves expire after 24 hours.
- **Account deletion:** there is no self-service account-delete endpoint.
  Request deletion through GitHub private vulnerability reporting; confirmed
  requests are completed within 7 days. The operator deletes the `users` row,
  and `ON DELETE CASCADE` removes the profile, documents and AQI context.
  Revocation records carry no user id and expire on their own; rotate
  `AUTH_SECRET` to invalidate any outstanding tokens at once.
- **Hosting:** the Render blueprint uses the free plan, whose disk is
  ephemeral. A redeploy or restart resets `data/air.db`, so this demo has no
  durable backups. Production use should add an encrypted managed database and
  an explicit backup policy.

### LLM and third-party sharing

Outbound calls happen only when the operator configures a provider. Provider
selection and precedence live in `backend/app/llm/factory.py`.

- **Remote LLM (Gemini or an OpenAI-compatible endpoint):** `/ask` sends the
  question, the grounded prompt (saved city/climate/commute/cooking/children/
  respiratory context plus the saved AQI city and band) and retrieved source
  excerpts, which can include the user's own documents. It does **not** send
  the email address, password hash, bearer token, user id or raw PDF bytes.
  However, free-text questions and document excerpts can themselves contain
  personal data, so the operator must treat the LLM provider as a
  sub-processor and review its data-use terms before enabling it.
- **OpenWeather (optional live AQI):** the app resolves the allowlisted Indian
  city server-side and sends its latitude/longitude and the API key. It does
  not send the user's email, token, profile, documents or account id.
- **Offline mode:** with no provider keys, `LocalSynthProvider` answers in
  process and no household or document data leaves the host.

### Data rights and operator duties

- **Access:** `GET /profile` returns the saved profile; `GET /documents`
  returns document summaries (id, kind, title, created time). The create and
  upload responses return the stored record, including sanitized text.
- **Rectification:** `PUT /profile` replaces the saved profile.
- **Erasure:** `DELETE /documents/{id}`, plus the account-deletion request
  above for the whole account.
- **Portability:** `GET /export?format=md` or `format=json` exports the
  personalized plan; profile and document metadata are available from their
  GET endpoints.
- **Objection/opt-out:** a deployment that must not share data with third
  parties should leave `GEMINI_API_KEY` and `OPENAI_API_KEY` unset. There is no
  per-user provider toggle.
- **Operator duties:** choose a lawful basis, publish the deployment's privacy
  notice, keep provider keys server-side, and include any configured LLM or
  weather provider in the deployment's sub-processor list. The repository's
  maintainers cannot grant consent on behalf of a deployment's users.

### Cookies, CSRF and browser storage

The API sets no cookies, so cookie-based CSRF does not apply. The frontend
keeps the bearer token in `sessionStorage` under `uqa_token`
(`frontend/js/api.js`); it is cleared when the tab session ends. Any same-origin
XSS could read that token, which is why the CSP restricts scripts and styles to
the app origin and the UI renders user text with `textContent` rather than
`innerHTML`. There is no localStorage persistence.

### Data at rest and in transit

Render terminates TLS and the app sends HSTS. `data/air.db` is plaintext
SQLite: only passwords are hashed, not the email, profile or document text,
and there is no field-level encryption or encrypted volume in the free
blueprint. Provider keys and `AUTH_SECRET` come from environment variables and
are not baked into the image or returned by any endpoint.

## Threat model (STRIDE)

| Threat | Primary mitigations | Residual risk |
| --- | --- | --- |
| **Spoofing** — forged or stolen bearer token | HMAC-SHA256 signature, 24-hour expiry, `jti` revocation on logout, generic 401s, rate limiting | Client-side token theft (for example a compromised browser) is not detectable; tokens minted before `jti` support are valid but not revocable, bounded by 24-hour expiry |
| **Tampering** — altering another user's data | Owner-scoped SQL predicates, parameterized queries, Pydantic validation, 404 for cross-owner access, 1 MiB JSON cap | An authenticated owner can freely edit their own data by design; there is no content-change audit trail |
| **Repudiation** — denying a change | Security events record auth failures, rate-limit hits and rejected uploads | No per-user audit log of profile/document writes, so the demo cannot reconstruct who changed content |
| **Information disclosure** — cross-owner reads, tooling files, logs, third-party prompts | Owner-scoped 404s, `/static` limited to the stylesheet and `js/` (tooling and `node_modules` are 404 and excluded from the image), metadata-only logs, no email/token/raw PDF to LLM, `Cache-Control: no-store`, CSP/COOP/CORP | `/docs` and `/openapi.json` are public by design and expose the API contract; enabled LLM providers receive the question and excerpts; SQLite is plaintext at rest |
| **Denial of service** — upload or ask floods | 5 MiB upload cap, 1 MiB JSON cap, 10-document cap, single-flight PDF parse slot with 503 + `Retry-After`, 200 req/min sliding window, bounded PDF pages/streams, 10-second LLM timeout and 1 MiB response cap | The rate limiter is in-process per worker, not a global quota; the in-process retrieval cache has no size bound; a single-instance free deployment has no upstream WAF |
| **Elevation of privilege** — reaching admin functions | No admin API or role surface; every route derives the owner from the verified token; secrets stay in environment variables | Anyone who can read the operator's environment or filesystem already has full control of the deployment |

## Incident response

1. Contain: rotate `AUTH_SECRET` (all outstanding tokens stop verifying) and
   rotate any exposed `GEMINI_API_KEY`, `OPENAI_API_KEY` or `AQI_API_KEY`, then
   redeploy so no old process keeps the previous environment.
2. Assess: review the hosting platform's logs for `security` events and
   abnormal request patterns. The app deliberately logs no request bodies,
   tokens or document text, so scope the incident from infrastructure logs.
3. Notify: use GitHub private vulnerability reporting for reporter/maintainer
   coordination; a deployment operator is responsible for notifying its own
   users and any regulator within applicable breach deadlines.
4. Recover and learn: redeploy from a clean image, verify `/health`, add a
   regression test and record the follow-up in `CHANGELOG.md`.
5. If account credentials may be exposed, tell affected users to change their
   password and re-login; there is no password-reset endpoint, so the operator
   handles credential recovery directly.

## Residual risks

- Rate limiting is per process, so a multi-worker deployment multiplies the
  effective limit; put a shared limiter or edge WAF in front before scaling.
- Prompt-injection defense is layered but not absolute: retrieved text is
  escaped and labelled as data, yet a sufficiently adversarial document can
  still influence a remote model's answer. Keep citations visible and treat
  answers as guidance, not instructions.
- The retrieval cache is bounded by document count per user, not by global
  memory; a single process serving many accounts will grow with active owners.
- `/docs` and `/openapi.json` are intentionally public for this demo. A
  deployment that treats the contract as sensitive should gate or disable them
  at the proxy.
- Free-tier Render storage is ephemeral and unencrypted; do not treat it as a
  system of record.
- Legacy tokens without `jti` cannot be revoked individually; rotate
  `AUTH_SECRET` for a global cutoff.

## Token rotation

Rotating `AUTH_SECRET` invalidates every outstanding token at once; users must
log in again. Revoked token ids are retained in the `revoked_tokens` table
until their expiry, so the table grows with logouts and can be pruned after
expiry. Rotate the secret immediately if it leaks, and rotate provider keys on
the same schedule.

## Deployment checklist

1. Set `AUTH_SECRET` to at least 32 random bytes (for example
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
2. Set `ALLOWED_ORIGINS`/`FRONTEND_ORIGIN` to the real HTTPS origin.
3. Enable `TRUST_PROXY` only behind a proxy that overwrites
   `X-Forwarded-For`, and set `TRUSTED_PROXY_HOPS` to the trusted chain length.
4. Keep provider keys server-side; never expose them to the frontend.
5. Run `pip-audit -r requirements.txt` and `gitleaks detect` before a release.
6. Serve behind HTTPS and keep the Docker image on a supported Python base.

## Out of scope

- Denial of service against a single-instance deployment without a proxy.
- Secrets committed to a fork or copied into a local `.env` by the operator.
- Vulnerabilities in optional third-party provider APIs.
