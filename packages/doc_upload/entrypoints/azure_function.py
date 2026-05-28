# extractor/entrypoints/azure_function.py
"""
Azure Functions entrypoint.

function.json::
    {
      "bindings": [{
        "authLevel": "function",
        "type": "httpTrigger",
        "direction": "in",
        "name": "req",
        "methods": ["post"]
      }, {
        "type": "http",
        "direction": "out",
        "name": "$return"
      }]
    }

Required app settings:
    DOC_UPLOAD_LLM_MODEL, DOC_UPLOAD_LLM_API_KEY
    DOC_UPLOAD_STORAGE=azure
    AZURE_OUTPUT_CONTAINER, AZURE_CONFIG_CONTAINER
    AZURE_STORAGE_CONNECTION_STRING
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from pdf_autofillr_doc_upload import DocUploadClient
        from pdf_autofillr_doc_upload.extraction.extractor import Extractor
        from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient
        from pdf_autofillr_doc_upload.storage.factory import StorageFactory

        storage = StorageFactory.create()
        extractor = Extractor(llm_client=LLMClient())
        pdf_filler = None  # DocUploadClient._build_default_filler handles this from env
        _client = DocUploadClient(
            storage=storage, extractor=extractor, pdf_filler=pdf_filler
        )
    return _client


def main(req) -> str:
    """Azure Functions HTTP trigger handler."""
    try:
        import azure.functions as func

        body = req.get_json()
    except Exception:
        body = {}

    try:
        document_path = body.get("document_path") or body.get("pdf_location")
        schema_path = body.get("schema_path", "configs/form_keys.json")
        job_id = body.get("job_id") or body.get("session_id") or str(uuid.uuid4())
        investor_type = body.get("investor_type", "Individual")

        if not document_path:
            import azure.functions as func

            return func.HttpResponse(
                json.dumps({"error": "document_path is required"}),
                status_code=400,
                mimetype="application/json",
            )

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

        import azure.functions as func

        return func.HttpResponse(
            json.dumps(
                {
                    "status": "success",
                    "job_id": job_id,
                    "fields": len(result["output_flat"]),
                },
                default=str,
            ),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        logger.exception("Azure function error")
        try:
            import azure.functions as func

            return func.HttpResponse(
                json.dumps({"status": "failed", "error": str(e)}),
                status_code=500,
                mimetype="application/json",
            )
        except Exception:
            return json.dumps({"status": "failed", "error": str(e)})
