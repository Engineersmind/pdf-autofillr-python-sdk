# server/local_server.py
"""
FastAPI dev server — mirrors all 6 Lambda APIs locally.
Run with: uvicorn server.local_server:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Any
import os

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
    field_name: Optional[str] = ""
    context: str = ""
    section_context: str = ""
    headers: List[str] = []


class PredictRequest(BaseModel):
    user_id: str
    session_id: str
    pdf_id: str
    pdf_hash: str
    pdf_category: dict
    fields: List[FieldInput]


class FilledPDFRequest(BaseModel):
    user_id: str
    session_id: str
    filled_doc_pdf_id: str
    llm_predictions: dict
    final_predictions: dict
    filled_pdf_location: Optional[str] = None


class FeedbackError(BaseModel):
    error_type: str
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    value: Optional[Any] = None
    feedback: Optional[str] = None
    page_number: Optional[int] = None
    corners: Optional[List] = None


class FeedbackRequest(BaseModel):
    user_id: str
    session_id: str
    pdf_id: str
    errors: List[FeedbackError]
    timestamp: Optional[str] = None


class MetricsRequest(BaseModel):
    metric_type: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    pdf_id: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    doctype: Optional[str] = None
    pdf_hash: Optional[str] = None
    pdfs: Optional[List[dict]] = None


@app.post("/predict")
def predict(req: PredictRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.get_predictions(
        user_id=req.user_id, session_id=req.session_id, pdf_id=req.pdf_id,
        fields=[f.dict() for f in req.fields],
        pdf_hash=req.pdf_hash, pdf_category=req.pdf_category,
    )
    return {"status": "success", "data": result}


@app.post("/save-filled-pdf")
def save_filled_pdf(req: FilledPDFRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.save_filled_pdf(
        user_id=req.user_id, session_id=req.session_id, pdf_id=req.filled_doc_pdf_id,
        llm_predictions=req.llm_predictions, final_predictions=req.final_predictions,
        filled_pdf_location=req.filled_pdf_location,
    )
    return {"status": "success", "data": result}


@app.post("/feedback")
def feedback(req: FeedbackRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    result = client.submit_feedback(
        user_id=req.user_id, session_id=req.session_id, pdf_id=req.pdf_id,
        errors=[e.dict() for e in req.errors], timestamp=req.timestamp,
    )
    return {"status": "success", "data": result}


@app.post("/metrics")
def metrics(req: MetricsRequest, x_api_key: str = Header(None)):
    _auth(x_api_key)
    params = {k: v for k, v in req.dict().items() if v is not None and k != "metric_type"}
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
