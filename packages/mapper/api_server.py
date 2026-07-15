"""

FastAPI Server for PDF Autofiller Mapper Module



Run with: uvicorn api_server:app --reload --port 8000



This provides HTTP API endpoints for the mapper module operations.

"""

import hmac
import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from pdf_autofillr_mapper.configs.local import LocalStorageConfig, build_operation_config
from pdf_autofillr_mapper.core.config import settings
from pdf_autofillr_mapper.core.logger import logger
from pdf_autofillr_mapper.utils.ini_config import get_ini_config
from pdf_autofillr_mapper.handlers.operations import (
    handle_check_embed_file_operation,
    handle_embed_operation,
    handle_extract_operation,
    handle_fill_operation,
    handle_fill_pdf_operation,
    handle_make_embed_file_operation,
    handle_map_operation,
    handle_run_all_operation,
)

app = FastAPI(
    title="PDF Autofiller Mapper API",
    description="API for PDF form field extraction, mapping, embedding, and filling",
    version="1.0.11",
)

# ============================================================================
# Authentication (API Key, fail-closed) — mirrors entrypoints/fastapi_app.py
# ============================================================================

# Set MAPPER_ALLOW_INSECURE_NO_AUTH=true to explicitly run without auth
# (local dev only). Otherwise a missing API key is a startup/config error,
# not a silent bypass. This app previously had NO authentication on any
# endpoint at all, including /mapper/* operations that read arbitrary local
# file paths (pdf_path) and /download/{file_path} which serves files back.
_ALLOW_INSECURE_NO_AUTH = os.getenv("MAPPER_ALLOW_INSECURE_NO_AUTH", "false").lower() == "true"


