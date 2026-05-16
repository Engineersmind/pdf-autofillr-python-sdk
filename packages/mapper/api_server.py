"""

FastAPI Server for PDF Autofiller Mapper Module



Run with: uvicorn api_server:app --reload --port 8000



This provides HTTP API endpoints for the mapper module operations.

"""



from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import asyncio
import os
from pathlib import Path

from pdf_autofillr_mapper.handlers.operations import (
    handle_extract_operation,
    handle_map_operation,
    handle_embed_operation,
    handle_fill_operation,
    handle_make_embed_file_operation,
    handle_check_embed_file_operation,
    handle_fill_pdf_operation,
    handle_run_all_operation
)
from pdf_autofillr_mapper.configs.local import LocalStorageConfig
from pdf_autofillr_mapper.core.logger import logger


app = FastAPI(
    title="PDF Autofiller Mapper API",
    description="API for PDF form field extraction, mapping, embedding, and filling",
    version="1.0.9"
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
    use_second_mapper: Optional[bool] = Field(False, description="Use dual mapper with RAG")


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
        "version": "1.0.9",
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
            "download": "/download/{file_path}"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/mapper/extract")
async def extract(request: ExtractRequest):
    """
    Extract fields from PDF

    Extracts form fields, headers, and structure from the PDF.
    """
    try:
        logger.info(f"API: Extract request for {request.pdf_path}")

        result = await handle_extract_operation(
            input_file=request.pdf_path,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Extract failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/map")
async def map_fields(request: MapRequest):
    """
    Map fields to target schema

    Maps extracted fields to input JSON keys using semantic mapper.
    """
    try:
        logger.info(f"API: Map request for {request.extracted_json_path}")

        from pdf_autofillr_mapper.core.config import get_mapping_config
        mapping_config = get_mapping_config()

        result = await handle_map_operation(
            extracted_json_path=request.extracted_json_path,
            input_json_path=request.input_json_path,
            mapping_config=mapping_config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id,
            investor_type=request.investor_type
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Map failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/embed")
async def embed(request: EmbedRequest):
    """
    Embed metadata into PDF

    Embeds field mappings into the PDF for later filling.
    """
    try:
        logger.info(f"API: Embed request for {request.original_pdf_path}")

        result = await handle_embed_operation(
            original_pdf_path=request.original_pdf_path,
            extracted_json_path=request.extracted_json_path,
            mapping_json_path=request.mapping_json_path,
            radio_groups_path=request.radio_groups_path,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Embed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/fill")
async def fill(request: FillRequest):
    """
    Fill PDF with data

    Fills the embedded PDF with actual data.
    """
    try:
        logger.info(f"API: Fill request for {request.embedded_pdf_path}")

        result = await handle_fill_operation(
            embedded_pdf_path=request.embedded_pdf_path,
            input_json_path=request.input_json_path,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Fill failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/make-embed-file")
async def make_embed_file(request: MakeEmbedRequest):
    """
    Make embed file (Extract -> Map -> Embed pipeline)

    Runs the complete pipeline to create an embedded PDF ready for filling.
    This is the recommended endpoint for preparing PDFs.
    """
    try:
        logger.info(f"API: Make embed file request for {request.pdf_path}")

        config = LocalStorageConfig(local_input_pdf=request.pdf_path)

        from pdf_autofillr_mapper.core.config import get_mapping_config
        mapping_config = get_mapping_config()

        result = await handle_make_embed_file_operation(
            config=config,
            user_id=request.user_id,
            pdf_doc_id=request.pdf_doc_id,
            session_id=request.session_id,
            investor_type=request.investor_type,
            mapping_config=mapping_config,
            use_second_mapper=request.use_second_mapper
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Make embed file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/fill-pdf")
async def fill_pdf(request: FillPDFRequest):
    """
    Fill PDF (with safety checks)

    Fills an embedded PDF with data, with optional validation.
    """
    try:
        logger.info(f"API: Fill PDF request for {request.embedded_pdf_path}")

        config = LocalStorageConfig(
            local_embedded_pdf=request.embedded_pdf_path,
            local_input_json=request.input_json_path
        )

        result = await handle_fill_pdf_operation(
            config=config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Fill PDF failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/check-embed-file")
async def check_embed_file(request: CheckEmbedRequest):
    """
    Check if PDF has embedded metadata

    Verifies if an embedded PDF exists and is ready for filling.
    """
    try:
        logger.info(f"API: Check embed file for {request.pdf_path}")

        config = LocalStorageConfig(local_embedded_pdf=request.pdf_path)

        result = await handle_check_embed_file_operation(
            config=config,
            user_id=request.user_id,
            session_id=request.session_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Check embed file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mapper/run-all")
async def run_all(request: RunAllRequest):
    """
    Run complete pipeline (Extract -> Map -> Embed -> Fill)

    Runs the entire pipeline from raw PDF to filled PDF.
    """
    try:
        logger.info(f"API: Run all request for {request.pdf_path}")

        from pdf_autofillr_mapper.core.config import get_mapping_config
        mapping_config = get_mapping_config()

        result = await handle_run_all_operation(
            input_pdf=request.pdf_path,
            input_json=request.input_json_path,
            mapping_config=mapping_config,
            user_id=request.user_id,
            session_id=request.session_id,
            pdf_doc_id=request.pdf_doc_id
        )

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Run all failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """
    Download file from local storage

    This endpoint allows SDK clients to download generated files (PDFs, JSONs)
    from the local storage. Useful for local deployment scenarios where the
    SDK is on a different machine than the mapper.

    Security: File path is validated to prevent directory traversal attacks.

    Args:
        file_path: Path to file (relative or absolute)

    Returns:
        File content as download

    Example:
        GET /download/output/filled_1234.pdf
        GET /download//absolute/path/to/file.json

    """
    try:
        logger.info(f"API: Download request for {file_path}")

        path = Path(file_path)

        if not path.is_absolute():
            path = Path.cwd() / path

        path = path.resolve()

        if not path.exists():
            logger.error(f"File not found: {path}")
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        if not path.is_file():
            logger.error(f"Not a file: {path}")
            raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

        # Optional: Add whitelist of allowed directories for extra security
        # allowed_dirs = [Path("/path/to/output"), Path("/path/to/temp")]
        # if not any(path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
        #     raise HTTPException(status_code=403, detail="Access denied")

        logger.info(f"Serving file: {path}")

        return FileResponse(
            path=str(path),
            filename=path.name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc)
        }
    )


# ============================================================================
# Main
# ============================================================================


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting PDF Autofiller Mapper API Server...")
    logger.info("API will be available at: http://localhost:8000")
    logger.info("API docs at: http://localhost:8000/docs")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )