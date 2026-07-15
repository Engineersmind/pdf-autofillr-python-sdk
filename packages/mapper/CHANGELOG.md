# Changelog — pdf-autofillr-mapper

## [1.0.11] - 2026-07-14

### Fixed (functional — not security)
- **Every server/CLI entrypoint called the operation handlers with the
  wrong calling convention.** `handle_extract_operation`/`handle_map_operation`/
  `handle_embed_operation`/`handle_fill_operation` all take a populated
  storage-config object as their first argument; every entrypoint either
  omitted it, passed `None`, passed a raw dict, or passed made-up keyword
  arguments (`input_file=`, `extracted_json_path=`, etc.) that don't exist
  on the real functions. In practice this meant `/extract`, `/map`, `/embed`,
  `/fill`, `/make-embed-file`, `/run-all` (and their CLI equivalents) always
  raised `TypeError`/`AttributeError`, or — in `entrypoints/fastapi_app.py`'s
  case — silently returned an unawaited coroutine instead of a result.
  Fixed by adding `build_operation_config()` (see `configs/local.py`), which
  builds a fully-populated config from a bare `pdf_path`, and rewiring:
  - `entrypoints/fastapi_app.py` (all 7 operation endpoints)
  - `api_server.py` (all 8 operation endpoints, plus a broken
    `from pdf_autofillr_mapper.core.config import get_mapping_config` import
    that doesn't exist — replaced with the real
    `get_ini_config().get_mapping_config()`)
  - `entrypoints/cli.py` (all 7 subcommands; also added missing `await`/
    `asyncio.run()` — these are async functions that were being called
    synchronously and their results silently discarded)
  - `handle_run_all_operation` and `handle_refresh_operation` internally
    (`handlers/operations.py`) — same bug in their own stage-to-stage calls
  Verified end-to-end against a real PDF: `/extract` and `/map` (both
  FastAPI apps and the CLI) now return real results.
- **`BoundingBox` constructor/attribute mismatch** — extraction code called
  `BoundingBox(l=..., t=..., ...)` and read `bbox.l`, but the class only
  ever defined `left`. Every real PDF extraction call failed with
  `TypeError`/`AttributeError` before even reaching field-mapping logic.
  Fixed the two constructor call sites in `detailed_fitz.py` and
  `fitz_extract_lines.py`, and added a backward-compatible `.l` property
  alias on `BoundingBox` for the several other read sites.
- **`storage/job_context.py` called `PathResolver` methods with the wrong
  number of arguments**, and referenced a `remote_semantic_mapping` method
  that didn't exist at all. Fixed the call sites and added the missing
  resolver method. (This code path isn't currently wired into any active
  entrypoint — `utils/entrypoint_helpers.py`, the only caller, isn't
  imported anywhere — but the bugs were real and are now fixed for whenever
  it is.)
- **`entrypoints/aws_lambda.py`** called a nonexistent
  `extractor.extract_to_json(...)` (async) instead of the real, synchronous
  `extractor.extract(pdf_path, storage_config)`. Fixed the call; note the
  surrounding AWS S3-specific extract/map/embed/fill routing in this file
  (and the equivalent Azure/GCP function entrypoints) still has the same
  wrong-calling-convention issue described above and was **not** fixed this
  round — it requires an S3/Blob/GCS-equivalent of `build_operation_config`
  that couldn't be verified without real cloud credentials in this
  environment. `handle_run_all_operation`'s call in `aws_lambda.py` was
  already correct and needed no change.
- Fixed the mismatched version string mapper's FastAPI apps reported at `/`
  (`1.0.10` vs. the package's actual `1.0.11`).

### Security
- **[Critical] `api_server.py` had no authentication whatsoever** — this is
  the entrypoint the README tells you to run (`python api_server.py`), and
  it's a separate implementation from `entrypoints/fastapi_app.py` (which
  had at least a broken auth check). Every `/mapper/*` operation endpoint —
  including ones that read an arbitrary local `pdf_path` — and the
  `/download/{file_path}` endpoint were reachable by anyone with no key at
  all. Added the same fail-closed `verify_api_key` dependency used in
  `entrypoints/fastapi_app.py` to every endpoint except `/` and `/health`.
- **[Medium] `/download/{file_path}` served anything under the server's
  working directory** — which typically also contains source code, `.env`
  files, and other secrets, not just generated output. Restricted to
  `MAPPER_DOWNLOAD_ROOT` (defaults to the same directory
  `LocalStorageConfig` writes output to).
