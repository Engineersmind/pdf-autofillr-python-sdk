# Changelog

All notable changes to `pdf-autofiller-core` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] - 2026-04-22

### Added
- Initial release of the core shared library
- `StorageInterface` — abstract base for S3, Azure Blob, GCS, and local storage backends
- `StorageConfig` — unified storage configuration model
- `HandlerInterface` — abstract base for all module handlers
- `HandlerRequest` / `HandlerResponse` — standard request/response models
- `common_utils` — shared utility functions used across all modules
