# chatbot/entrypoints/fastapi_app.py
"""
Bare FastAPI app — no /chatbot prefix on routes.

Use this when mounting into a larger application or running behind
a reverse proxy that adds the prefix itself.

Routes:
    POST   /chat
    GET    /session/{user_id}/{session_id}
    GET    /session/{user_id}/{session_id}/fill-report
    DELETE /session/{user_id}/{session_id}
    GET    /health

For standalone deployment use api_server.py instead (has /chatbot/* prefix).

Mount example::

    from entrypoints.fastapi_app import app as chatbot_app
    main_app.mount("/onboarding", chatbot_app)
"""
from __future__ import annotations

import os
import logging
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chatbot import chatbotClient, FormConfig
from chatbot.storage.factory import StorageFactory

logger = logging.getLogger(__name__)

app = FastAPI(
    title="chatbot (bare routes)",
    description="chatbot sub-app — /chat instead of /chatbot/chat.",
    version="0.3.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_client: Optional[chatbotClient] = None


def _build_pdf_filler():
    mode = os.getenv("chatbot_PDF_FILLER", "none").lower()
    if mode in ("none", ""):
        return None
    if mode in ("mapper", "managed"):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        return MapperPDFFiller(
            mapper_api_url=os.getenv("MAPPER_API_URL", ""),
            mapper_api_key=os.getenv("MAPPER_API_KEY", ""),
            config_dir=os.getenv("chatbot_CONFIG_PATH", "./configs"),
        )
    raise ValueError(f"Unknown chatbot_PDF_FILLER: {mode!r}. Use: none | mapper | custom")


def get_client() -> chatbotClient:
    global _client
    if _client is None:
        storage = StorageFactory.create()
        config_path = os.getenv("chatbot_CONFIG_PATH", "./configs")
        _client = chatbotClient(
            # api_key read from CHATBOT_LLM_API_KEY env var automatically
            storage=storage,
            form_config=FormConfig.from_directory(config_path),
            pdf_filler=_build_pdf_filler(),
        )
    return _client


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str = ""
    pdf_path: Optional[str] = None


class ChatResponse(BaseModel):
    user_id: str
    session_id: str
    response: str
    session_complete: bool
    filled_data: Optional[dict] = None


class SessionDataResponse(BaseModel):
    user_id: str
    session_id: str
    data: Optional[dict]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        client = get_client()
        pdf_path = req.pdf_path or os.getenv("chatbot_PDF_PATH", "")
        if pdf_path:
            client.create_session(req.user_id, req.session_id, pdf_path=pdf_path)
        response, complete, data = client.send_message(req.user_id, req.session_id, req.message)
        return ChatResponse(
            user_id=req.user_id,
            session_id=req.session_id,
            response=response,
            session_complete=complete,
            filled_data=data if complete else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error in /chat")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{user_id}/{session_id}", response_model=SessionDataResponse)
def get_session(user_id: str, session_id: str):
    data = get_client().get_session_data(user_id, session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found or not complete.")
    return SessionDataResponse(user_id=user_id, session_id=session_id, data=data)


@app.get("/session/{user_id}/{session_id}/fill-report")
def get_fill_report(user_id: str, session_id: str, format: str = "json"):
    client = get_client()
    if format == "text":
        text = client.get_fill_report_text(user_id, session_id)
        if text is None:
            raise HTTPException(status_code=404, detail="Fill report not found.")
        return {"report": text}
    report = client.get_fill_report(user_id, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Fill report not found.")
    return report


@app.delete("/session/{user_id}/{session_id}")
def delete_session(user_id: str, session_id: str):
    get_client().delete_session(user_id, session_id)
    return {"deleted": True}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "storage": os.getenv("chatbot_STORAGE", "local"),
        "pdf_filler": os.getenv("chatbot_PDF_FILLER", "none"),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": str(exc)})
