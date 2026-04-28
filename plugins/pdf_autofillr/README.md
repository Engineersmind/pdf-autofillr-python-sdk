# pdf-autofiller-plugins

Plugin SDK for extending the pdf-autofillr pipeline.

## Install

```bash
pip install pdf-autofiller-plugins
# or from source:
pip install -e plugins/pdf_autofillr
```

## Plugin types

| Interface | Extends |
|-----------|---------|
| `ExtractorPlugin` | PDF field detection logic |
| `MapperPlugin` | LLM field-to-schema mapping |
| `ChunkerPlugin` | Document chunking strategy |
| `EmbedderPlugin` | Embedding generation |
| `ValidatorPlugin` | Field value validation |
| `FillerPlugin` | PDF writing logic |
| `TransformerPlugin` | Value transformation before fill |

## Create a plugin

```python
from pdf_autofiller_plugins import plugin, PluginManager
from pdf_autofiller_plugins.interfaces import MapperPlugin

@plugin(category="mapper", name="custom-mapper", version="1.0.0")
class CustomMapper(MapperPlugin):
    def map(self, fields, schema_keys, context):
        # your mapping logic
        return {field: schema_keys[0] for field in fields}

manager = PluginManager()
manager.load_plugin(CustomMapper)
```

## Examples

See `examples/` for:
- `email_validator_plugin.py`
- `invoice_extractor_plugin.py`
- `ml_mapper_plugin.py`
- `using_plugins.py`
