# Changelog — pdf-autofillr-doc-upload

## [0.1.6] - 2026-07-14

### Security
- **[High] Unauthenticated arbitrary local file disclosure** — `/extract` accepted a
  user-controlled `document_path` (and `schema_path`) and passed it straight to
  `LocalStorage.download_document()` / `load_schema()` with no directory
  restriction, so any reachable local file (`.json`, `.txt`, `.md`, `.xml`,
  `.csv`, `.pdf`, `.docx`, etc.) could be read and returned via the job-output
  endpoints. Fixed by resolving every path and requiring it to live under an
  explicit allow-list of directories (`DOC_UPLOAD_DATA_PATH`,
  `DOC_UPLOAD_CONFIG_PATH`, and the new `DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS`).
  Reported by Farid Narimanov.
- **[High] Auth silently disabled when unconfigured** — `_check_api_key()`
  returned successfully with no `AUTH_TOKEN` set, so a forgotten env var meant
  every endpoint was unauthenticated with no warning. The server now refuses
  requests with a clear config error unless `AUTH_TOKEN` is set, or
  `DOC_UPLOAD_ALLOW_INSECURE_NO_AUTH=true` is explicitly set for local dev.
- API key comparison now uses `hmac.compare_digest` instead of `!=` to avoid
  timing side-channels.
- `job_id` is now restricted to a single path segment before being used to
  build filesystem paths, closing a secondary traversal vector.

### Added
- `DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS` env var — comma-separated extra
  directories `document_path` may resolve into, in addition to
  `DOC_UPLOAD_DATA_PATH` / `DOC_UPLOAD_CONFIG_PATH`.
- `DOC_UPLOAD_ALLOW_INSECURE_NO_AUTH` env var — explicit opt-in to run the
  API without authentication (local development only; do not use in
  production).
- `PathAccessError` exception, raised (and mapped to HTTP 400) when a request
  references a path outside the allowed roots.

## [Unreleased]

### Changed
- All packages: added `ruff`, `isort`, `flake8` to `[dev]` dependencies
- All packages: added `[tool.ruff]`, `[tool.isort]` config sections to `pyproject.toml`
- CI: new `ci.yml` workflow for lint and type checking (black, isort, ruff, mypy) across all packages
- CI: new `release.yml` workflow adds lint and type gate before publish, plus GitHub Release creation with changelog notes

---

## [0.1.5] - 2026-05-16

### Fixed
- Suppress interpreter shutdown errors from background PDF fill thread
- Silent catch for `cannot schedule new futures after interpreter shutdown` in mapper headers
- Demote shutdown-phase RAG API errors to debug level

## [0.1.4] — 2026-04-22

### Added
- PPTX, HTML, XML input format support
- `fallback_extractor` — rule-based extraction when LLM confidence is low
- S3, Azure Blob, GCS storage backends

### Changed
- `DocUploadClient` is now the single public entry point
- Document reader auto-detects format from file extension

### Fixed
- CSV files with quoted commas were split incorrectly
- DOCX files with embedded images caused extraction to hang

---

## [0.1.3] — 2026-03-20

### Added
- XLSX and CSV input format support
- `inprocess_filler` — direct mapper integration without HTTP

### Fixed
- JSON extraction failing on nested objects deeper than 2 levels

---

## [0.1.0] — 2026-03-10

### Added
- Initial public release
- PDF, DOCX, TXT, MD, JSON input formats
- LLM-based field extraction
- Mapper integration (inprocess and HTTP)
- FastAPI server and CLI
- AWS Lambda entrypoint
- Local storage backend
