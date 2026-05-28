# entrypoints/aws_lambda.py
"""
AWS Lambda handler.
Set handler to: entrypoints.aws_lambda.lambda_handler

Required env vars (in Lambda console):
    RAGPDF_STORAGE=s3
    RAGPDF_VECTOR_STORE=s3
    RAGPDF_S3_BUCKET=your-bucket
    RAGPDF_CORRECTOR_BACKEND=openai   (or noop)
    OPENAI_API_KEY=sk-...
    RAGPDF_API_KEY=your-secret

Local test:
    RAGPDF_STORAGE=local RAGPDF_CORRECTOR_BACKEND=noop python -c "
    from entrypoints.aws_lambda import lambda_handler
    import json
    event = {'headers': {}, 'body': json.dumps({'api_name': 'get_system_info'})}
    print(lambda_handler(event, None))
    "
"""

import json
import logging
import os
from typing import Any

from ragpdf import RAGPDFClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EXPECTED_API_KEY = os.getenv("RAGPDF_API_KEY", "")
_client: RAGPDFClient = None


def _get_client() -> RAGPDFClient:
    global _client
    if _client is None:
        _client = RAGPDFClient.from_env()
    return _client


def _response(
    status_code: int, message: str, data: dict[Any, Any] | None = None
) -> dict:
    body: dict[str, Any] = {
        "status": "success" if status_code == 200 else "failure",
        "message": message,
    }
    if data:
        body["data"] = data
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    try:
        headers = event.get("headers") or {}
        api_key = headers.get("x-api-key") or headers.get("X-Api-Key", "")
        if EXPECTED_API_KEY and api_key != EXPECTED_API_KEY:
            return _response(401, "Invalid API key")

        raw = event.get("body", "{}")
        body = json.loads(raw) if isinstance(raw, str) else (raw or {})
        api_name = body.get("api_name")
        c = _get_client()

        if api_name == "get_rag_predictions":
            return _response(
                200,
                "OK",
                c.get_predictions(
                    user_id=body["user_id"],
                    session_id=body["session_id"],
                    pdf_id=body["pdf_id"],
                    fields=body["fields"],
                    pdf_hash=body["pdf_hash"],
                    pdf_category=body["pdf_category"],
                ),
            )

        elif api_name == "saving_filled_pdf":
            return _response(
                200,
                "OK",
                c.save_filled_pdf(
                    user_id=body["user_id"],
                    session_id=body["session_id"],
                    pdf_id=body["filled_doc_pdf_id"],
                    llm_predictions=body["llm_predictions"],
                    final_predictions=body["final_predictions"],
                ),
            )

        elif api_name == "user_feedback":
            return _response(
                200,
                "OK",
                c.submit_feedback(
                    user_id=body["user_id"],
                    session_id=body["session_id"],
                    pdf_id=body["pdf_id"],
                    errors=body.get("errors", []),
                    timestamp=body.get("timestamp"),
                ),
            )

        elif api_name == "get_metrics":
            mt = body.pop("metric_type")
            body.pop("api_name", None)
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
