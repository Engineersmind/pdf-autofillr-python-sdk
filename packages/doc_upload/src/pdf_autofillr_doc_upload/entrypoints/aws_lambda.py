# extractor/entrypoints/aws_lambda.py
"""
AWS Lambda entrypoint — ports lambda_function.py.

Deploy with::
    handler = entrypoints.aws_lambda.handler

Expected event body::
    {
        "user_id": "42",
        "session_id": "sess_abc",
        "filled_doc_pdf_id": "99",
        "pdf_doc_id": "99",
        "pdf_location": "s3://bucket/path/to/doc.pdf",
        "investor_type": "Individual"       # optional, default: Individual
    }

Required env vars::
    DOC_UPLOAD_LLM_MODEL         e.g. openai/gpt-4.1-mini
    DOC_UPLOAD_LLM_API_KEY       or OPENAI_API_KEY
    DOC_UPLOAD_STORAGE           s3
    AWS_OUTPUT_BUCKET
    AWS_CONFIG_BUCKET
    DOC_UPLOAD_PDF_FILLER        mapper  (optional)
    DOC_UPLOAD_FILL_PDF_LAMBDA_URL
    DOC_UPLOAD_PDF_API_KEY
    AUTH_TOKEN                  optional — validates X-API-Key header
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("DOC_UPLOAD_LOG_LEVEL", "INFO"))

_client = None


def _build_client():
    from pdf_autofillr_doc_upload import DocUploadClient
    from pdf_autofillr_doc_upload.storage.factory import StorageFactory
    from pdf_autofillr_doc_upload.extraction.extractor import Extractor
    from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

    storage = StorageFactory.create()
    extractor = Extractor(llm_client=LLMClient())

    pdf_filler = None  # DocUploadClient._build_default_filler handles this from env

    return DocUploadClient(storage=storage, extractor=extractor, pdf_filler=pdf_filler)


def _get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _parse_body(event: dict) -> dict:
    if "body" in event and isinstance(event["body"], str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body")
    return event


def handler(event: Dict[str, Any], context: Any) -> dict:
    from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger
    log = ExecutionLogger()

    try:
        body = _parse_body(event)
        log.log_input_request(body)

        # ── API key check ──────────────────────────────────────────
        expected_token = os.environ.get("AUTH_TOKEN")
        if expected_token:
            headers = event.get("headers", {})
            api_key = next(
                (v for k, v in headers.items() if k.lower() == "x-api-key"), None
            )
            if not api_key:
                return _response(401, {"error": "Missing X-API-Key header"})
            if api_key != expected_token:
                return _response(403, {"error": "Invalid API token"})

        # ── Required fields ────────────────────────────────────────
        user_id          = body.get("user_id")
        session_id       = body.get("session_id")
        filled_doc_pdf_id= body.get("filled_doc_pdf_id")
        pdf_doc_id       = body.get("pdf_doc_id")
        pdf_location     = body.get("pdf_location")
        investor_type    = body.get("investor_type", "Individual")

        if not all([user_id, session_id, filled_doc_pdf_id, pdf_doc_id, pdf_location]):
            return _response(400, {
                "error": "Missing required fields: user_id, session_id, filled_doc_pdf_id, pdf_doc_id, pdf_location"
            })

        # ── Env check ──────────────────────────────────────────────
        bucket_base = os.environ.get("AWS_OUTPUT_BUCKET") or os.environ.get("STATIC_BUCKET")
        if not bucket_base:
            return _response(500, {"error": "AWS_OUTPUT_BUCKET not set"})

        schema_s3_uri = f"s3://{bucket_base}/config/form_keys.json"
        output_s3_uri = (
            f"s3://{bucket_base}/outputs/"
            f"{user_id}/sessions/{session_id}/{filled_doc_pdf_id}/"
            "final_upload_form_keys_filled.json"
        )

        # ── Run pipeline ───────────────────────────────────────────
        client = _get_client()
        result = client.run(
            document_path=pdf_location,
            schema_path=schema_s3_uri,
            job_id=session_id,
            output_path=output_s3_uri,
            investor_type=investor_type,
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            filled_doc_pdf_id=filled_doc_pdf_id,
        )

        resp = {
            "status": "success",
            "response": "Your document has been extracted and the PDF filled",
            "user_id": user_id,
            "session_id": session_id,
            "filled_doc_pdf_id": filled_doc_pdf_id,
            "pdf_doc_id": pdf_doc_id,
            "output_location": output_s3_uri,
        }
        log.log_output_response(resp)
        return _response(200, resp)

    except (KeyError, ValueError) as e:
        log.log_error(str(e), exception=e)
        return _response(400, {"status": "failed", "error": str(e)})
    except Exception as e:
        log.log_error(f"Unhandled exception: {e}", exception=e)
        return _response(500, {"status": "failed", "error": str(e)})