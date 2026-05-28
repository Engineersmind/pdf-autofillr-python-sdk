# extractor/entrypoints/server.py
"""
Uvicorn server entrypoint.

Usage::

    doc-upload-server
    python -m entrypoints.server
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required: pip install 'pdf-autofillr-doc-upload[server]'")
        sys.exit(1)

    uvicorn.run(
        "entrypoints.fastapi_app:app",
        host=os.getenv("DOC_UPLOAD_HOST", "0.0.0.0"),
        port=int(os.getenv("DOC_UPLOAD_PORT", "8001")),
        reload=os.getenv("DOC_UPLOAD_RELOAD", "false").lower() == "true",
        log_level=os.getenv("DOC_UPLOAD_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
