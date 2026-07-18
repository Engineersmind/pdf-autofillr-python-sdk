# Changelog — pdf-autofillr-rag

All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

---

## [0.2.6] - 2026-07-18

### Security
- **[High] Path traversal in `LocalStorage`** — `_full_path()`, `load_json()`,
  `load_jsonl()`, and `copy_file()` built filesystem paths from `key` with
  no validation at all (CWE-22). `key` is constructed elsewhere from
  `user_id`/`session_id`/`pdf_id`, which reach here directly from HTTP
  request bodies via the prediction/feedback pipelines — a crafted
  `user_id` like `../../../etc` reached `open()` unchecked. Added
  `_validated_path()`, which resolves the path (following symlinks, not
  just string-normalizing it) and confines it to `data_path` before any
  file operation.
- **[Medium] Log injection** — 10 sites across
  `storage/{s3,gcs,azure,local}_storage.py`,
  `pipeline/{prediction,processing}_pipeline.py`,
  `vector_stores/{pinecone,local_vector}_store.py`, and
  `services/case_classifier.py` interpolated user-controlled values
  (`user_id`, `session_id`, `pdf_id`, `vector_id`, `field_name`, storage
  keys) directly into log messages, letting a crafted value forge a fake
  log line via an embedded newline (CWE-117). Added a shared
  `safe_for_log()` helper in `utils/helpers.py` and applied it at every
  flagged call site.

### Fixed
- `LocalStorage`'s confinement check now uses `Path.is_relative_to()`
  instead of string prefix matching, for a more robust, semantic
  containment check (equivalent behavior, cleaner implementation).
- Fixed a docstring in `safe_for_log()` that said it "strips" characters
  when it actually replaces them with a visible escape sequence.

### Testing
- Added unit tests for `safe_for_log()` covering newline, carriage
  return, and CRLF escaping, plus a realistic forged-log-line case and
  non-string input.
- Added rejection-case unit tests for `LocalStorage`'s path confinement:
  `../..` traversal on every affected method, an absolute path outside
  `data_path`, and — most importantly — a real symlink created inside
  `data_path` pointing outside it, confirming the switch from
  `os.path.normpath` to `Path.resolve()` actually closes that escape
  (the test is skipped, not failed, on platforms without symlink
  support).

## [0.2.5] - 2026-07-14

### Security
- **[High] Hardcoded default API key** — `EXPECTED_API_KEY` fell back to the
  literal string `"dev-key"` when `RAGPDF_API_KEY` wasn't set, so any
  deployment that forgot to configure it was protected by a publicly-known
  credential (CWE-798). There is no default now: the server fails closed
  with a config error unless `RAGPDF_API_KEY` is set, or
  `RAGPDF_ALLOW_INSECURE_NO_AUTH=true` is explicitly set for local dev.
- API key comparison uses `hmac.compare_digest` to avoid timing side-channels.

### Added
- `RAGPDF_ALLOW_INSECURE_NO_AUTH` — explicit opt-in to run without auth
  (local dev only).

## [Unreleased]

### Changed
- All packages: added `ruff`, `isort`, `flake8` to `[dev]` dependencies
- All packages: added `[tool.ruff]`, `[tool.isort]` config sections to `pyproject.toml`
- CI: new `ci.yml` workflow for lint and type checking (black, isort, ruff, mypy) across all packages
- CI: new `release.yml` workflow adds lint and type gate before publish, plus GitHub Release creation with changelog notes

---

## [0.2.4] - 2026-05-16

### Fixed
- No changes in this package — version bump to stay in sync with mapper 1.0.10 release

## [0.2.3] — 2026-04-28

### Added
- `LiteLLMEmbeddingBackend` — use any embedding provider via LiteLLM (Cohere, Vertex, Mistral, etc.)
- `LiteLLMCorrectorBackend` — use any LLM corrector via LiteLLM
- Azure Blob vector store backend (`AzureVectorStore`)
- GCS vector store backend (`GCSVectorStore`)
- Azure Blob storage backend (`AzureStorage`)
- GCS storage backend (`GCSStorage`)
- `ragpdf-setup` CLI command — one-time bootstrap (creates configs, data dirs, copies seed vectors)
- `ragpdf system-info` — prints vector count, active users, PDFs processed, storage backend
- Time-series metrics at 5 levels: `pdf_hash` · `category` · `subcategory` · `doctype` · `global`
- `TimeSeriesService` — tracks accuracy trends over time per dimension
- `CaseClassifier` — classifies each feedback event into CASE_A through CASE_E
- `AnalyticsService` — aggregated analytics across users, sessions, categories
- `MetricsService` — per-run accuracy, coverage, confidence, agreement, recovery, case distribution
- Optional extras: `[azure]`, `[gcs]`, `[litellm]`, `[azure_func]`, `[gcp_func]`
- Azure Functions entrypoint (`entrypoints/azure_function.py`)
- GCP Cloud Functions entrypoint (`entrypoints/gcp_function.py`)

