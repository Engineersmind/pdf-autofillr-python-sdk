# pdf-autofiller-core

Shared abstract interfaces and utilities — zero dependencies.

## Install

```bash
pip install pdf-autofiller-core
# or from source:
pip install -e plugins/core
```

## What's inside

- `StorageInterface` — abstract base for all storage backends (local, S3, Azure, GCS)
- `HandlerInterface` — abstract base for all handlers
- 15+ utility functions in `pdf_autofiller_core/utils/`

## Usage

```python
from pdf_autofiller_core.interfaces import StorageInterface

class MyStorage(StorageInterface):
    def upload(self, local_path, remote_path): ...
    def download(self, remote_path, local_path): ...
    def exists(self, remote_path): ...
    def list(self, prefix): ...
```

See `examples/` for full implementations.
