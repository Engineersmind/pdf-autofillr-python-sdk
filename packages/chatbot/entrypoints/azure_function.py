# chatbot/entrypoints/azure_function.py
"""
Azure Functions HTTP trigger entrypoint for the chatbot module.

Deploy with:
    Azure Function App, Python runtime, HTTP trigger.
    Set the function entry point to: entrypoints.azure_function.main

HTTP trigger event format (JSON body):
    {
        "user_id":    "investor_123",
        "session_id": "session_abc",
        "message":    "Hello",
        "pdf_path":   "azure://container/blank_form.pdf"   # optional
    }

Recommended env vars (set in Azure Function App Configuration):
    CHATBOT_LLM_MODEL=openai/gpt-4o-mini
    CHATBOT_LLM_API_KEY=sk-...  (or OPENAI_API_KEY, ANTHROPIC_API_KEY etc.)
    chatbot_STORAGE=azure
    AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
    AZURE_OUTPUT_CONTAINER=chatbot-output
    AZURE_CONFIG_CONTAINER=chatbot-configs
    chatbot_PDF_FILLER=mapper        (optional)
    MAPPER_API_URL=https://...       (optional — for HTTP mapper mode)
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

try:
    import azure.functions as func
    _AZURE_AVAILABLE = True
except ImportError:
    _AZURE_AVAILABLE = False
    func = None  # type: ignore

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


def _json_response(status: int, body: dict):
    """Return an Azure Functions HttpResponse with JSON body."""
    if not _AZURE_AVAILABLE:
        # Fallback for testing without azure-functions installed
        return {"statusCode": status, "body": json.dumps(body, default=str)}
    return func.HttpResponse(
        body=json.dumps(body, default=str),
        status_code=status,
        mimetype="application/json",
    )


def _parse_request(req) -> dict:
    """Parse payload from Azure HttpRequest or plain dict (tests)."""
    if isinstance(req, dict):
        return req
    try:
        return req.get_json()
    except Exception:
        return {}


def main(req: Any) -> Any:
    """
    Azure Functions HTTP trigger handler.

    Azure wires this automatically when function entry point is set to
    entrypoints.azure_function.main in function.json.
    """
    try:
        payload = _parse_request(req)

        user_id    = payload.get("user_id")
        session_id = payload.get("session_id")
        message    = payload.get("message", "")
        pdf_path   = payload.get("pdf_path") or os.getenv("chatbot_PDF_PATH", "")

        if not user_id or not session_id:
            return _json_response(400, {"error": "user_id and session_id are required"})

        client = _get_client()
        if pdf_path:
            client.create_session(user_id, session_id, pdf_path=pdf_path)

        response, complete, data = client.send_message(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )

        return _json_response(200, {
            "user_id":          user_id,
            "session_id":       session_id,
            "response":         response,
            "session_complete": complete,
            "filled_data":      data if complete else None,
        })

    except (KeyError, ValueError) as e:
        logger.warning("Bad request: %s", e)
        return _json_response(400, {"error": str(e)})
    except Exception as e:
        logger.exception("Unhandled Azure Function error")
        return _json_response(500, {"error": "Internal server error", "detail": str(e)})
