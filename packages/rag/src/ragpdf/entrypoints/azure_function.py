"""
Azure Function HTTP trigger for pdf-autofillr-rag.

Set the function entry point to: entrypoints.azure_function.main

Required env vars (set in Azure Function App -> Configuration):
    RAGPDF_STORAGE=s3 (or azure)
    RAGPDF_VECTOR_STORE=s3 (or azure)
    RAGPDF_S3_BUCKET=your-bucket       (if using S3)
    RAGPDF_AZURE_CONN_STR=...          (if using Azure storage)
    RAGPDF_CORRECTOR_BACKEND=openai    (or noop)
    OPENAI_API_KEY=sk-...
    RAGPDF_API_KEY=your-secret

Local test:
    func start   (Azure Functions Core Tools)
    # POST http://localhost:7071/api/ragpdf
    # Body: {"api_name": "get_system_info"}
"""
import json
import logging
import azure.functions as func
from ragpdf import RAGPDFClient

logger = logging.getLogger(__name__)
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = RAGPDFClient.from_env()
    return _client


def _response(status_code: int, message: str, data: dict = None) -> func.HttpResponse:
    import os
    body = {"status": "success" if status_code == 200 else "failure", "message": message}
    if data:
        body["data"] = data
    return func.HttpResponse(
        body=json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    import os
    try:
        api_key = req.headers.get("x-api-key", "")
        expected = os.getenv("RAGPDF_API_KEY", "")
        if expected and api_key != expected:
            return _response(401, "Invalid API key")

        body = req.get_json()
        api_name = body.get("api_name")
        c = _get_client()

        if api_name == "get_rag_predictions":
            return _response(200, "OK", c.get_predictions(
                user_id=body["user_id"], session_id=body["session_id"], pdf_id=body["pdf_id"],
                fields=body["fields"], pdf_hash=body["pdf_hash"], pdf_category=body["pdf_category"],
            ))
        elif api_name == "saving_filled_pdf":
            return _response(200, "OK", c.save_filled_pdf(
                user_id=body["user_id"], session_id=body["session_id"], pdf_id=body["filled_doc_pdf_id"],
                llm_predictions=body["llm_predictions"], final_predictions=body["final_predictions"],
            ))
        elif api_name == "user_feedback":
            return _response(200, "OK", c.submit_feedback(
                user_id=body["user_id"], session_id=body["session_id"], pdf_id=body["pdf_id"],
                errors=body.get("errors", []), timestamp=body.get("timestamp"),
            ))
        elif api_name == "get_metrics":
            mt = body.pop("metric_type"); body.pop("api_name", None)
            return _response(200, "OK", c.get_metrics(mt, **body))
        elif api_name == "get_system_info":
            return _response(200, "OK", c.get_system_info())
        elif api_name == "get_error_analytics":
            body.pop("api_name", None)
            return _response(200, "OK", c.get_error_analytics(**body))

        return _response(400, f"Unknown api_name: {api_name}")
    except Exception as e:
        logger.exception("Unhandled exception")
        return _response(500, str(e))
