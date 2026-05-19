# pdf-autofillr-doc-upload — Plugin Examples

Plugin examples and entrypoint extensions specific to the doc_upload package.

## Adding plugins to doc_upload

1. Create your plugin class (see [plugins/pdf_autofillr/](../pdf_autofillr/))
2. Register it before starting the server:

```python
from pdf_autofiller_plugins import PluginManager

manager = PluginManager()
manager.auto_discover("plugins/doc_upload/")
```

## Available plugin hooks in doc_upload

See `packages/doc_upload/src/` for where plugins are loaded in the pipeline.

## Examples

Drop your plugin files here — they will be auto-discovered.
