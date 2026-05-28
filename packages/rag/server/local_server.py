# server/local_server.py
"""
FastAPI dev server — mirrors all 6 Lambda APIs locally.
Run with: uvicorn server.local_server:app --reload --port 8000
"""

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ragpdf import RAGPDFClient

app = FastAPI(title="ragpdf-sdk dev server", version="0.1.0")

EXPECTED_API_KEY = os.getenv("RAGPDF_API_KEY", "dev-key")
client: RAGPDFClient = None


@app.on_event("startup")
def startup():
    global client
    client = RAGPDFClient.from_env()


def _auth(x_api_key: str = Header(None)):
    if x_api_key != EXPECTED_API_KEY:
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


@app.post("/predict")
def predict(req: PredictRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.get_predictions(
        user_id=req.user_id,
        session_id=req.session_id,
        pdf_id=req.pdf_id,
        fields=[f.dict() for f in req.fields],
        pdf_hash=req.pdf_hash,
        pdf_category=req.pdf_category,
    )
    return {"status": "success", "data": result}


@app.post("/save-filled-pdf")
def save_filled_pdf(req: FilledPDFRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.save_filled_pdf(
        user_id=req.user_id,
        session_id=req.session_id,
        pdf_id=req.filled_doc_pdf_id,
        llm_predictions=req.llm_predictions,
        final_predictions=req.final_predictions,
        filled_pdf_location=req.filled_pdf_location,
    )
    return {"status": "success", "data": result}


@app.post("/feedback")
def feedback(req: FeedbackRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.submit_feedback(
        user_id=req.user_id,
        session_id=req.session_id,
        pdf_id=req.pdf_id,
        errors=[e.dict() for e in req.errors],
        timestamp=req.timestamp,
    )
    return {"status": "success", "data": result}


@app.post("/metrics")
def metrics(req: MetricsRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    params = {
        k: v for k, v in req.dict().items() if v is not None and k != "metric_type"
    }
    result = client.get_metrics(req.metric_type, **params)
    return {"status": "success", "data": result}


@app.get("/system-info")
def system_info(x_api_key: str = Header(None)):
    _auth(x_api_key)
    return {"status": "success", "data": client.get_system_info()}


@app.post("/error-analytics")
def error_analytics(body: dict, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.get_error_analytics(**{k: v for k, v in body.items()})
    return {"status": "success", "data": result}


@app.get("/health")
def health():
    return {"status": "ok", "vectors": client._vector_store.count()}
