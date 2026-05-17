# Changelog

All notable changes across all pdf-autofillr packages are documented here.
Each package also maintains its own `CHANGELOG.md` inside `packages/<module>/`.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/)

---

## Packages

| Package | Latest | Changelog |
|---------|--------|-----------|
| pdf-autofillr (umbrella) | 1.1.4 | [packages/pdf_autofillr/CHANGELOG.md](packages/pdf_autofillr/CHANGELOG.md) |
| pdf-autofillr-mapper | 1.0.10 | [packages/mapper/CHANGELOG.md](packages/mapper/CHANGELOG.md) |
| pdf-autofillr-chatbot | 0.3.0 | [packages/chatbot/CHANGELOG.md](packages/chatbot/CHANGELOG.md) |
| pdf-autofillr-doc-upload | 0.1.5 | [packages/doc_upload/CHANGELOG.md](packages/doc_upload/CHANGELOG.md) |
| pdf-autofillr-rag | 0.2.4 | [packages/rag/CHANGELOG.md](packages/rag/CHANGELOG.md) |
| pdf-autofiller-core | 1.0.0 | [plugins/core/CHANGELOG.md](plugins/core/CHANGELOG.md) |
| pdf-autofiller-plugins | 0.1.0 | [plugins/pdf_autofillr/CHANGELOG.md](plugins/pdf_autofillr/CHANGELOG.md) |

---

## [Unreleased]

---

## [umbrella-1.1.4] — 2026-05-16

### Fixed
- Bumped mapper to 1.0.10 — catch interpreter shutdown in `semantic_mapper.py`

---

## [umbrella-1.1.3] — 2026-05-16

### Fixed
- Bumped all sub-package minimums: chatbot 0.3.0, doc-upload 0.1.5, mapper 1.0.10, rag 0.2.4
- Suppressed PyMuPDF layout warning globally
- Resolved interpreter shutdown noise after chatbot/doc-upload sessions
- Fixed OpenAI 400 empty string error on repeated RAG prediction calls

---

## [mapper-1.0.10] — 2026-05-16

### Fixed
- Catch interpreter shutdown `RuntimeError` in `semantic_mapper.py` `process_batch()` and `process_and_save()` to suppress noisy shutdown errors

---

## [mapper-1.0.9] — 2026-05-16

### Fixed
- Suppress `PYMUPDF_SUGGEST_LAYOUT_ANALYZER` warning globally via `os.environ.setdefault` in `detailed_fitz.py`
- Silent catch for `cannot schedule new futures after interpreter shutdown` in `get_form_fields_points.py`
- Demote shutdown-phase RAG API errors to debug level in `operations.py`
- Filter empty-context fields before calling `RAGPDFClient.get_predictions()` to prevent OpenAI 400 empty string error on repeated runs
- Silent catch for shutdown-phase errors in `unified_llm_client.py`

---

## [chatbot-0.3.0] — 2026-05-16

### Fixed
- Suppress interpreter shutdown errors from background PDF fill thread
- Silent catch for `cannot schedule new futures after interpreter shutdown` in mapper headers
- Demote shutdown-phase RAG API errors to debug level

---

## [doc-upload-0.1.5] — 2026-05-16

### Fixed
- Suppress interpreter shutdown errors from background PDF fill thread
- Silent catch for `cannot schedule new futures after interpreter shutdown` in mapper headers
- Demote shutdown-phase RAG API errors to debug level

---

## [rag-0.2.4] — 2026-05-16

### Fixed
- No changes in this package — version bump to stay in sync with mapper 1.0.10 release

---

## [umbrella-1.1.2] — 2026-04-22

### Changed
- All sub-package version pins updated to latest
- Added `chatbot-doc-upload`, `doc-upload-rag`, `chatbot-rag` combination extras
- Cloud extras (`s3`, `gcp`, `azure`) are now additive and independent of module extras
- RAG vector store extras exposed at umbrella level: `rag-pinecone`, `rag-chroma`, `rag-weaviate`

---

## [mapper-1.0.8] — 2026-04-28

