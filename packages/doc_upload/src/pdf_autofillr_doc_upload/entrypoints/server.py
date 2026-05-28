# modules/doc_upload/src/pdf_autofillr_doc_upload/entrypoints/server.py
"""
Uvicorn server entrypoint.

Usage::

    doc-upload-server
"""

from __future__ import annotations

import os
import sys

# ── UTF-8 fix for Windows ─────────────────────────────────────────────────────
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()


def main():
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required: pip install 'pdf-autofillr-doc-upload[server]'")
        sys.exit(1)

    from pdf_autofillr_doc_upload.entrypoints.fastapi_app import app

    uvicorn.run(
        app,
        host=os.getenv("DOC_UPLOAD_HOST", "0.0.0.0"),
        port=int(os.getenv("DOC_UPLOAD_PORT", "8001")),
        reload=os.getenv("DOC_UPLOAD_RELOAD", "false").lower() == "true",
        log_level=os.getenv("DOC_UPLOAD_LOG_LEVEL", "warning").lower(),
    )


if __name__ == "__main__":
    main()