- **[High] `entrypoints/fastapi_app.py` auth was a no-op** —
  `verify_api_key()` read `settings.api_key`,
  a field that didn't exist on `Settings`, so `hasattr(settings, "api_key")`
  was always `False` and every request was accepted regardless of the
  `X-API-Key` header. Added a real `api_key` setting (env var `API_KEY`),
  and the dependency now fails closed: requests are rejected with a clear
  config error if no key is configured, unless
  `MAPPER_ALLOW_INSECURE_NO_AUTH=true` is explicitly set for local dev.
- **[Medium] Permissive CORS** — `allow_origins=["*"]` combined with
  `allow_credentials=True` is an invalid/dangerous combination that some
  clients will honor anyway. Now uses an explicit allow-list via
  `MAPPER_CORS_ALLOWED_ORIGINS`; credentials are only enabled when a
  concrete allow-list is configured.
- API key comparison uses `hmac.compare_digest` to avoid timing side-channels.

### Added
- `API_KEY` — the mapper API's shared secret; required in production.
- `MAPPER_ALLOW_INSECURE_NO_AUTH` — explicit opt-in to run without auth
  (local dev only).
- `MAPPER_CORS_ALLOWED_ORIGINS` — comma-separated list of allowed origins.

## [Unreleased]

### Changed
- All packages: added `ruff`, `isort`, `flake8` to `[dev]` dependencies
- All packages: added `[tool.ruff]`, `[tool.isort]` config sections to `pyproject.toml`
- CI: new `ci.yml` workflow for lint and type checking (black, isort, ruff, mypy) across all packages
- CI: new `release.yml` workflow adds lint and type gate before publish, plus GitHub Release creation with changelog notes

---

## [1.0.10] - 2026-05-23

### Changed
- Remove commented-out legacy `UnifiedLLMClient` implementation from `unified_llm_client.py`

### Fixed
- Catch interpreter shutdown RuntimeError in `semantic_mapper.py` `process_batch()` and `process_and_save()` to suppress noisy shutdown errors

## [1.0.9] - 2026-05-16

### Fixed
- Suppress `PYMUPDF_SUGGEST_LAYOUT_ANALYZER` warning globally via `os.environ.setdefault` in `detailed_fitz.py`
- Silent catch for `cannot schedule new futures after interpreter shutdown` in `get_form_fields_points.py`
- Demote shutdown-phase RAG API errors to debug level in `operations.py`
- Filter empty-context fields before calling `RAGPDFClient.get_predictions()` to prevent OpenAI 400 empty string error on repeated runs
- Silent catch for shutdown-phase errors in `unified_llm_client.py`

## [1.0.8] - 2026-04-28

### Fixed
- `semantic_mapper.py`: nested f-string quote syntax incompatible with Python 3.11 (pre-compute list before f-string)
- `tests/test_make_embed.py`, `tests/test_make_embed_integration.py`: corrupted `\r\r\n` line endings causing `SyntaxError` on collection

## [1.0.7] — 2026-04-22

### Added
- `inprocess_filler.py` — direct in-process PDF filling (no HTTP roundtrip)
- Java utilities: form_field_filler, form_field_rebuilder, form_field_refresher
- Unified LLM client via LiteLLM — OpenAI, Anthropic, Bedrock, Ollama and any provider

### Changed
- `MapperOrchestrator` is now the single public entry point
- Chunking strategy configurable via `mapper_config.ini`
- `pdf-mapper embed` replaces `pdf-mapper make-embed-file`

### Fixed
- Cache invalidation on embed file re-generation
- Field extraction on password-protected PDFs now raises a clear error

---

## [1.0.6] — 2026-03-20

### Added
- GCP Cloud Functions entrypoint
- Azure Functions entrypoint
- Sliding-window chunker for very long PDFs

### Fixed
- Semantic mapper confidence score was always returning 1.0
- S3 storage backend ignoring region when constructing presigned URLs

---

## [1.0.0] — 2026-03-01

### Added
- Initial public release
- PyMuPDF-based field extraction
- Semantic LLM mapping (OpenAI, Anthropic)
- Embed file builder
- PDF form filler
- FastAPI server
- AWS Lambda entrypoint
- Local and S3 storage backends
