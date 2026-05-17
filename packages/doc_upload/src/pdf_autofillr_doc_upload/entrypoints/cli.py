# modules/doc_upload/src/pdf_autofillr_doc_upload/entrypoints/cli.py
"""
Command-line interface.

Usage::

    doc-upload-cli --document investor.pdf --schema configs/form_keys.json
    doc-upload-cli --document doc.docx --output filled.json --report
    doc-upload-cli --help
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

import argparse
import json
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def _setup_logging(log_level: str = "WARNING") -> None:
    log_dir = Path(os.getcwd()) / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "doc_upload.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    ))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    for name in [
        "LiteLLM", "litellm", "httpx", "httpcore", "openai",
        "pdf_autofillr_doc_upload", "ragpdf", "urllib3", "asyncio",
    ]:
        logging.getLogger(name).setLevel(logging.WARNING)

    for name in [
        "pdf_autofillr_mapper",
        "pdf_autofillr_mapper.mappers.semantic_mapper",
        "pdf_autofillr_mapper.extractors.detailed_fitz",
        "pdf_autofillr_mapper.orchestrator.PDFPipeline",
        "pdf_autofillr_mapper.embedders.embed_keys",
        "pdf_autofillr_mapper.groupers.group_by_llm",
        "pdf_autofillr_mapper.clients.unified_llm_client",
        "pdf_autofillr_mapper.utils.storage",
        "pdf_autofillr_mapper.chunkers",
        "pdf_autofillr_mapper.inprocess_filler",
    ]:
        logging.getLogger(name).setLevel(logging.ERROR)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    root.addHandler(console)


def _build_client():
    from pdf_autofillr_doc_upload import DocUploadClient
    from pdf_autofillr_doc_upload.storage.factory import StorageFactory
    from pdf_autofillr_doc_upload.extraction.extractor import Extractor
    from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

    storage = StorageFactory.create()
    extractor = Extractor(llm_client=LLMClient())
    # Do NOT pass pdf_filler=None — let DocUploadClient._build_default_filler()
    # read DOC_UPLOAD_PDF_FILLER from env and wire up the correct filler automatically.
    return DocUploadClient(storage=storage, extractor=extractor)


def _parse_args():
    p = argparse.ArgumentParser(prog="doc-upload-cli")
    p.add_argument("--document", "-d", required=True)
    p.add_argument("--schema", "-s", default="configs/form_keys.json")
    p.add_argument("--output", "-o", default=None)
    p.add_argument("--job-id", default=None)
    p.add_argument("--report", action="store_true")
    p.add_argument("--log-level", default="WARNING")
    return p.parse_args()


def main():
    args = _parse_args()
    _setup_logging(args.log_level)

    client = _build_client()
    job_id = args.job_id or str(uuid.uuid4())

    result = client.run(
        document_path=args.document,
        schema_path=args.schema,
        job_id=job_id,
        output_path=args.output,
    )

    print(json.dumps(result["output_flat"], indent=2, default=str))

    if args.output:
        print(f"\n✅ Output saved to: {args.output}", file=sys.stderr)

    if args.report:
        log = client.storage.get_execution_log(job_id) or {}
        print(f"\nJob ID  : {job_id}")
        print(f"Fields  : {len(result['output_flat'])}")
        print(f"Success : {result['success']}")
        print(f"Errors  : {len(result.get('errors', []))}")


if __name__ == "__main__":
    main()