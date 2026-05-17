# Plugin Framework

Extend any stage of the pipeline.

## Install

```bash
pip install pdf-autofiller-core      # shared interfaces
pip install pdf-autofiller-plugins   # plugin SDK
```

## Plugin types

| Plugin | Interface | Extends |
|--------|-----------|---------|
| Extractor | `ExtractorPlugin` | PDF field detection |
| Mapper | `MapperPlugin` | LLM field-to-schema mapping |
| Chunker | `ChunkerPlugin` | Document chunking |
| Embedder | `EmbedderPlugin` | Embedding generation |
| Validator | `ValidatorPlugin` | Field value validation |
| Filler | `FillerPlugin` | PDF writing |
| Transformer | `TransformerPlugin` | Value transformation before fill |

## Create a plugin

```python
from pdf_autofiller_plugins import plugin, PluginManager
from pdf_autofiller_plugins.interfaces import ValidatorPlugin

@plugin(category="validator", name="ssn-validator", version="1.0.0")
class SSNValidatorPlugin(ValidatorPlugin):
    def validate(self, field_name, value, context):
        import re
        valid = bool(re.match(r"^\d{3}-\d{2}-\d{4}$", value))
        return {"valid": valid, "error": None if valid else "Invalid SSN"}

manager = PluginManager()
manager.load_plugin(SSNValidatorPlugin)
results = manager.run_validators("ssn", "123-45-6789", context={})
```

## Examples

See [`plugins/pdf_autofillr/examples/`](../../plugins/pdf_autofillr/examples/):
- `email_validator_plugin.py`
- `invoice_extractor_plugin.py`
- `ml_mapper_plugin.py`
- `using_plugins.py`
