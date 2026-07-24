# Changelog

All notable changes across all pdf-autofillr packages are documented here.
Each package also maintains its own `CHANGELOG.md` inside `packages/<module>/`.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
Versioning: [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Changed
- All packages: added `ruff`, `isort`, `flake8` to `[dev]` dependencies
- All packages: added `[tool.ruff]`, `[tool.isort]` config sections to `pyproject.toml`
- CI: new `ci.yml` workflow for lint and type checking (black, isort, ruff, mypy) across all packages
- CI: new `release.yml` workflow adds lint and type gate before publish, plus GitHub Release creation with changelog notes

---

## Packages

| Package | Latest | Changelog |
|---------|--------|-----------|
| pdf-autofillr (umbrella) | 1.1.5 | [packages/pdf_autofillr/CHANGELOG.md](packages/pdf_autofillr/CHANGELOG.md) |
| pdf-autofillr-mapper | 1.0.11 | [packages/mapper/CHANGELOG.md](packages/mapper/CHANGELOG.md) |
| pdf-autofillr-chatbot | 0.3.1 | [packages/chatbot/CHANGELOG.md](packages/chatbot/CHANGELOG.md) |
| pdf-autofillr-doc-upload | 0.1.6 | [packages/doc_upload/CHANGELOG.md](packages/doc_upload/CHANGELOG.md) |
| pdf-autofillr-rag | 0.2.5 | [packages/rag/CHANGELOG.md](packages/rag/CHANGELOG.md) |
| pdf-autofiller-core | 1.0.0 | [plugins/core/CHANGELOG.md](plugins/core/CHANGELOG.md) |
| pdf-autofiller-plugins | 0.1.0 | [plugins/pdf_autofillr/CHANGELOG.md](plugins/pdf_autofillr/CHANGELOG.md) |

---

## [umbrella-1.1.5 / mapper-1.0.11 / chatbot-0.3.1 / doc-upload-0.1.6 / rag-0.2.5] — 2026-07-14

### Security
- **[High] Unauthenticated arbitrary local file disclosure** in `doc_upload`'s
  `/extract` endpoint (coordinated disclosure, reported by Farid Narimanov) —
  `document_path`/`schema_path` reached the storage backend with no directory
  restriction. Fixed with an explicit allow-list of directories every request
  path must resolve inside.
- **[High] Auth silently disabled when unconfigured** across `doc_upload`,
  `chatbot`, and `mapper` — each service accepted requests with no API key
  check whenever its key env var was unset. All three now fail closed with a
  config error unless the key is set, or `*_ALLOW_INSECURE_NO_AUTH=true` is
  explicitly set for local dev.
- **[High] Hardcoded default API key** (`"dev-key"`) removed from every `rag`
  entrypoint — the installer now generates a unique random secret per install.
- **[Medium] Path traversal via `user_id`/`session_id`** in `chatbot`'s
  `LocalStorage` — both are now validated as single path segments before any
  filesystem access.
- API key comparisons across all four packages now use
  `hmac.compare_digest` to avoid timing side-channels.

See each package's own `CHANGELOG.md` for full per-package detail.

---

## [umbrella-1.1.2] — 2026-04-22

### Changed
- Extras now map correctly to all 5 packages
- Added `chatbot-doc-upload`, `doc-upload-rag`, `chatbot-rag` combination extras
- Cloud storage extras (`s3`, `gcp`, `azure`) work independently of module extras

---

## [mapper-1.0.7] — 2026-04-22

### Added
- `inprocess_filler.py` — direct in-process PDF filling without HTTP roundtrip
- Java utilities for complex form field operations (filler, rebuilder, refresher)
- Unified LLM client via LiteLLM — supports OpenAI, Anthropic, Bedrock, Ollama, and any provider

### Changed
- `MapperOrchestrator` is now the single public entry point
- Chunking strategy configurable via `mapper_config.ini`

### Fixed
- Cache invalidation on embed file re-generation
- Field extraction on password-protected PDFs now raises a clear error

---

## [chatbot-0.2.8] — 2026-04-22

### Added
- `sequential_fill_handler` — fills fields one by one without state machine complexity
- `telemetry/collector.py` — session metrics (turns, duration, field coverage)
- Azure and GCP storage backends

### Changed
- Chatbot state machine refactored — states are now composable handlers
- `chatbot_PDF_FILLER=mapper` is the new default (was `none`)

### Fixed
- Boolean group handler incorrectly skipping optional fields
- Mailing address check handler not triggering on partial address input

---

## [doc-upload-0.1.4] — 2026-04-22

### Added
- Support for PPTX, XLSX, HTML, XML input formats
- `fallback_extractor` — rule-based extraction when LLM confidence is low
- S3, Azure, GCS storage backends

### Changed
- `DocUploadClient` is now the single public entry point
- Document reader auto-detects format from file extension

### Fixed
- CSV files with quoted commas were split incorrectly
- DOCX files with embedded images caused extraction to hang

---

## [rag-0.2.3] — 2026-04-22

### Added
- Azure Blob and GCS vector store backends
- `LiteLLMEmbeddingBackend` — use any embedding provider via LiteLLM
- `LiteLLMCorrectorBackend` — use any LLM corrector via LiteLLM
- Time-series metrics at 5 levels: pdf_hash / category / subcategory / doctype / global

### Changed
- Ships with 137 pre-built LP Subscription Agreement vectors (OpenAI text-embedding-3-small, 1536-dim)
- `RAGPDFClient.from_env()` is the recommended constructor

### Fixed
- `find_by_name()` was using hardcoded local path instead of configured vector store backend
- ChromaDB collection name parameter renamed to `collection` (was `collection_name`)
- `CorrectionResult` dataclass missing from `correctors/base.py`

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