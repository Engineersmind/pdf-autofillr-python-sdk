# Changelog — pdf-autofillr (umbrella)

## [1.1.3] - 2026-05-16

### Fixed
- Bumped all sub-package minimums: chatbot 0.3.0, doc-upload 0.1.5, mapper 1.0.9, rag 0.2.4
- Suppressed PyMuPDF layout warning globally
- Resolved interpreter shutdown noise after chatbot/doc-upload sessions
- Fixed OpenAI 400 empty string error on repeated RAG predictions calls

## [1.1.2] — 2026-04-22

### Changed
- All sub-package version pins updated to latest
- Added `chatbot-doc-upload`, `doc-upload-rag`, `chatbot-rag` combination extras
- Cloud extras (`s3`, `gcp`, `azure`) are now additive and independent of module extras
- RAG vector store extras exposed at umbrella level: `rag-pinecone`, `rag-chroma`, `rag-weaviate`

---

## [1.1.1] — 2026-03-25

### Added
- `doc-upload-mapper` and `chatbot-mapper` explicit extras (same as `doc-upload` / `chatbot` but self-documenting)

---

## [1.0.0] — 2026-03-10

### Added
- Initial public release
- Zero hard dependencies — all installs via extras
- `pdf-autofillr setup` — generates .env.example, configs/, data/ for installed combination
- `pdf-autofillr status` — verifies installation and configuration
