# chatbot/src/chatbot/entrypoints/aws_lambda.py
"""
AWS Lambda handler for pdf-autofillr-chatbot.

Lambda handler path:  chatbot.entrypoints.aws_lambda.handler

Expected event::

    {
        "user_id":    "investor_123",
        "session_id": "session_abc",
        "message":    "my name is John Smith",
        "pdf_path":   "s3://your-bucket/blank_form.pdf"   # optional
    }

Recommended env vars:
    CHATBOT_LLM_MODEL=openai/gpt-4o-mini
    CHATBOT_LLM_API_KEY=sk-...  (or OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
    chatbot_STORAGE=s3
    AWS_OUTPUT_BUCKET=...
    AWS_CONFIG_BUCKET=...
    chatbot_PDF_FILLER=mapper   (optional)
    MAPPER_API_URL=...          (optional — for HTTP mapper mode)
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("chatbot_LOG_LEVEL", "INFO"))

_client = None


def _build_client():
    from chatbot import FormConfig, chatbotClient
    from chatbot.storage.factory import StorageFactory

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
        # api_key read from CHATBOT_LLM_API_KEY env var automatically
        storage=storage,
        form_config=form_config,
        pdf_filler=pdf_filler,
    )


def handler(event, context):
    global _client
    try:
        if _client is None:
            _client = _build_client()

        user_id = event["user_id"]
        session_id = event["session_id"]
        message = event.get("message", "")
        pdf_path = event.get("pdf_path") or os.getenv("chatbot_PDF_PATH", "")

        if pdf_path:
            _client.create_session(user_id, session_id, pdf_path=pdf_path)

        response, complete, data = _client.send_message(user_id, session_id, message)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "response": response,
                    "session_complete": complete,
                    "filled_data": data if complete else None,
                },
                default=str,
            ),
        }

    except (KeyError, ValueError) as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        logger.exception("Lambda handler error")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
