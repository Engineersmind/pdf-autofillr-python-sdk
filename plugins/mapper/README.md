# pdf-autofillr-mapper — Plugin Examples

Plugin examples and entrypoint extensions specific to the mapper package.

## Adding plugins to mapper

1. Create your plugin class (see [plugins/pdf_autofillr/](../pdf_autofillr/))
2. Register it before starting the server:

```python
from pdf_autofiller_plugins import PluginManager

manager = PluginManager()
manager.auto_discover("plugins/mapper/")
```

## Available plugin hooks in mapper

See `packages/mapper/src/` for where plugins are loaded in the pipeline.

## Examples

Drop your plugin files here — they will be auto-discovered.
