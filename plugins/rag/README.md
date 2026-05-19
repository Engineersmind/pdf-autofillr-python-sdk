# pdf-autofillr-rag — Plugin Examples

Plugin examples and entrypoint extensions specific to the rag package.

## Adding plugins to rag

1. Create your plugin class (see [plugins/pdf_autofillr/](../pdf_autofillr/))
2. Register it before starting the server:

```python
from pdf_autofiller_plugins import PluginManager

manager = PluginManager()
manager.auto_discover("plugins/rag/")
```

## Available plugin hooks in rag

See `packages/rag/src/` for where plugins are loaded in the pipeline.

## Examples

Drop your plugin files here — they will be auto-discovered.
