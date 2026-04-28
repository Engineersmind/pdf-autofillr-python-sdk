# Changelog — pdf-autofillr-doc-upload

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
