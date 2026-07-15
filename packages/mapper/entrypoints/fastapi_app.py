"""
FastAPI REST API entrypoint for PDF Mapper Module.

This provides a REST API interface for the mapper module with:
- Multiple endpoints for different operations
- OpenAPI/Swagger documentation
- Request validation with Pydantic
- Async support
- Authentication middleware

The actual business logic is in src/handlers/operations.py
"""

import hmac
import logging
from typing import Any, Optional

# FastAPI imports
try:
    import uvicorn
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None  # type: ignore[no-redef, misc, assignment]
    HTTPException = None  # type: ignore[no-redef, misc, assignment]

from pdf_autofillr_mapper.core.config import settings
from pdf_autofillr_mapper.core.logger import setup_logging

# Builds a fully-populated config object (config.local_* paths etc.) from a
# bare pdf_path — see its docstring for why this exists.
from pdf_autofillr_mapper.configs.local import build_operation_config, validate_request_path

# Import platform-agnostic handlers
from pdf_autofillr_mapper.handlers.operations import (
    handle_check_embed_file_operation,
    handle_embed_operation,
    handle_extract_operation,
    handle_fill_pdf_operation,
    handle_make_embed_file_operation,
    handle_map_operation,
    handle_run_all_operation,
)

import json
import os

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================


class OperationRequest(BaseModel):
    """Base request model for operations."""

    pdf_path: str = Field(..., description="Path to PDF file")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    user_id: Optional[int] = Field(None, description="User ID for tracking")
    pdf_doc_id: Optional[int] = Field(None, description="PDF document ID for tracking")
    input_json_path: Optional[str] = Field(
        None, description="Path to input JSON data, if this operation needs it"
    )


class ExtractRequest(OperationRequest):
    """Request model for extract operation."""

    pass


class MapRequest(OperationRequest):
    """Request model for map operation."""

    mapper_type: Optional[str] = Field(
        "ensemble", description="Mapper type: semantic, rag, headers, ensemble"
    )
    mapping_config: Optional[dict[str, Any]] = Field(
        None, description="Mapping configuration overrides (all keys optional)"
    )


class EmbedRequest(OperationRequest):
    """Request model for embed operation."""

    pass


class FillRequest(OperationRequest):
    """Request model for fill operation."""

    data: dict[str, Any] = Field(..., description="Data to fill into PDF")


class MakeEmbedFileRequest(OperationRequest):
    """Request model for make_embed_file operation."""

    investor_type: str = Field("individual", description="Investor type for mapping")
    mapping_config: Optional[dict[str, Any]] = Field(
        None, description="Mapping configuration overrides (all keys optional)"
    )
    use_second_mapper: bool = Field(
        False, description="Whether to use the second (RAG) mapper"
    )


class CheckEmbedFileRequest(OperationRequest):
    """Request model for check_embed_file operation."""

    pass


