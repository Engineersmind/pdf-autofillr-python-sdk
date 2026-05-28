# Changelog

All notable changes to `pdf-autofiller-plugins` are documented here.
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

## [0.1.0] - 2026-04-22

### Added
- Initial release of the plugin framework
- `PluginManager` — loads, validates, and executes plugins
- `PluginRegistry` — central registry for plugin discovery
- `@plugin` decorator — register a class as a plugin
- 7 plugin interfaces: `BasePlugin`, `ExtractorPlugin`, `MapperPlugin`, `EmbedderPlugin`, `FillerPlugin`, `ChunkerPlugin`, `TransformerPlugin`, `ValidatorPlugin`
- Example plugins: email validator, invoice extractor, ML mapper
