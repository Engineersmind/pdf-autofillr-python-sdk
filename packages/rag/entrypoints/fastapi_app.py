# entrypoints/fastapi_app.py
"""
FastAPI server — all 6 APIs over HTTP.

Run:
    uvicorn entrypoints.fastapi_app:app --reload --port 8000
    python -m entrypoints.fastapi_app

Swagger UI: http://localhost:8000/docs
"""

import hmac
import os
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ragpdf import RAGPDFClient

app = FastAPI(title="pdf-autofillr-rag", version="0.2.5")

# No safe default: a hardcoded fallback key ("dev-key") would mean any
# deployment that forgets to set RAGPDF_API_KEY is protected by a
# publicly-known secret. Set RAGPDF_ALLOW_INSECURE_NO_AUTH=true to
# explicitly run without auth (local dev only).
client: RAGPDFClient = None


@app.on_event("startup")
def startup():
    global client
    client = RAGPDFClient.from_env()


def _auth(x_api_key: str = Header(None)):
    # Read per-request, not at module import time — see local_server.py
    # for the full rationale (late env-var injection e.g. from a secrets
    # manager would otherwise leave EXPECTED_API_KEY permanently None).
    expected = os.environ.get("RAGPDF_API_KEY")
    allow_insecure = os.environ.get("RAGPDF_ALLOW_INSECURE_NO_AUTH", "").lower() == "true"
    if not expected:
        if allow_insecure:
            return
        raise HTTPException(
            status_code=500,
            detail=(
                "Server misconfigured: RAGPDF_API_KEY is not set. Set "
                "RAGPDF_API_KEY to a strong secret, or set "
                "RAGPDF_ALLOW_INSECURE_NO_AUTH=true to explicitly run "
                "without authentication (not recommended)."
            ),
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


class FieldInput(BaseModel):
    field_id: str
    field_name: str | None = ""
    context: str = ""
    section_context: str = ""
    headers: list[str] = []


class PredictRequest(BaseModel):
    user_id: str
    session_id: str
    pdf_id: str
    pdf_hash: str
    pdf_category: dict
    fields: list[FieldInput]


class FilledPDFRequest(BaseModel):
    user_id: str
    session_id: str
    filled_doc_pdf_id: str
    llm_predictions: dict
    final_predictions: dict
    filled_pdf_location: str | None = None


class FeedbackError(BaseModel):
    error_type: str
    field_name: str | None = None
    field_type: str | None = None
    value: Any | None = None
    feedback: str | None = None
    page_number: int | None = None
    corners: list | None = None


class FeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    pdf_id: str
    errors: list[FeedbackError]
    timestamp: str | None = None


class MetricsRequest(BaseModel):
    metric_type: str
    user_id: str | None = None
    session_id: str | None = None
    pdf_id: str | None = None
    category: str | None = None
    subcategory: str | None = None
    doctype: str | None = None
    pdf_hash: str | None = None
    pdfs: list[dict] | None = None


@app.get("/health")
def health():
    return {"status": "ok", "vectors": client._vector_store.count()}


@app.post("/predict")
def predict(req: PredictRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    return {
        "status": "success",
        "data": client.get_predictions(
            user_id=req.user_id,
            session_id=req.session_id,
            pdf_id=req.pdf_id,
            fields=[f.dict() for f in req.fields],
            pdf_hash=req.pdf_hash,
            pdf_category=req.pdf_category,
        ),
    }


@app.post("/save-filled-pdf")
def save_filled_pdf(req: FilledPDFRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    return {
        "status": "success",
        "data": client.save_filled_pdf(
            user_id=req.user_id,
            session_id=req.session_id,
            pdf_id=req.filled_doc_pdf_id,
            llm_predictions=req.llm_predictions,
            final_predictions=req.final_predictions,
        ),
    }


@app.post("/feedback")
def feedback(req: FeedbackRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    return {
        "status": "success",
        "data": client.submit_feedback(
            user_id=req.user_id,
            session_id=req.session_id,
            pdf_id=req.pdf_id,
            errors=[e.dict() for e in req.errors],
            timestamp=req.timestamp,
        ),
    }


@app.post("/metrics")
def metrics(req: MetricsRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    params = {
        k: v for k, v in req.dict().items() if v is not None and k != "metric_type"
    }
    return {"status": "success", "data": client.get_metrics(req.metric_type, **params)}


@app.get("/system-info")
def system_info(x_api_key: str = Header(None)):
    _auth(x_api_key)
    return {"status": "success", "data": client.get_system_info()}


@app.post("/error-analytics")
def error_analytics(body: dict, x_api_key: str = Header(None)):
    _auth(x_api_key)
    return {
        "status": "success",
        "data": client.get_error_analytics(**{k: v for k, v in body.items()}),
    }


if __name__ == "__main__":
    uvicorn.run("entrypoints.fastapi_app:app", host="0.0.0.0", port=8000, reload=True)