async def verify_api_key(x_api_key: str = Header(None)):
    expected_key = settings.api_key if hasattr(settings, "api_key") else None
    if not expected_key:
        if _ALLOW_INSECURE_NO_AUTH:
            return x_api_key
        raise HTTPException(
            status_code=500,
            detail=(
                "Server misconfigured: no API key configured. Set the "
                "mapper API key (API_KEY env var), or set "
                "MAPPER_ALLOW_INSECURE_NO_AUTH=true to explicitly run "
                "without authentication (not recommended)."
            ),
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# Directory /download is allowed to serve from. Previously this endpoint
# allowed anything under the server process's current working directory,
# which typically also contains source code, .env files, and other secrets
# — not just generated output. Restricted to the actual output directory.
_DOWNLOAD_ROOT = Path(
    os.getenv("MAPPER_DOWNLOAD_ROOT", LocalStorageConfig().base_dir)
).resolve()

# Directories user-supplied path fields (pdf_path, extracted_json_path, etc.)
# are allowed to point into. Defaults to _DOWNLOAD_ROOT; extend with
# MAPPER_ALLOWED_INPUT_ROOTS (comma-separated) if your PDFs/JSON live
# elsewhere (e.g. an uploads directory).
_ALLOWED_INPUT_ROOTS = [_DOWNLOAD_ROOT] + [
    Path(r).resolve()
    for r in os.getenv("MAPPER_ALLOWED_INPUT_ROOTS", "").split(",")
    if r.strip()
]


def _validate_path(raw_path: str, *, label: str) -> str:
    """
    Normalize `raw_path` and verify it lives inside one of
    _ALLOWED_INPUT_ROOTS. Every request field that ends up being read from
    or written to disk (pdf_path, extracted_json_path, input_json_path,
    embedded_pdf_path, mapping_json_path, radio_groups_path,
    original_pdf_path) must go through this before being used — otherwise
    an authenticated-but-malicious caller can read/write arbitrary files
    on the server (CWE-22 / CodeQL py/path-injection).

    Uses os.path.abspath + normpath (pure string manipulation) rather than
    Path.resolve() (which also follows symlinks via filesystem I/O) — the
    confinement check below is exactly as strict either way, but this form
    isn't a filesystem-touching operation itself.
    """
    normalized = os.path.normpath(os.path.abspath(raw_path))
    for root in _ALLOWED_INPUT_ROOTS:
        root_str = str(root)
        if normalized == root_str or normalized.startswith(root_str + os.sep):
            return normalized
    raise HTTPException(
        status_code=400,
        detail=(
            f"Invalid {label}: '{raw_path}' resolves to '{normalized}', which "
            f"is outside the allowed directories "
            f"{[str(r) for r in _ALLOWED_INPUT_ROOTS]}. Set "
            f"MAPPER_ALLOWED_INPUT_ROOTS if your files live elsewhere."
        ),
    )


# ============================================================================
# Request Models
# ============================================================================


class ExtractRequest(BaseModel):
    pdf_path: str = Field(..., description="Path to PDF file (local)")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")


class MapRequest(BaseModel):
    extracted_json_path: str = Field(..., description="Path to extracted JSON")
    input_json_path: str = Field(..., description="Path to input JSON with data")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")
    investor_type: Optional[str] = Field("individual", description="Investor type")


class EmbedRequest(BaseModel):
    original_pdf_path: str = Field(..., description="Path to original PDF")
    extracted_json_path: str = Field(..., description="Path to extracted JSON")
    mapping_json_path: str = Field(..., description="Path to mapping JSON")
    radio_groups_path: str = Field(..., description="Path to radio groups JSON")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")


class FillRequest(BaseModel):
    embedded_pdf_path: str = Field(..., description="Path to embedded PDF")
    input_json_path: str = Field(..., description="Path to input JSON with data")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")


class MakeEmbedRequest(BaseModel):
    pdf_path: str = Field(..., description="Path to input PDF file")
    user_id: Optional[int] = Field(1, description="User ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    investor_type: Optional[str] = Field("individual", description="Investor type")
    use_second_mapper: Optional[bool] = Field(
        False, description="Use dual mapper with RAG"
    )


class FillPDFRequest(BaseModel):
    embedded_pdf_path: str = Field(..., description="Path to embedded PDF")
    input_json_path: str = Field(..., description="Path to input JSON")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")


class CheckEmbedRequest(BaseModel):
    pdf_path: str = Field(..., description="Path to PDF file to check")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")


class RunAllRequest(BaseModel):
    pdf_path: str = Field(..., description="Path to input PDF")
    input_json_path: str = Field(..., description="Path to input JSON with data")
    user_id: Optional[int] = Field(1, description="User ID")
    session_id: Optional[int] = Field(None, description="Session ID")
    pdf_doc_id: Optional[int] = Field(100, description="PDF document ID")


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "PDF Autofiller Mapper API",
        "version": "1.0.11",
        "status": "running",
        "endpoints": {
            "extract": "/mapper/extract",
            "map": "/mapper/map",
            "embed": "/mapper/embed",
            "fill": "/mapper/fill",
            "make_embed_file": "/mapper/make-embed-file",
            "fill_pdf": "/mapper/fill-pdf",
            "check_embed": "/mapper/check-embed-file",
            "run_all": "/mapper/run-all",
            "download": "/download/{file_path}",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/mapper/extract")
async def extract(request: ExtractRequest, api_key: str = Depends(verify_api_key)):
    """
    Extract fields from PDF

    Extracts form fields, headers, and structure from the PDF.
    """
    try:
        logger.info(f"API: Extract request for {request.pdf_path}")

        validated_pdf_path = _validate_path(request.pdf_path, label="pdf_path")
        config = build_operation_config(
            pdf_path=validated_pdf_path,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )
        result = await handle_extract_operation(
            config=config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Extract failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/map")
async def map_fields(request: MapRequest, api_key: str = Depends(verify_api_key)):
    """
    Map fields to target schema

    Maps extracted fields to input JSON keys using semantic mapper.
    """
    try:
        logger.info(f"API: Map request for {request.extracted_json_path}")

        mapping_config = get_ini_config().get_mapping_config()

        validated_extracted_json = _validate_path(
            request.extracted_json_path, label="extracted_json_path"
        )
        validated_input_json = _validate_path(
            request.input_json_path, label="input_json_path"
        )
        config = LocalStorageConfig()
        config.local_extracted_json = validated_extracted_json
        config.local_input_json = validated_input_json
        stem = Path(validated_extracted_json).stem
        config.local_mapped_json = os.path.join(config.base_dir, f"{stem}_mapped_fields.json")
        config.local_radio_json = os.path.join(
            config.base_dir, f"{stem}_radio_groups.json"
        )

        result = await handle_map_operation(
            config=config,
            mapping_config=mapping_config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
            investor_type=request.investor_type,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Map failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/embed")
async def embed(request: EmbedRequest, api_key: str = Depends(verify_api_key)):
    """
    Embed metadata into PDF

    Embeds field mappings into the PDF for later filling.
    """
    try:
        logger.info(f"API: Embed request for {request.original_pdf_path}")

        validated_pdf_path = _validate_path(request.original_pdf_path, label="original_pdf_path")
        config = LocalStorageConfig()
        config.local_input_pdf = validated_pdf_path
        config.local_extracted_json = _validate_path(
            request.extracted_json_path, label="extracted_json_path"
        )
        config.local_mapped_json = _validate_path(
            request.mapping_json_path, label="mapping_json_path"
        )
        config.local_radio_json = _validate_path(
            request.radio_groups_path, label="radio_groups_path"
        )
        stem = Path(validated_pdf_path).stem
        config.local_embedded_pdf = os.path.join(
            config.base_dir, f"{stem}_embedded.pdf"
        )

        result = await handle_embed_operation(
            config=config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Embed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/fill")
async def fill(request: FillRequest, api_key: str = Depends(verify_api_key)):
    """
    Fill PDF with data

    Fills the embedded PDF with actual data.
    """
    try:
        logger.info(f"API: Fill request for {request.embedded_pdf_path}")

        validated_embedded_pdf = _validate_path(
            request.embedded_pdf_path, label="embedded_pdf_path"
        )
        config = LocalStorageConfig()
        config.local_embedded_pdf = validated_embedded_pdf
        config.local_input_json = _validate_path(
            request.input_json_path, label="input_json_path"
        )
        stem = Path(validated_embedded_pdf).stem
        config.local_filled_pdf = os.path.join(config.base_dir, f"{stem}_filled.pdf")

        result = await handle_fill_operation(
            config=config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Fill failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/make-embed-file")
async def make_embed_file(request: MakeEmbedRequest, api_key: str = Depends(verify_api_key)):
    """
    Make embed file (Extract -> Map -> Embed pipeline)

    Runs the complete pipeline to create an embedded PDF ready for filling.
    This is the recommended endpoint for preparing PDFs.
    """
    try:
        logger.info(f"API: Make embed file request for {request.pdf_path}")

        config = build_operation_config(
            pdf_path=_validate_path(request.pdf_path, label="pdf_path"),
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )

        mapping_config = get_ini_config().get_mapping_config()

        result = await handle_make_embed_file_operation(
            config=config,
            user_id=request.user_id,
            pdf_doc_id=request.pdf_doc_id,
            session_id=request.session_id,
            investor_type=request.investor_type,
            mapping_config=mapping_config,
            use_second_mapper=request.use_second_mapper,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Make embed file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/fill-pdf")
async def fill_pdf(request: FillPDFRequest, api_key: str = Depends(verify_api_key)):
    """
    Fill PDF (with safety checks)

    Fills an embedded PDF with data, with optional validation.
    """
    try:
        logger.info(f"API: Fill PDF request for {request.embedded_pdf_path}")

        config = LocalStorageConfig()
        config.local_embedded_pdf = _validate_path(
            request.embedded_pdf_path, label="embedded_pdf_path"
        )
        config.local_input_json = _validate_path(
            request.input_json_path, label="input_json_path"
        )

        result = await handle_fill_pdf_operation(
            config=config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Fill PDF failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/check-embed-file")
async def check_embed_file(request: CheckEmbedRequest, api_key: str = Depends(verify_api_key)):
    """
    Check if PDF has embedded metadata

    Verifies if an embedded PDF exists and is ready for filling.
    """
    try:
        logger.info(f"API: Check embed file for {request.pdf_path}")

        config = LocalStorageConfig()
        config.local_embedded_pdf = _validate_path(request.pdf_path, label="pdf_path")

        result = await handle_check_embed_file_operation(
            config=config, user_id=request.user_id, session_id=request.session_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Check embed file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/mapper/run-all")
async def run_all(request: RunAllRequest, api_key: str = Depends(verify_api_key)):
    """
    Run complete pipeline (Extract -> Map -> Embed -> Fill)

    Runs the entire pipeline from raw PDF to filled PDF.
    """
    try:
        logger.info(f"API: Run all request for {request.pdf_path}")

        mapping_config = get_ini_config().get_mapping_config()

        result = await handle_run_all_operation(
            input_pdf=_validate_path(request.pdf_path, label="pdf_path"),
            input_json=_validate_path(request.input_json_path, label="input_json_path"),
            mapping_config=mapping_config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Run all failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/download/{file_path:path}")
async def download_file(file_path: str, api_key: str = Depends(verify_api_key)):
    """
    Download file from local storage

    This endpoint allows SDK clients to download generated files (PDFs, JSONs)
    from the local storage. Useful for local deployment scenarios where the
    SDK is on a different machine than the mapper.

    Security: File path is validated to prevent directory traversal attacks,
    and must resolve inside the mapper's output directory (MAPPER_DOWNLOAD_ROOT,
    default: the same base_dir LocalStorageConfig writes output to) — not just
    "somewhere under the server's current working directory", which could
    include source code, .env files, and other secrets.

    Args:
        file_path: Path to file (relative or absolute)

    Returns:
        File content as download

    Example:
        GET /download/output/filled_1234.pdf

    """
    try:
        logger.info(f"API: Download request for {file_path}")

        if ".." in file_path.replace("\\", "/").split("/"):
            raise HTTPException(status_code=403, detail="Access denied")

        safe_file_path = file_path.lstrip("/\\")
        # Pure string normalization (no filesystem I/O / symlink following)
        # — normpath collapses ".."/"."/redundant separators; the confinement
        # check right after rejects anything that escapes _DOWNLOAD_ROOT
        # before the path is ever opened.
        normalized = os.path.normpath(str(_DOWNLOAD_ROOT / safe_file_path))
        download_root_str = str(_DOWNLOAD_ROOT)
        if not (
            normalized == download_root_str
            or normalized.startswith(download_root_str + os.sep)
        ):
            raise HTTPException(status_code=403, detail="Access denied")
        path = Path(normalized)

        if not path.exists():
            logger.error(f"File not found: {path}")
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        if not path.is_file():
            logger.error(f"Not a file: {path}")
            raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

        logger.info(f"Serving file: {path}")

        return FileResponse(
            path=str(path), filename=path.name, media_type="application/octet-stream"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500, content={"error": "Internal Server Error", "detail": str(exc)}
    )


# ============================================================================
# Main
# ============================================================================


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting PDF Autofiller Mapper API Server...")
    logger.info("API will be available at: http://localhost:8000")
    logger.info("API docs at: http://localhost:8000/docs")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