class OperationResponse(BaseModel):
    """Standard response model."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# =============================================================================
# FastAPI App Setup
# =============================================================================

if not FASTAPI_AVAILABLE:
    app = None
else:
    app = FastAPI(
        title="PDF Mapper API",
        description="Platform-agnostic PDF field extraction, mapping, embedding, and filling API",
        version="1.0.11",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware — restrict to an explicit allow-list in production via
    # MAPPER_CORS_ALLOWED_ORIGINS (comma-separated). "*" is only used if that
    # env var is left unset, which keeps local/dev usage simple but should
    # never be relied on in a real deployment.
    import os as _os

    _cors_origins_env = _os.getenv("MAPPER_CORS_ALLOWED_ORIGINS", "")
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] or [
        "*"
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=_cors_origins != ["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # =============================================================================
    # Authentication (API Key, fail-closed)
    # =============================================================================

    # Set MAPPER_ALLOW_INSECURE_NO_AUTH=true to explicitly run without auth
    # (local dev only). Otherwise a missing API key is a startup/config error,
    # not a silent bypass — this closes the "auth disabled if unset" hole.
    _allow_insecure_no_auth = (
        _os.getenv("MAPPER_ALLOW_INSECURE_NO_AUTH", "false").lower() == "true"
    )

    async def verify_api_key(x_api_key: str = Header(None)):
        """Verify API key from header. Fails closed if none is configured."""
        expected_key = settings.api_key if hasattr(settings, "api_key") else None
        if not expected_key:
            if _allow_insecure_no_auth:
                return x_api_key
            raise HTTPException(
                status_code=500,
                detail=(
                    "Server misconfigured: no API key configured. Set the "
                    "mapper API key setting (see settings.api_key / "
                    "MAPPER_API_KEY), or set "
                    "MAPPER_ALLOW_INSECURE_NO_AUTH=true to explicitly run "
                    "without authentication (not recommended)."
                ),
            )
        if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
        return x_api_key

    # =============================================================================
    # Health Check
    # =============================================================================

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "pdf-mapper"}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "PDF Mapper API",
            "version": "1.0.11",
            "docs": "/docs",
        }

    # =============================================================================
    # Operation Endpoints
    # =============================================================================

    @app.post("/extract", response_model=OperationResponse)
    async def extract(request: ExtractRequest, api_key: str = Depends(verify_api_key)):
        """Extract fields from PDF."""
        try:
            config = build_operation_config(
                pdf_path=validate_request_path(request.pdf_path, label="pdf_path"),
                input_json_path=validate_request_path(request.input_json_path, label="input_json_path") if request.input_json_path else None,
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
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Extract operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/map", response_model=OperationResponse)
    async def map_fields(request: MapRequest, api_key: str = Depends(verify_api_key)):
        """Map PDF fields to target schema."""
        try:
            config = build_operation_config(
                pdf_path=validate_request_path(request.pdf_path, label="pdf_path"),
                input_json_path=validate_request_path(request.input_json_path, label="input_json_path") if request.input_json_path else None,
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            result = await handle_map_operation(
                config=config,
                mapping_config=request.mapping_config or {},
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Map operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/embed", response_model=OperationResponse)
    async def embed_metadata(
        request: EmbedRequest, api_key: str = Depends(verify_api_key)
    ):
        """Embed metadata into PDF."""
        try:
            config = build_operation_config(
                pdf_path=validate_request_path(request.pdf_path, label="pdf_path"),
                input_json_path=validate_request_path(request.input_json_path, label="input_json_path") if request.input_json_path else None,
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            result = await handle_embed_operation(
                config=config,
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Embed operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/fill", response_model=OperationResponse)
    async def fill_pdf(request: FillRequest, api_key: str = Depends(verify_api_key)):
        """Fill PDF form with data."""
        try:
            config = build_operation_config(
                pdf_path=validate_request_path(request.pdf_path, label="pdf_path"),
                input_json_path=validate_request_path(request.input_json_path, label="input_json_path") if request.input_json_path else None,
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            # handle_fill_pdf_operation reads fill data from
            # config.local_input_json — write the caller's `data` there
            # (this is what makes /fill self-contained: the caller sends
            # data in the request body rather than a pre-existing file).
            fill_data_path = config.local_input_json or os.path.join(
                config.base_dir, f"{os.path.splitext(os.path.basename(request.pdf_path))[0]}_fill_data.json"
            )
            os.makedirs(os.path.dirname(fill_data_path), exist_ok=True)
            with open(fill_data_path, "w", encoding="utf-8") as f:
                json.dump(request.data, f)
            config.local_input_json = fill_data_path

            result = await handle_fill_pdf_operation(
                config=config,
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Fill operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/make-embed-file", response_model=OperationResponse)
    async def make_embed_file(
        request: MakeEmbedFileRequest, api_key: str = Depends(verify_api_key)
    ):
        """Extract + Map + Embed in one operation."""
        try:
            config = build_operation_config(
                pdf_path=validate_request_path(request.pdf_path, label="pdf_path"),
                input_json_path=validate_request_path(request.input_json_path, label="input_json_path") if request.input_json_path else None,
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            # handle_make_embed_file_operation requires real user_id/pdf_doc_id
            # (not Optional) — default to 1 for standalone/demo callers that
            # don't track multi-tenant identifiers.
            result = await handle_make_embed_file_operation(
                config=config,
                user_id=request.user_id or 1,
                pdf_doc_id=request.pdf_doc_id or 1,
                session_id=request.session_id,
                investor_type=request.investor_type,
                mapping_config=request.mapping_config or {},
                use_second_mapper=request.use_second_mapper,
            )
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Make embed file operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/check-embed-file", response_model=OperationResponse)
    async def check_embed_file(
        request: CheckEmbedFileRequest, api_key: str = Depends(verify_api_key)
    ):
        """Check if PDF has embedded metadata."""
        try:
            config = build_operation_config(
                pdf_path=validate_request_path(request.pdf_path, label="pdf_path"),
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            result = await handle_check_embed_file_operation(
                config=config,
                user_id=request.user_id,
                session_id=request.session_id,
            )
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Check embed file operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/run-all", response_model=OperationResponse)
    async def run_all(
        request: OperationRequest, api_key: str = Depends(verify_api_key)
    ):
        """Run complete pipeline: Extract + Map + Embed + Fill."""
        try:
            result = await handle_run_all_operation(
                input_pdf=validate_request_path(request.pdf_path, label="pdf_path"),
                input_json=(
                    validate_request_path(request.input_json_path, label="input_json_path")
                    if request.input_json_path
                    else ""
                ),
                mapping_config={},
                user_id=request.user_id,
                session_id=request.session_id,
                pdf_doc_id=request.pdf_doc_id,
            )
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Run all operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run the FastAPI server."""
    if not FASTAPI_AVAILABLE:
        print("ERROR: FastAPI not installed")
        print("Install with: pip install fastapi uvicorn[standard]")
        return

    host = getattr(settings, "api_host", "0.0.0.0")
    port = getattr(settings, "api_port", 8000)
    reload = getattr(settings, "api_reload", False)

    logger.info(f"Starting FastAPI server on {host}:{port}")

    uvicorn.run(
        "entrypoints.fastapi_app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
