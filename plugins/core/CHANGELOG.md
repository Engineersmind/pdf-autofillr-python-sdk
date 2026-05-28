# Changelog

All notable changes to `pdf-autofiller-core` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Changed

- All packages: added `ruff`, `isort`, `flake8` to `[dev]` dependencies
- All packages: added `[tool.ruff]`, `[tool.isort]` config sections to `pyproject.toml`
- CI: new `ci.yml` workflow for lint and type checking (black, isort, ruff, mypy) across all packages
- CI: new `release.yml` workflow adds lint and type gate before publish, plus GitHub Release creation with changelog notes

---



## [1.0.0] - 2026-04-22

### Added
- Initial release of the core shared library
- `StorageInterface` — abstract base for S3, Azure Blob, GCS, and local storage backends
- `StorageConfig` — unified storage configuration model
- `HandlerInterface` — abstract base for all module handlers
- `HandlerRequest` / `HandlerResponse` — standard request/response models
- `common_utils` — shared utility functions used across all modules
