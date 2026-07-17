# extractor/entrypoints/fastapi_app.py
"""
FastAPI app entrypoint — can be mounted standalone or into a larger app.

Standalone::
    uvicorn entrypoints.fastapi_app:app --reload

Mount into existing FastAPI app::
    from entrypoints.fastapi_app import app as extractor_app
    main_app.mount("/extractor", extractor_app)

Endpoints:
    POST /extract          — run extraction (+ optional PDF fill)
    GET  /jobs/{job_id}    — get job output
    GET  /health           — health check
"""

from __future__ import annotations

import hmac
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

try:
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError as e:
    raise ImportError(
        "fastapi and uvicorn are required: pip install 'pdf-autofillr-doc-upload[server]'"
    ) from e

from pdf_autofillr_doc_upload.storage.local_storage import PathAccessError

app = FastAPI(
    title="pdf-autofillr-doc-upload",
    version="0.1.6",
    description="Document extraction + PDF filling API",
)

_client = None


def _get_client():
    global _client
    if _client is None:
        from pdf_autofillr_doc_upload import DocUploadClient
        from pdf_autofillr_doc_upload.extraction.extractor import Extractor
        from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient
        from pdf_autofillr_doc_upload.storage.factory import StorageFactory

        storage = StorageFactory.create()
        extractor = Extractor(llm_client=LLMClient())

        pdf_filler = None  # DocUploadClient._build_default_filler handles this from env

        _client = DocUploadClient(
            storage=storage, extractor=extractor, pdf_filler=pdf_filler
        )
    return _client


# ── Request / response models ────────────────────────────────────────────────


class ExtractRequest(BaseModel):
    document_path: str
    schema_path: str = "configs/form_keys.json"
    job_id: str | None = None
    output_path: str | None = None
    user_id: str | None = None
    pdf_doc_id: str | None = None
    session_id: str | None = None
    investor_type: str = "Individual"
    filled_doc_pdf_id: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "service": "pdf-autofillr-doc-upload"}


@app.post("/extract")
def extract(
    request: ExtractRequest,
    x_api_key: str | None = Header(default=None),
):
    _check_api_key(x_api_key)
    client = _get_client()
    job_id = request.job_id or str(uuid.uuid4())
    try:
        # document_path/schema_path here are untrusted HTTP input. Validate
        # them against the allowed roots *before* they reach the storage
        # backend — this is what actually prevents the arbitrary local file
        # disclosure previously possible via this endpoint. LocalStorage's
        # download_document()/load_schema() remain deliberately unrestricted
        # for trusted, programmatic (non-HTTP) use of the library.
        #
        # This runs unconditionally, regardless of storage backend — a
        # previous version only validated when the configured backend
        # happened to implement assert_path_allowed() (LocalStorage only),
        # silently skipping validation entirely for S3/GCS/Azure backends.
        _assert_path_allowed(request.document_path, purpose="document")
        _assert_path_allowed(request.schema_path, purpose="schema")
        result = client.run(
            document_path=request.document_path,
            schema_path=request.schema_path,
            job_id=job_id,
            output_path=request.output_path,
            user_id=request.user_id,
            pdf_doc_id=request.pdf_doc_id,
            session_id=request.session_id,
            investor_type=request.investor_type,
            filled_doc_pdf_id=request.filled_doc_pdf_id,
        )
        return JSONResponse(
            content={
                "status": "success",
                "job_id": job_id,
                "output_flat": result["output_flat"],
                "output_path": result.get("output_path"),
            }
        )
    except PathAccessError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/jobs/{job_id}/output")
def get_job_output(job_id: str, x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    client = _get_client()
    data = client.storage.get_output(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JSONResponse(content=data)


@app.get("/jobs/{job_id}/output-flat")
def get_job_output_flat(job_id: str, x_api_key: str | None = Header(default=None)):
    _check_api_key(x_api_key)
    client = _get_client()
    data = client.storage.get_output_flat(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JSONResponse(content=data)


# ── API key helper ───────────────────────────────────────────────────────────

# Set this explicitly to allow running with no auth (e.g. local dev only).
# Anything other than "true" means auth is mandatory — the previous
# behaviour of silently disabling auth when AUTH_TOKEN was unset allowed
# unauthenticated arbitrary local file disclosure and is no longer allowed.
_ALLOW_INSECURE_NO_AUTH = os.getenv("DOC_UPLOAD_ALLOW_INSECURE_NO_AUTH", "false").lower() == "true"


def _check_api_key(provided: str | None) -> None:
    expected = os.environ.get("AUTH_TOKEN")
    if not expected:
        if _ALLOW_INSECURE_NO_AUTH:
            return  # explicitly opted into no-auth mode
        raise HTTPException(
            status_code=500,
            detail=(
                "Server misconfigured: AUTH_TOKEN is not set. Set AUTH_TOKEN "
                "to a strong secret, or set DOC_UPLOAD_ALLOW_INSECURE_NO_AUTH=true "
                "to explicitly run without authentication (not recommended)."
            ),
        )
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


def _allowed_path_roots() -> list[Path]:
    """
    Roots that document_path/schema_path are allowed to resolve into,
    independent of which storage backend (local/S3/GCS/Azure) is
    configured. Reads the same env vars LocalStorage does, so behavior is
    identical when LocalStorage is active, but this no longer depends on
    the storage backend implementing assert_path_allowed at all — the
    previous hasattr() guard silently skipped validation entirely for any
    cloud backend, leaving the original arbitrary-file-read vulnerability
    open whenever DOC_UPLOAD_STORAGE was s3/gcp/azure.
    """
    roots = [
        Path(os.getenv("DOC_UPLOAD_DATA_PATH", "./data/doc_upload")).resolve(),
        Path(os.getenv("DOC_UPLOAD_CONFIG_PATH", "./configs")).resolve(),
    ]
    roots += [
        Path(r).resolve()
        for r in os.getenv("DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS", "").split(",")
        if r.strip()
    ]
    return roots


def _assert_path_allowed(raw_path: str, *, purpose: str) -> None:
    """
    Resolve raw_path (following symlinks) and verify it lives inside one
    of _allowed_path_roots(). Runs unconditionally for every request,
    regardless of storage backend — this is an HTTP boundary concern, not
    a storage-backend concern, and must not be skippable by configuring a
    cloud backend.
    """
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        base = Path(os.getenv("DOC_UPLOAD_CONFIG_PATH", "./configs")).resolve() \
            if purpose == "schema" \
            else Path(os.getenv("DOC_UPLOAD_DATA_PATH", "./data/doc_upload")).resolve()
        candidate = base / raw_path
    resolved = candidate.resolve()
    for root in _allowed_path_roots():
        try:
            resolved.relative_to(root)
            return
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"{purpose} path is outside the allowed directories.",
    )


def main():
    import uvicorn

    uvicorn.run(
        "entrypoints.fastapi_app:app",
        host=os.getenv("DOC_UPLOAD_HOST", "0.0.0.0"),
        port=int(os.getenv("DOC_UPLOAD_PORT", "8001")),
        reload=os.getenv("DOC_UPLOAD_RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
