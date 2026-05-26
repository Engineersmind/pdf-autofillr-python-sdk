# Changelog — pdf-autofillr-mapper

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
