# chatbot/entrypoints/gcp_function.py
"""
Google Cloud Functions HTTP trigger entrypoint for the chatbot module.

Deploy with:
    gcloud functions deploy chatbot \
        --runtime python311 \
        --trigger-http \
        --entry-point main \
        --source .

HTTP trigger request body (JSON):
    {
        "user_id":    "investor_123",
        "session_id": "session_abc",
        "message":    "Hello",
        "pdf_path":   "gs://bucket/blank_form.pdf"   # optional
    }

Recommended env vars (set via --set-env-vars or Secret Manager):
    CHATBOT_LLM_MODEL=openai/gpt-4o-mini
    CHATBOT_LLM_API_KEY=sk-...  (or OPENAI_API_KEY, ANTHROPIC_API_KEY etc.)
    chatbot_STORAGE=gcp
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json  (or use Workload Identity)
    GCP_OUTPUT_BUCKET=chatbot-output
    GCP_CONFIG_BUCKET=chatbot-configs
    GCP_PROJECT_ID=your-project
    chatbot_PDF_FILLER=mapper     (optional)
    MAPPER_API_URL=https://...    (optional — for HTTP mapper mode)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("chatbot_LOG_LEVEL", "INFO"))

from chatbot import chatbotClient, FormConfig
from chatbot.storage.factory import StorageFactory

_client: Optional[chatbotClient] = None


def _build_client() -> chatbotClient:
    storage = StorageFactory.create()
    config_path = os.getenv("chatbot_CONFIG_PATH", "./configs")
    form_config = FormConfig.from_directory(config_path)

    pdf_filler = None
    if os.getenv("chatbot_PDF_FILLER", "none").lower() in ("mapper", "managed"):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        pdf_filler = MapperPDFFiller(
            mapper_api_url=os.getenv("MAPPER_API_URL", ""),
            mapper_api_key=os.getenv("MAPPER_API_KEY", ""),
        )

    return chatbotClient(
        storage=storage,
        form_config=form_config,
        pdf_filler=pdf_filler,
    )


def _get_client() -> chatbotClient:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _make_response(status: int, body: dict):
    """
    Build a response compatible with both real GCF runtime and local testing.

    In real GCF: the runtime provides a Flask app context, so we return a
    proper Flask Response via flask.make_response.
    In tests / local: no app context exists, so we return a plain dict.
    """
    payload = json.dumps(body, default=str)
    try:
        from flask import make_response as flask_make_response
        resp = flask_make_response(payload, status)
        resp.headers["Content-Type"] = "application/json"
        return resp
    except RuntimeError:
        # Outside Flask application context (unit tests, local execution)
        return {"statusCode": status, "body": payload}


def _parse_request(request: Any) -> dict:
    """Parse payload from Flask Request or plain dict (tests)."""
    if isinstance(request, dict):
        return request
    try:
        return request.get_json(force=True) or {}
    except Exception:
        return {}


def main(request: Any) -> Any:
    """
    Google Cloud Functions HTTP trigger handler.

    GCF calls this with a Flask Request object.
    Also works with a plain dict for local testing.
    """
    try:
        payload = _parse_request(request)

        user_id    = payload.get("user_id")
        session_id = payload.get("session_id")
        message    = payload.get("message", "")
        pdf_path   = payload.get("pdf_path") or os.getenv("chatbot_PDF_PATH", "")

        if not user_id or not session_id:
            return _make_response(400, {"error": "user_id and session_id are required"})

        client = _get_client()
        if pdf_path:
            client.create_session(user_id, session_id, pdf_path=pdf_path)

        response, complete, data = client.send_message(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )

        return _make_response(200, {
            "user_id":          user_id,
            "session_id":       session_id,
            "response":         response,
            "session_complete": complete,
            "filled_data":      data if complete else None,
        })

    except (KeyError, ValueError) as e:
        logger.warning("Bad request: %s", e)
        return _make_response(400, {"error": str(e)})
    except Exception:
        # Log full exception server-side only — never expose stack trace to caller
        logger.exception("Unhandled GCP Function error")
        return _make_response(500, {"error": "Internal server error"})