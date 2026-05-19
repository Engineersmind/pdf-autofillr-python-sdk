"""
Azure Functions entrypoint for PDF Mapper Module.

This is a THIN wrapper that:
1. Parses Azure Functions HTTP trigger events
2. Validates authentication
3. Calls platform-agnostic handlers from pdf_autofillr_mapper.handlers
4. Returns Azure Functions HTTP response format

The actual business logic is in src/handlers/operations.py
"""

import json
import logging
import os
from typing import Any, Dict

# Azure Functions imports
try:
    import azure.functions as func
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    func = None

from pdf_autofillr_mapper.core.logger import setup_logging
from pdf_autofillr_mapper.core.config import settings

# Import platform-agnostic handlers
from pdf_autofillr_mapper.handlers.operations import (
    handle_extract_operation,
    handle_map_operation,
    handle_embed_operation,
    handle_fill_operation,
    handle_run_all_operation,
    handle_refresh_operation,
    handle_make_embed_file_operation,
    handle_make_form_fields_data_points,
    handle_fill_pdf_operation,
    handle_check_embed_file_operation
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def main(req: "func.HttpRequest") -> "func.HttpResponse":
    """
    Azure Functions HTTP trigger entry point.
    
    Args:
        req: Azure Functions HTTP request object
        
    Returns:
        Azure Functions HTTP response object
    """
    if not AZURE_AVAILABLE:
        return func.HttpResponse(
            json.dumps({
                "error": "Azure Functions package not installed. Install with: pip install azure-functions"
            }),
            status_code=500,
            mimetype="application/json"
        )
    
    logger.info("Azure Function triggered")
    
    try:
        # Parse request body
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON in request body"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Extract operation type
        operation = req_body.get("operation")
        if not operation:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'operation' field"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # TODO: Add authentication/authorization here
        # auth_header = req.headers.get("Authorization")
        
        # Route to appropriate handler
        result = route_operation(operation, req_body)
        
        return func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                "error": str(e),
                "type": type(e).__name__
            }),
            status_code=500,
            mimetype="application/json"
        )


def route_operation(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route the operation to the appropriate handler.
    
    Args:
        operation: Operation type
        payload: Request payload
        
    Returns:
        Handler response
    """
    handlers = {
        "extract": handle_extract_operation,
        "map": handle_map_operation,
        "embed": handle_embed_operation,
        "fill": handle_fill_operation,
        "run_all": handle_run_all_operation,
        "refresh": handle_refresh_operation,
        "make_embed_file": handle_make_embed_file_operation,
        "make_form_fields_data_points": handle_make_form_fields_data_points,
        "fill_pdf": handle_fill_pdf_operation,
        "check_embed_file": handle_check_embed_file_operation,
    }
    
    handler = handlers.get(operation)
    if not handler:
        raise ValueError(f"Unknown operation: {operation}")
    
    return handler(payload)


# =============================================================================
# Local Testing
# =============================================================================
if __name__ == "__main__":
    """
    For local testing without Azure Functions runtime.
    """
    print("Azure Functions entrypoint - for local testing, use FastAPI or CLI instead")
    
    # Example test payload
    test_payload = {
        "operation": "check_embed_file",
        "pdf_path": "test.pdf"
    }
    
    result = route_operation(test_payload["operation"], test_payload)
    print(json.dumps(result, indent=2))
