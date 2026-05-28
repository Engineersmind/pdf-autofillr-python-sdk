# extractor/entrypoints/cli.py
"""
Command-line interface.

Usage::

    doc-upload-cli --document investor.pdf --schema configs/form_keys.json
    doc-upload-cli --document doc.docx --output filled.json --report
    doc-upload-cli --help

Options:
    --document     PATH    Source document (PDF/DOCX/PPTX/XLSX/CSV/JSON/MD/TXT)
    --schema       PATH    Schema JSON path (default: configs/form_keys.json)
    --output       PATH    Save extracted JSON to file
    --job-id       ID      Job identifier (auto-generated if omitted)
    --report               Print execution summary at end
    --log-level    LEVEL   DEBUG | INFO | WARNING | ERROR (default: WARNING)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv()


def _build_client():
    from pdf_autofillr_doc_upload import DocUploadClient
    from pdf_autofillr_doc_upload.extraction.extractor import Extractor
    from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient
    from pdf_autofillr_doc_upload.storage.factory import StorageFactory

    storage = StorageFactory.create()
    extractor = Extractor(llm_client=LLMClient())

    pdf_filler = None  # DocUploadClient._build_default_filler handles this from env

    return DocUploadClient(storage=storage, extractor=extractor, pdf_filler=pdf_filler)


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
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.WARNING))

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
        log.get("summary", {})
        print(f"\nJob ID  : {job_id}")
        print(f"Fields  : {len(result['output_flat'])}")
        print(f"Success : {result['success']}")
        print(f"Errors  : {len(result.get('errors', []))}")


if __name__ == "__main__":
    main()
