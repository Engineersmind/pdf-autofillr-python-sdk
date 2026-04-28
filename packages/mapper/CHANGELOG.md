# Changelog — pdf-autofillr-mapper

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