### Fixed
- `semantic_mapper.py`: nested f-string quote syntax incompatible with Python 3.11 — pre-compute list before f-string
- `tests/test_make_embed.py`, `tests/test_make_embed_integration.py`: corrupted `\r\r\n` line endings causing `SyntaxError` on collection

---

## [chatbot-0.2.9] — 2026-04-28

### Added
- `src/chatbot/limits/__init__.py`, `src/chatbot/limits/rate_limiter.py`: stub `RateLimiter` so `test_rate_limiter.py` passes CI

---

## [rag-0.2.3] — 2026-04-28

### Added
- `LiteLLMEmbeddingBackend` — any embedding provider via LiteLLM (Cohere, Vertex, Mistral, etc.)
- `LiteLLMCorrectorBackend` — any LLM corrector via LiteLLM
- Azure Blob vector store backend (`AzureVectorStore`)
- GCS vector store backend (`GCSVectorStore`)
- Azure Blob storage backend (`AzureStorage`) and GCS storage backend (`GCSStorage`)
- `ragpdf-setup` CLI — one-time bootstrap (creates configs, data dirs, copies seed vectors)
- `ragpdf system-info` — prints vector count, active users, PDFs processed, storage backend
- Time-series metrics at 5 levels: `pdf_hash` · `category` · `subcategory` · `doctype` · `global`
- `TimeSeriesService`, `CaseClassifier`, `AnalyticsService`, `MetricsService`
- Azure Functions and GCP Cloud Functions entrypoints

### Changed
- Ships with 137 pre-built LP Subscription Agreement vectors (OpenAI `text-embedding-3-small`, 1536-dim)
- `RAGPDFClient.from_env()` is now the recommended constructor
- Prediction pipeline returns typed `PredictionResult`; feedback pipeline returns typed `FeedbackResult`

### Fixed
- `find_by_name()` was using hardcoded local path instead of configured vector store backend
- ChromaDB constructor: `collection_name=` renamed to `collection=`
- `CorrectionResult` dataclass missing from `correctors/base.py`
- `NoOpEmbeddingBackend` not exported from top-level `ragpdf.__init__`
- `managed/__init__.py` was an empty stub

---

## [mapper-1.0.7] — 2026-04-22

### Added
- `inprocess_filler.py` — direct in-process PDF filling without HTTP roundtrip
- Java utilities: `form_field_filler`, `form_field_rebuilder`, `form_field_refresher`
- Unified LLM client via LiteLLM — OpenAI, Anthropic, Bedrock, Ollama, and any provider

### Changed
- `MapperOrchestrator` is now the single public entry point
- Chunking strategy configurable via `mapper_config.ini`
- `pdf-mapper embed` replaces `pdf-mapper make-embed-file`

### Fixed
- Cache invalidation on embed file re-generation
- Field extraction on password-protected PDFs now raises a clear error

---

## [chatbot-0.2.8] — 2026-04-22

### Added
- `sequential_fill_handler` — fills fields one by one without full state machine
- `telemetry/collector.py` — session metrics: turns, duration, field coverage
- Azure Blob and GCS storage backends

### Changed
- State machine handlers are now composable
- `chatbot_PDF_FILLER=mapper` is the new default (was `none`)
- Config samples reorganised into investor-type subfolders

### Fixed
- Boolean group handler skipping optional fields incorrectly
- Mailing address check handler not triggering on partial address input
- Rate limiter test was flaky under parallel test runners

---

## [doc-upload-0.1.4] — 2026-04-22

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

## [core-1.0.0] — 2026-04-22

### Added
- Initial release
- `StorageInterface` — abstract base for all storage backends
- `HandlerInterface` — abstract base for all handlers
- `common_utils` — 15+ shared utility functions

---

## [plugins-0.1.0] — 2026-04-22

### Added
- Initial release
- `PluginManager` — loads, validates, executes plugins
- `PluginRegistry` — central registry with auto-discovery
- `@plugin` decorator — register any class as a plugin
- 7 plugin interfaces: `BasePlugin`, `ExtractorPlugin`, `MapperPlugin`, `ChunkerPlugin`, `EmbedderPlugin`, `ValidatorPlugin`, `FillerPlugin`, `TransformerPlugin`
- Example plugins: email validator, invoice extractor, ML mapper

