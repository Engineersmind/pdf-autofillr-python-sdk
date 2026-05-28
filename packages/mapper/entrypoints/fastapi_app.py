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


class ExtractRequest(OperationRequest):
    """Request model for extract operation."""

    pass


class MapRequest(OperationRequest):
    """Request model for map operation."""

    mapper_type: Optional[str] = Field(
        "ensemble", description="Mapper type: semantic, rag, headers, ensemble"
    )


class EmbedRequest(OperationRequest):
    """Request model for embed operation."""

    pass


class FillRequest(OperationRequest):
    """Request model for fill operation."""

    data: dict[str, Any] = Field(..., description="Data to fill into PDF")


class MakeEmbedFileRequest(OperationRequest):
    """Request model for make_embed_file operation."""

    pass


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
        version="1.0.10",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # =============================================================================
    # Authentication (Simple API Key - enhance as needed)
    # =============================================================================

    async def verify_api_key(x_api_key: str = Header(None)):
        """Verify API key from header."""
        # TODO: Implement proper authentication
        expected_key = settings.api_key if hasattr(settings, "api_key") else None
        if expected_key and x_api_key != expected_key:
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
            "version": "1.0.10",
            "docs": "/docs",
        }

    # =============================================================================
    # Operation Endpoints
    # =============================================================================

    @app.post("/extract", response_model=OperationResponse)
    async def extract(request: ExtractRequest, api_key: str = Depends(verify_api_key)):
        """Extract fields from PDF."""
        try:
            result = handle_extract_operation(request.dict())
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Extract operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/map", response_model=OperationResponse)
    async def map_fields(request: MapRequest, api_key: str = Depends(verify_api_key)):
        """Map PDF fields to target schema."""
        try:
            result = handle_map_operation(request.dict())
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
            result = handle_embed_operation(request.dict())
            return OperationResponse(success=True, data=result)
        except Exception as e:
            logger.error(f"Embed operation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/fill", response_model=OperationResponse)
    async def fill_pdf(request: FillRequest, api_key: str = Depends(verify_api_key)):
        """Fill PDF form with data."""
        try:
            result = handle_fill_pdf_operation(request.dict())
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
            result = handle_make_embed_file_operation(request.dict())
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
            result = handle_check_embed_file_operation(request.dict())
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
            result = handle_run_all_operation(request.dict())
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
