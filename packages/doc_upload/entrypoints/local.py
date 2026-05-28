# extractor/entrypoints/local.py
"""
Local deployment entrypoint — interactive CLI for development.

Usage::

    python -m entrypoints.local

Or non-interactively::

    python -m entrypoints.local --document investor.pdf --schema configs/form_keys.json
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import uuid
import warnings
from pathlib import Path

from dotenv import load_dotenv

# Suppress Python warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

# Force UTF-8 output on Windows so Unicode arrows/emoji in log messages don't crash
import sys as _sys  # noqa: E402

if hasattr(_sys.stdout, "reconfigure"):
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(level=logging.WARNING)
logging.getLogger("pdf_autofillr_doc_upload").setLevel(
    logging.DEBUG
    if os.getenv("DOC_UPLOAD_DEBUG_LOGGING", "").lower() == "true"
    else logging.INFO
)
logging.getLogger("pdf_autofillr_mapper").setLevel(logging.ERROR)
logging.getLogger("pymupdf").setLevel(logging.ERROR)
logging.getLogger("fitz").setLevel(logging.ERROR)


# ── Silence PyMuPDF advisory print ──────────────────────────────────────────


class _FitzSilencer:
    _NOISE = "Consider using the pymupdf_layout package"

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def write(self, s):
        if self._NOISE in s:
            return len(s)
        # On Windows the console may be cp1252 which cannot encode Unicode
        # arrows/emoji used in log messages. Encode to UTF-8 and replace
        # unmappable chars rather than crashing.
        try:
            return self._wrapped.write(s)
        except (UnicodeEncodeError, UnicodeDecodeError):
            safe = s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            return self._wrapped.write(safe)

    def flush(self):
        return self._wrapped.flush()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


def _silence_fitz_import() -> None:
    _real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        import fitz  # noqa: F401

        try:
            from pdf_autofillr_doc_upload.extraction.document_reader import (
                _read_pdf,  # noqa: F401
            )  # noqa
        except Exception:
            pass
    except ImportError:
        pass
    finally:
        sys.stdout = _real
    sys.stdout = _FitzSilencer(sys.stdout)


_silence_fitz_import()


# ── Client builder ───────────────────────────────────────────────────────────


def _build_client():
    from pdf_autofillr_doc_upload import DocUploadClient
    from pdf_autofillr_doc_upload.extraction.extractor import Extractor
    from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient
    from pdf_autofillr_doc_upload.storage.factory import StorageFactory
    from pdf_autofillr_doc_upload.telemetry.collector import TelemetryCollector
    from pdf_autofillr_doc_upload.telemetry.config import TelemetryConfig

    storage = StorageFactory.create()
    llm = LLMClient()
    extractor = Extractor(llm_client=llm)

    # pdf_filler is built automatically by DocUploadClient from env vars
    # DOC_UPLOAD_PDF_FILLER=mapper + MAPPER_API_URL set   -> HTTP filler
    # DOC_UPLOAD_PDF_FILLER=mapper + MAPPER_API_URL empty -> in-process filler
    pdf_filler = None  # DocUploadClient._build_default_filler handles this

    telemetry_mode = os.getenv("DOC_UPLOAD_TELEMETRY", "off").lower()
    telemetry = TelemetryCollector(
        TelemetryConfig() if telemetry_mode != "off" else None
    )

    return DocUploadClient(
        storage=storage,
        extractor=extractor,
        pdf_filler=pdf_filler,
        telemetry=telemetry,
    )


# ── Argument parser ──────────────────────────────────────────────────────────


def _parse_args():
    p = argparse.ArgumentParser(
        prog="doc-upload-local", description="Extractor local runner"
    )
    p.add_argument("--document", "-d", default=None, help="Path to source document")
    p.add_argument("--schema", "-s", default=None, help="Path to schema JSON")
    p.add_argument("--output", "-o", default=None, help="Output JSON path")
    p.add_argument("--job-id", default=None)
    p.add_argument("--user-id", default=None)
    p.add_argument("--pdf-doc-id", default=None)
    p.add_argument("--session-id", default=None)
    p.add_argument("--investor-type", default="Individual")
    return p.parse_args()


# ── Interactive REPL ─────────────────────────────────────────────────────────


def run_interactive():
    print("\n" + "=" * 60)
    print("  pdf-autofillr-doc-upload — Interactive Local Runner")
    print("=" * 60)
    print("Type 'exit' to quit.\n")

    client = _build_client()

    try:
        document = input("Document path: ").strip()
        if document.lower() in ("exit", "quit"):
            return

        schema = input("Schema path [configs/form_keys.json]: ").strip()
        if not schema:
            schema = "configs/form_keys.json"

        output = input("Output path [leave blank to skip]: ").strip() or None

        job_id = str(uuid.uuid4())
        print(f"\nJob ID: {job_id}")
        print("-" * 60)

        result = client.run(
            document_path=document,
            schema_path=schema,
            job_id=job_id,
            output_path=output,
        )

        print("\n" + "=" * 60)
        print("  Extraction complete!")
        print("=" * 60)
        print(json.dumps(result["output_flat"], indent=2, default=str))

        if output:
            print(f"\n✅ Output saved to: {output}")

        filled = result.get("filled_pdf_path")
        if filled:
            print(f"✅ PDF filled:  {filled}")

    except (KeyboardInterrupt, EOFError):
        print("\nSession ended.")
    except OSError as e:
        print(f"\n❌ Configuration error:\n{e}")
        sys.exit(1)


# ── Non-interactive run ──────────────────────────────────────────────────────


def run_with_args(args):
    client = _build_client()
    job_id = args.job_id or str(uuid.uuid4())

    result = client.run(
        document_path=args.document,
        schema_path=args.schema or "configs/form_keys.json",
        job_id=job_id,
        output_path=args.output,
        investor_type=args.investor_type,
        user_id=args.user_id,
        pdf_doc_id=args.pdf_doc_id,
        session_id=args.session_id or (str(uuid.uuid4()) if args.pdf_doc_id else None),
    )

    print("\n" + "=" * 60)
    print("  Extraction complete!")
    print("=" * 60)
    print(json.dumps(result["output_flat"], indent=2, default=str))

    if args.output:
        print(f"\n✅ Output saved to: {args.output}")


# ── Entry ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = _parse_args()
    if args.document:
        run_with_args(args)
    else:
        run_interactive()
