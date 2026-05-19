"""
Google Cloud Function HTTP trigger for pdf-autofillr-rag.

Set the entry point to: ragpdf_handler

Required env vars (set in Cloud Run / Cloud Function environment):
    RAGPDF_STORAGE=gcs
    RAGPDF_VECTOR_STORE=gcs
    RAGPDF_GCS_BUCKET=your-bucket
    RAGPDF_CORRECTOR_BACKEND=openai
    OPENAI_API_KEY=sk-...
    RAGPDF_API_KEY=your-secret

Local test (Functions Framework):
    pip install functions-framework
    functions-framework --target ragpdf_handler --port 8080
    # POST http://localhost:8080
    # Body: {"api_name": "get_system_info"}
"""
import json
import logging
import os
from ragpdf import RAGPDFClient

logger = logging.getLogger(__name__)
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = RAGPDFClient.from_env()
    return _client


def ragpdf_handler(request):
    """GCP Cloud Function HTTP entry point."""
    try:
        api_key  = request.headers.get("x-api-key", "")
        expected = os.getenv("RAGPDF_API_KEY", "")
        if expected and api_key != expected:
            return (json.dumps({"status": "failure", "message": "Invalid API key"}), 401, {"Content-Type": "application/json"})

        body     = request.get_json(silent=True) or {}
        api_name = body.get("api_name")
        c        = _get_client()

        def ok(data):
            return (json.dumps({"status": "success", "message": "OK", "data": data}), 200, {"Content-Type": "application/json"})

        def err(code, msg):
            return (json.dumps({"status": "failure", "message": msg}), code, {"Content-Type": "application/json"})

        if api_name == "get_rag_predictions":
            return ok(c.get_predictions(user_id=body["user_id"], session_id=body["session_id"],
                pdf_id=body["pdf_id"], fields=body["fields"], pdf_hash=body["pdf_hash"], pdf_category=body["pdf_category"]))
        elif api_name == "saving_filled_pdf":
            return ok(c.save_filled_pdf(user_id=body["user_id"], session_id=body["session_id"],
                pdf_id=body["filled_doc_pdf_id"], llm_predictions=body["llm_predictions"], final_predictions=body["final_predictions"]))
        elif api_name == "user_feedback":
            return ok(c.submit_feedback(user_id=body["user_id"], session_id=body["session_id"],
                pdf_id=body["pdf_id"], errors=body.get("errors", []), timestamp=body.get("timestamp")))
        elif api_name == "get_metrics":
            mt = body.pop("metric_type"); body.pop("api_name", None)
            return ok(c.get_metrics(mt, **body))
        elif api_name == "get_system_info":
            return ok(c.get_system_info())
        elif api_name == "get_error_analytics":
            body.pop("api_name", None)
            return ok(c.get_error_analytics(**body))

        return err(400, f"Unknown api_name: {api_name}")
    except Exception as e:
        logger.exception("Unhandled exception")
        return (json.dumps({"status": "failure", "message": str(e)}), 500, {"Content-Type": "application/json"})