### Changed
- Ships with **137 pre-built LP Subscription Agreement vectors** (OpenAI `text-embedding-3-small`, 1536-dim) — ready to use without running `init-vectors`
- `RAGPDFClient.from_env()` is now the recommended constructor
- `ragpdf predict` CLI now accepts `--user`, `--session`, `--pdf` flags
- `ragpdf feedback` CLI now accepts `--errors` as a path to JSON file
- `ragpdf metrics` CLI now accepts `--type` flag (`global`, `category`, `pdf_hash`, etc.)
- Prediction pipeline returns typed `PredictionResult` with `.predictions`, `.confidence`, `.case`
- Feedback pipeline returns typed `FeedbackResult` with `.vectors_updated`, `.cases`

### Fixed
- `find_by_name()` was using hardcoded `vectors/vector_database.json` path instead of the configured vector store backend — caused silent failures with Pinecone, Chroma, Weaviate on CASE_B/CASE_C feedback
- ChromaDB constructor: `collection_name=` renamed to `collection=`
- `CorrectionResult` dataclass missing from `correctors/base.py` — was referenced in examples but not exported
- `NoOpEmbeddingBackend` not exported from top-level `ragpdf.__init__` and `__all__`
- `FeedbackPipeline._find_vector_by_name()` now delegates to `vector_store.find_by_name()` across all backends
- Custom corrector example used wrong method name (`generate_corrected_field_name`) and returned undefined type
- `managed/__init__.py` was an empty stub — replaced with descriptive module placeholder

---

## [0.2.0] — 2026-03-25

### Added
- Pinecone vector store backend (`PineconeStore`)
- ChromaDB vector store backend (`ChromaStore`)
- Weaviate vector store backend (`WeaviateStore`)
- `AnthropicCorrectorBackend` — Claude-based field name correction
- Full 5-case classification engine:
  - **CASE_A** — exact vector match, high confidence → accept as-is
  - **CASE_B** — near match found → LLM corrects
  - **CASE_C** — weak match → LLM corrects, vector added
  - **CASE_D** — no match → LLM predicts from schema, vector added
  - **CASE_E** — LLM uncertain → flagged for human review
- Confidence decay on repeated errors, confidence growth on successful fills
- Embedding regeneration triggered automatically when confidence drops below threshold
- `processing_pipeline.py` — orchestrates prediction + correction + vector update in one pass
- Optional extras: `[pinecone]`, `[chroma]`, `[weaviate]`, `[anthropic]`

### Changed
- Vector store interface now requires `find_by_name(field_name)` on all backends
- Prediction now returns top-3 candidates with scores, not just top-1

### Fixed
- `FeedbackPipeline` silently failing on CASE_B/CASE_C when using remote vector stores (Pinecone/Chroma/Weaviate) — `find_by_name()` was only implemented on `LocalVectorStore`
- S3VectorStore not respecting `bucket` prefix when listing vectors

---

## [0.1.1] — 2026-03-10

### Added
- `tests/unit/test_find_by_name.py` — unit tests for `find_by_name()` across all vector store implementations

### Fixed
- Added `CorrectionResult` dataclass to `correctors/base.py` — was referenced in examples but missing from the codebase
- Added `find_by_name(field_name)` to `VectorStoreBackend` base class and all 5 implementations (Local, S3, Pinecone, Chroma, Weaviate)
- `FeedbackPipeline._find_vector_by_name()` now calls `vector_store.find_by_name()` instead of hardcoded `vectors/vector_database.json`
- `ChromaStore` constructor: `collection_name=` → `collection=`
- Custom corrector example: wrong method name `generate_corrected_field_name`, now returns `dict` instead of undefined `CorrectionResult`
- Exported `NoOpEmbeddingBackend` from `ragpdf.__init__` and `__all__`
- `managed/__init__.py` updated from empty stub to descriptive placeholder

---

## [0.1.0] — 2026-03-10

### Added
- `RAGPDFClient` — single public entry point with 6 typed methods: `predict`, `submit_feedback`, `get_metrics`, `get_analytics`, `init_vectors`, `system_info`
- Pluggable storage backends: `LocalStorage`, `S3Storage`
- Pluggable embedding backends: `SentenceTransformerBackend`, `OpenAIEmbeddingBackend`
- Pluggable vector store backends: `LocalVectorStore`, `S3VectorStore`
- Pluggable LLM corrector backends: `OpenAICorrectorBackend`, `NoOpCorrectorBackend`
- Prediction pipeline (`pipeline/prediction_pipeline.py`)
- Feedback pipeline (`pipeline/feedback_pipeline.py`)
- Processing pipeline (`pipeline/processing_pipeline.py`)
- `result.py` — typed `PredictionResult` and `FeedbackResult`
- Analytics API: pdf, category, subcategory, doctype, global, compare, pdf_hash, system_info
- Error analytics with date / category / type filters
- FastAPI dev server (`entrypoints/fastapi_app.py`)
- CLI (`entrypoints/cli.py`) — `ragpdf predict`, `ragpdf feedback`, `ragpdf metrics`, `ragpdf system-info`
- AWS Lambda entrypoint (`entrypoints/aws_lambda.py`)
- Full unit test suite — 7 test files, no API keys required
- Integration test suite with `NoOpEmbeddingBackend` (no API keys)
- GitHub Actions CI/CD
- Optional extras: `[openai]`, `[transformers]`, `[s3]`, `[server]`, `[dev]`
