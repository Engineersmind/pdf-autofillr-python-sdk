# Changelog — pdf-autofillr-doc-upload

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