---

## [umbrella-1.1.1] — 2026-03-25

### Added
- `doc-upload-mapper` and `chatbot-mapper` explicit extras (same as `doc-upload` / `chatbot` but self-documenting)

---

## [chatbot-0.2.7] — 2026-03-25

### Added
- `update_existing_handler` — lets users correct previously entered values
- `optional_fields_handler` — collects non-required fields at end of session
- S3 storage backend

### Fixed
- Session state not persisted correctly when PDF filler raised an exception

---

## [rag-0.2.0] — 2026-03-25

### Added
- Pinecone, ChromaDB, and Weaviate vector store backends
- `AnthropicCorrectorBackend` — Claude-based field name correction
- Full 5-case classification engine (CASE_A through CASE_E)
- Confidence decay on repeated errors; confidence growth on successful fills
- Embedding regeneration triggered when confidence drops below threshold
- `processing_pipeline.py` — orchestrates prediction + correction + vector update in one pass

### Changed
- Vector store interface now requires `find_by_name(field_name)` on all backends
- Prediction now returns top-3 candidates with scores

### Fixed
- `FeedbackPipeline` silently failing on CASE_B/CASE_C with remote vector stores
- `S3VectorStore` not respecting `bucket` prefix when listing vectors

---

## [mapper-1.0.6] — 2026-03-20

### Added
- GCP Cloud Functions entrypoint
- Azure Functions entrypoint
- Sliding-window chunker for very long PDFs

### Fixed
- Semantic mapper confidence score always returning 1.0
- S3 storage backend ignoring region when constructing presigned URLs

---

## [doc-upload-0.1.3] — 2026-03-20

### Added
- XLSX and CSV input format support
- `inprocess_filler` — direct mapper integration without HTTP

### Fixed
- JSON extraction failing on nested objects deeper than 2 levels

---

## [rag-0.1.1] — 2026-03-10

### Fixed
- Added `CorrectionResult` dataclass to `correctors/base.py`
- Added `find_by_name(field_name)` to `VectorStoreBackend` base class and all implementations
- `FeedbackPipeline._find_vector_by_name()` now delegates to `vector_store.find_by_name()`
- `ChromaStore` constructor: `collection_name=` → `collection=`
- Exported `NoOpEmbeddingBackend` from `ragpdf.__init__` and `__all__`

---

## [mapper-1.0.0] — 2026-03-01

### Added
- Initial public release
- PyMuPDF-based field extraction
- Semantic LLM mapping (OpenAI, Anthropic)
- Embed file builder and PDF form filler
- FastAPI server and AWS Lambda entrypoint
- Local and S3 storage backends

---

## [chatbot-0.2.0] — 2026-03-10

### Added
- Initial public release
- Conversation engine with state machine
- LLM-based field extraction from transcript
- Per-state handlers: init, investor type, data collection, missing fields, boolean groups
- FastAPI server, CLI, and AWS Lambda entrypoint
- Local storage backend

---

## [doc-upload-0.1.0] — 2026-03-10

### Added
- Initial public release
- PDF, DOCX, TXT, MD, JSON input formats
- LLM-based field extraction
- Mapper integration (inprocess and HTTP)
- FastAPI server, CLI, and AWS Lambda entrypoint
- Local storage backend

---

## [rag-0.1.0] — 2026-03-10

### Added
- Initial public release
- `RAGPDFClient` with 6 typed methods: `predict`, `submit_feedback`, `get_metrics`, `get_analytics`, `init_vectors`, `system_info`
- Pluggable storage, embedding, vector store, and corrector backends
- Prediction, feedback, and processing pipelines
- Analytics API at pdf, category, subcategory, doctype, and global levels
- FastAPI server, CLI, and AWS Lambda entrypoint
- Full unit and integration test suites (no API keys required)

---

## [umbrella-1.0.0] — 2026-03-10

### Added
- Initial public release
- Zero hard dependencies — all installs via extras
- `pdf-autofillr setup` — generates `.env.example`, `configs/`, `data/` for installed combination
- `pdf-autofillr status` — verifies installation and configuration