# extractor/entrypoints/gcp_function.py
"""
GCP Cloud Functions entrypoint.

Deploy::
    gcloud functions deploy extractor \
        --runtime python311 \
        --trigger-http \
        --entry-point handler \
        --source .

Required env vars (set in GCP console or --set-env-vars):
    DOC_UPLOAD_LLM_MODEL, DOC_UPLOAD_LLM_API_KEY
    DOC_UPLOAD_STORAGE=gcp
    GCP_OUTPUT_BUCKET, GCP_CONFIG_BUCKET
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from pdf_autofillr_doc_upload import DocUploadClient
        from pdf_autofillr_doc_upload.storage.factory import StorageFactory
        from pdf_autofillr_doc_upload.extraction.extractor import Extractor
        from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

        storage = StorageFactory.create()
        extractor = Extractor(llm_client=LLMClient())
        pdf_filler = None  # DocUploadClient._build_default_filler handles this from env
        _client = DocUploadClient(storage=storage, extractor=extractor, pdf_filler=pdf_filler)
    return _client


def handler(request):
    """GCP Cloud Functions HTTP handler."""
    import uuid
    try:
        body = request.get_json(force=True, silent=True) or {}

        document_path = body.get("document_path") or body.get("pdf_location")
        schema_path   = body.get("schema_path", "configs/form_keys.json")
        job_id        = body.get("job_id") or body.get("session_id") or str(uuid.uuid4())
        investor_type = body.get("investor_type", "Individual")

        if not document_path:
            return (json.dumps({"error": "document_path is required"}), 400,
                    {"Content-Type": "application/json"})

        client = _get_client()
        result = client.run(
            document_path=document_path,
            schema_path=schema_path,
            job_id=job_id,
            user_id=body.get("user_id"),
            pdf_doc_id=body.get("pdf_doc_id"),
            session_id=body.get("session_id"),
            investor_type=investor_type,
        )

        return (json.dumps({"status": "success", "job_id": job_id,
                            "fields": len(result["output_flat"])}, default=str),
                200, {"Content-Type": "application/json"})

    except Exception as e:
        logger.exception("GCP handler error")
        return (json.dumps({"status": "failed", "error": str(e)}),
                500, {"Content-Type": "application/json"})