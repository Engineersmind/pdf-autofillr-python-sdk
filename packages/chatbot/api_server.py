# chatbot/api_server.py
"""
FastAPI server for the chatbot module.

Run with:
    python api_server.py

Or via the installed command:
    chatbot-server

API docs: http://localhost:8001/docs

PDF filler mode (set in .env):
    chatbot_PDF_FILLER=none      ← data-only (default)
    chatbot_PDF_FILLER=mapper    ← connect to pdf-autofillr-mapper
"""
from __future__ import annotations

import os
import logging
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    raise ImportError(
        "FastAPI is required to run the API server.\n"
        "Install it with: pip install 'pdf-autofillr-chatbot[server]'"
    )

from chatbot import chatbotClient, FormConfig
from chatbot.storage.factory import StorageFactory

logger = logging.getLogger(__name__)

app = FastAPI(
    title="chatbot Onboarding API",
    description="Conversational investor onboarding — collects data and fills PDF forms.",
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
    if mode == "custom":
        raise ValueError(
            "chatbot_PDF_FILLER=custom requires wiring programmatically.\n"
            "Instantiate chatbotClient directly and pass your PDFFillerInterface."
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


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the investor")
    session_id: str = Field(..., description="Unique identifier for this conversation session")
    message: str = Field(default="", description="User's message text")
    pdf_path: Optional[str] = Field(default=None, description="Path to blank PDF (first turn only)")


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "chatbot Onboarding API",
        "version": "0.3.0",
        "status": "running",
        "docs": "/docs",
    }


@app.post("/chatbot/chat", response_model=ChatResponse)
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
        logger.exception("Unhandled error in /chatbot/chat")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chatbot/session/{user_id}/{session_id}", response_model=SessionDataResponse)
def get_session(user_id: str, session_id: str):
    data = get_client().get_session_data(user_id, session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Session not found or not yet complete.")
    return SessionDataResponse(user_id=user_id, session_id=session_id, data=data)


@app.get("/chatbot/session/{user_id}/{session_id}/fill-report")
def get_fill_report(user_id: str, session_id: str, format: str = "json"):
    client = get_client()
    if format == "text":
        text = client.get_fill_report_text(user_id, session_id)
        if text is None:
            raise HTTPException(status_code=404, detail="Fill report not found.")
        return {"user_id": user_id, "session_id": session_id, "report": text}
    report = client.get_fill_report(user_id, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Fill report not found.")
    return {"user_id": user_id, "session_id": session_id, "report": report}


@app.delete("/chatbot/session/{user_id}/{session_id}")
def delete_session(user_id: str, session_id: str):
    get_client().delete_session(user_id, session_id)
    return {"deleted": True, "user_id": user_id, "session_id": session_id}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.3.0",
        "storage": os.getenv("chatbot_STORAGE", "local"),
        "pdf_filler": os.getenv("chatbot_PDF_FILLER", "none"),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": str(exc)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=os.getenv("chatbot_LOG_LEVEL", "info").lower())
