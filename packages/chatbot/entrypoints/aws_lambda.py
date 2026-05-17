# chatbot/entrypoints/aws_lambda.py
"""
AWS Lambda entrypoint for the chatbot module.

Deploy with:
    handler = entrypoints.aws_lambda.handler

Lambda event formats supported:

    Direct invocation::
        {
            "user_id": "investor_123",
            "session_id": "session_abc",
            "message": "Hello",
            "pdf_path": "/tmp/blank_form.pdf"    # optional
        }

    API Gateway proxy (auto-detected)::
        {
            "httpMethod": "POST",
            "body": "{\"user_id\": ..., \"message\": ...}"
        }

Recommended env vars for Lambda:
    CHATBOT_LLM_MODEL=openai/gpt-4o-mini
    CHATBOT_LLM_API_KEY=sk-...  (or OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
    chatbot_STORAGE=s3
    AWS_OUTPUT_BUCKET=...
    AWS_CONFIG_BUCKET=...
    chatbot_CONFIG_PATH   (omit — S3Storage reads configs from AWS_CONFIG_BUCKET)
    chatbot_PDF_FILLER=mapper  (optional)
    MAPPER_API_URL=...         (optional — for HTTP mapper mode)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from chatbot import chatbotClient, FormConfig
from chatbot.storage.factory import StorageFactory

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("chatbot_LOG_LEVEL", "INFO"))

_client: Optional[chatbotClient] = None


def _build_client() -> chatbotClient:
    storage = StorageFactory.create()
    config_path = os.getenv("chatbot_CONFIG_PATH", "/tmp/configs")
    form_config = FormConfig.from_directory(config_path)

    pdf_filler = None
    if os.getenv("chatbot_PDF_FILLER", "none").lower() in ("mapper", "managed"):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        pdf_filler = MapperPDFFiller(
            mapper_api_url=os.getenv("MAPPER_API_URL", ""),
            mapper_api_key=os.getenv("MAPPER_API_KEY", ""),
        )

    return chatbotClient(
        # api_key read from CHATBOT_LLM_API_KEY env var automatically
        storage=storage,
        form_config=form_config,
        pdf_filler=pdf_filler,
    )


def _get_client() -> chatbotClient:
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


def _parse_event(event: dict) -> dict:
    if "httpMethod" in event and "body" in event:
        body = event.get("body") or "{}"
        return json.loads(body) if isinstance(body, str) else body
    return event


def handler(event: Dict[str, Any], context: Any) -> dict:
    try:
        payload = _parse_event(event)
        user_id = payload.get("user_id")
        session_id = payload.get("session_id")
        message = payload.get("message", "")
        pdf_path = payload.get("pdf_path") or os.getenv("chatbot_PDF_PATH", "")

        if not user_id or not session_id:
            return _response(400, {"error": "user_id and session_id are required"})

        client = _get_client()
        if pdf_path:
            client.create_session(user_id, session_id, pdf_path=pdf_path)

        response, complete, data = client.send_message(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )

        return _response(200, {
            "user_id": user_id,
            "session_id": session_id,
            "response": response,
            "session_complete": complete,
            "filled_data": data if complete else None,
        })

    except (KeyError, ValueError) as e:
        return _response(400, {"error": str(e)})
    except Exception as e:
        logger.exception("Unhandled Lambda error")
        return _response(500, {"error": "Internal server error", "detail": str(e)})
