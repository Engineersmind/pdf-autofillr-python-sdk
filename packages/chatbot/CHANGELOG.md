# Changelog — pdf-autofillr-chatbot

## [0.4.0] - 2026-07-14

### Security
- **[High] No authentication on any endpoint** — the FastAPI app had no API
  key check at all, so `/chatbot/chat`, `/chatbot/session/{user_id}/{session_id}`
  (read + delete), and the fill-report endpoint were reachable by anyone who
  could route to the server. All endpoints now require `X-API-Key` matching
  `CHATBOT_API_KEY`. The server refuses to start serving requests if
  `CHATBOT_API_KEY` isn't set, unless `CHATBOT_ALLOW_INSECURE_NO_AUTH=true`
  is explicitly set for local dev.
- **[Medium] Path traversal via `user_id`/`session_id`** — these were used
  directly as filesystem path segments in `LocalStorage`, so a crafted id
  (e.g. containing `../`) could read/write/delete outside the intended
  per-user directory. Both are now validated as single path segments before
  any filesystem access; invalid values return HTTP 400.
- **[Medium] Permissive CORS** — `allow_origins=["*"]` with all methods/headers
  open is replaced with an explicit allow-list via
  `CHATBOT_CORS_ALLOWED_ORIGINS` (comma-separated), empty (no cross-origin
  access) by default.
- API key comparison uses `hmac.compare_digest` to avoid timing side-channels.

### Added
- `CHATBOT_API_KEY` — required in production; requests must send it as the
  `X-API-Key` header.
- `CHATBOT_ALLOW_INSECURE_NO_AUTH` — explicit opt-in to run without auth
  (local dev only).
- `CHATBOT_CORS_ALLOWED_ORIGINS` — comma-separated list of allowed origins.

### Note
- Authentication above is a single shared API key, matching the pattern used
  by the other services in this SDK. It stops unauthenticated access from
  outside; it does not yet enforce that caller A cannot address caller B's
  `user_id`/`session_id` if both hold the same API key. If you expose this
  service to multiple mutually-untrusting users directly, add a per-user
  auth/session-ownership layer on top (e.g. a signed per-user token) before
  going to production.

## [Unreleased]

### Changed
- All packages: added `ruff`, `isort`, `flake8` to `[dev]` dependencies
- All packages: added `[tool.ruff]`, `[tool.isort]` config sections to `pyproject.toml`
- CI: new `ci.yml` workflow for lint and type checking (black, isort, ruff, mypy) across all packages
- CI: new `release.yml` workflow adds lint and type gate before publish, plus GitHub Release creation with changelog notes

---

## [0.3.0] - 2026-05-16

### Fixed
- Suppress interpreter shutdown errors from background PDF fill thread
- Silent catch for `cannot schedule new futures after interpreter shutdown` in mapper headers
- Demote shutdown-phase RAG API errors to debug level

## [0.2.9] - 2026-04-28

### Added
- `src/chatbot/limits/__init__.py`, `src/chatbot/limits/rate_limiter.py`: stub `RateLimiter` implementation so `test_rate_limiter.py` passes CI (not wired into application)

## [0.2.8] — 2026-04-22

### Added
- `sequential_fill_handler` — fills fields one by one without full state machine
- `telemetry/collector.py` — session metrics: turns, duration, field coverage
- Azure Blob and GCS storage backends

### Changed
- State machine handlers are now composable
- `chatbot_PDF_FILLER=mapper` is the default (was `none`)
- Config samples reorganised into investor-type subfolders

### Fixed
- Boolean group handler skipping optional fields incorrectly
- Mailing address check handler not triggering on partial address input
- Rate limiter test was flaky under parallel test runners

---

## [0.2.7] — 2026-03-25

### Added
- `update_existing_handler` — lets users correct previously entered values
- `optional_fields_handler` — collects non-required fields at end of session
- S3 storage backend

### Fixed
- Session state not persisted correctly when PDF filler raised an exception

---

## [0.2.0] — 2026-03-10

### Added
- Initial public release
- Conversation engine with state machine
- LLM-based field extraction from transcript
- Per-state handlers: init, investor type, data collection, missing fields, boolean groups
- FastAPI server and CLI
- AWS Lambda entrypoint
- Local storage backend
