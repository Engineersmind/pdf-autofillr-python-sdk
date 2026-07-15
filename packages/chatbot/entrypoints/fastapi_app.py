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

import hmac
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from chatbot import FormConfig, chatbotClient  # noqa: E402
from chatbot.storage.factory import StorageFactory  # noqa: E402
from chatbot.storage.local_storage import PathAccessError  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(
    title="chatbot (bare routes)",
    description="chatbot sub-app — /chat instead of /chatbot/chat.",
    version="0.4.0",
)

# CORS: restrict to an explicit allow-list. "*" origins combined with any
# form of credentialed access is unsafe in production — set
# CHATBOT_CORS_ALLOWED_ORIGINS to a comma-separated list of real origins.
_cors_origins_env = os.getenv("CHATBOT_CORS_ALLOWED_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] or []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

_client: chatbotClient | None = None

# Every request must present a valid API key. There is no safe default —
# the server refuses to start serving requests until CHATBOT_API_KEY is set,
# closing the "no auth configured => no auth required" hole.
_ALLOW_INSECURE_NO_AUTH = (
    os.getenv("CHATBOT_ALLOW_INSECURE_NO_AUTH", "false").lower() == "true"
)


def _check_api_key(provided: str | None) -> None:
    expected = os.environ.get("CHATBOT_API_KEY")
    if not expected:
        if _ALLOW_INSECURE_NO_AUTH:
            return  # explicitly opted into no-auth mode (local dev only)
        raise HTTPException(
            status_code=500,
            detail=(
                "Server misconfigured: CHATBOT_API_KEY is not set. Set "
                "CHATBOT_API_KEY to a strong secret, or set "
                "CHATBOT_ALLOW_INSECURE_NO_AUTH=true to explicitly run "
                "without authentication (not recommended)."
            ),
        )
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


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
    raise ValueError(
        f"Unknown chatbot_PDF_FILLER: {mode!r}. Use: none | mapper | custom"
    )


def get_client() -> chatbotClient:
    global _client
    if _client is None:
        config_path = os.getenv("chatbot_CONFIG_PATH", "./configs")
        storage = StorageFactory.create()
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
    pdf_path: str | None = None


class ChatResponse(BaseModel):
    user_id: str
    session_id: str
    response: str
    session_complete: bool
    filled_data: dict | None = None


class SessionDataResponse(BaseModel):
    user_id: str
    session_id: str
    data: dict | None


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    try:
        client = get_client()
        pdf_path = req.pdf_path or os.getenv("chatbot_PDF_PATH", "")
        if pdf_path:
            client.create_session(req.user_id, req.session_id, pdf_path=pdf_path)
        response, complete, data = client.send_message(
            req.user_id, req.session_id, req.message
        )
        return ChatResponse(
            user_id=req.user_id,
            session_id=req.session_id,
            response=response,
            session_complete=complete,
            filled_data=data if complete else None,
        )
    except PathAccessError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error in /chat")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/session/{user_id}/{session_id}", response_model=SessionDataResponse)
def get_session(
    user_id: str, session_id: str, x_api_key: str | None = Header(default=None)
):
    _check_api_key(x_api_key)
    try:
        data = get_client().get_session_data(user_id, session_id)
    except PathAccessError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if data is None:
        raise HTTPException(
            status_code=404, detail="Session not found or not complete."
        )
    return SessionDataResponse(user_id=user_id, session_id=session_id, data=data)


@app.get("/session/{user_id}/{session_id}/fill-report")
def get_fill_report(
    user_id: str,
    session_id: str,
    format: str = "json",
    x_api_key: str | None = Header(default=None),
):
    _check_api_key(x_api_key)
    client = get_client()
    try:
        if format == "text":
            text = client.get_fill_report_text(user_id, session_id)
            if text is None:
                raise HTTPException(status_code=404, detail="Fill report not found.")
            return {"report": text}
        report = client.get_fill_report(user_id, session_id)
    except PathAccessError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if report is None:
        raise HTTPException(status_code=404, detail="Fill report not found.")
    return report


@app.delete("/session/{user_id}/{session_id}")
def delete_session(
    user_id: str, session_id: str, x_api_key: str | None = Header(default=None)
):
    _check_api_key(x_api_key)
    try:
        get_client().delete_session(user_id, session_id)
    except PathAccessError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"deleted": True}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.4.0",
        "storage": os.getenv("chatbot_STORAGE", "local"),
        "pdf_filler": os.getenv("chatbot_PDF_FILLER", "none"),
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": str(exc)})
