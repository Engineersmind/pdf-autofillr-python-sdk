# Changelog

All notable changes to `pdf-autofiller-plugins` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [0.1.0] - 2026-04-22

### Added
- Initial release of the plugin framework
- `PluginManager` — loads, validates, and executes plugins
- `PluginRegistry` — central registry for plugin discovery
- `@plugin` decorator — register a class as a plugin
- 7 plugin interfaces: `BasePlugin`, `ExtractorPlugin`, `MapperPlugin`, `EmbedderPlugin`, `FillerPlugin`, `ChunkerPlugin`, `TransformerPlugin`, `ValidatorPlugin`
- Example plugins: email validator, invoice extractor, ML mapper
