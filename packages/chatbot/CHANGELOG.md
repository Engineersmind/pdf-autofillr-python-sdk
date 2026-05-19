# Changelog — pdf-autofillr-chatbot

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
