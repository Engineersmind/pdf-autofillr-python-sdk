# pdf-autofillr Plugins

Extension framework for the pipeline. Six folders:

| Folder | PyPI package | Contents |
|--------|-------------|----------|
| `core/` | `pdf-autofiller-core` | Shared abstract interfaces and utilities |
| `pdf_autofillr/` | `pdf-autofiller-plugins` | Full plugin SDK (manager, registry, 7 interfaces) |
| `mapper/` | — | Mapper-specific plugin examples and entrypoints |
| `chatbot/` | — | Chatbot-specific plugin examples |
| `doc_upload/` | — | Doc upload plugin examples |
| `rag/` | — | RAG plugin examples |

## Install

```bash
pip install pdf-autofiller-core
pip install pdf-autofiller-plugins
```

## Plugin types (from pdf_autofillr/)

`ExtractorPlugin` · `MapperPlugin` · `ChunkerPlugin` · `EmbedderPlugin` · `ValidatorPlugin` · `FillerPlugin` · `TransformerPlugin`

## Quick example

```python
from pdf_autofiller_plugins import plugin, PluginManager
from pdf_autofiller_plugins.interfaces import ValidatorPlugin

@plugin(category="validator", name="my-validator", version="1.0.0")
class MyValidator(ValidatorPlugin):
    def validate(self, field_name, value, context):
        return {"valid": bool(value), "error": None}

manager = PluginManager()
manager.load_plugin(MyValidator)
```

See [`plugins/pdf_autofillr/examples/`](pdf_autofillr/examples/) for full examples.
