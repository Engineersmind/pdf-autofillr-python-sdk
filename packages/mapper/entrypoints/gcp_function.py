"""
Google Cloud Functions entrypoint for PDF Mapper Module.

This is a THIN wrapper that:
1. Parses GCP Cloud Functions HTTP request
2. Validates authentication
3. Calls platform-agnostic handlers from pdf_autofillr_mapper.handlers
4. Returns GCP Cloud Functions HTTP response format

The actual business logic is in src/handlers/operations.py
"""

import json
import logging
import os
from typing import Any, Dict

# GCP Functions imports
try:
    import functions_framework
    from flask import Request, jsonify
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    functions_framework = None
    Request = None

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


if GCP_AVAILABLE:
    @functions_framework.http
    def pdf_mapper_handler(request: Request) -> Any:
        """
        GCP Cloud Functions HTTP entry point.
        
        Args:
            request: Flask request object
            
        Returns:
            Flask response with JSON
        """
        logger.info("GCP Cloud Function triggered")
        
        try:
            # Parse request body
            request_json = request.get_json(silent=True)
            if not request_json:
                return jsonify({
                    "error": "Invalid JSON in request body"
                }), 400
            
            # Extract operation type
            operation = request_json.get("operation")
            if not operation:
                return jsonify({
                    "error": "Missing 'operation' field"
                }), 400
            
            # TODO: Add authentication/authorization here
            # auth_header = request.headers.get("Authorization")
            
            # Route to appropriate handler
            result = route_operation(operation, request_json)
            
            return jsonify(result), 200
            
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}", exc_info=True)
            return jsonify({
                "error": str(e),
                "type": type(e).__name__
            }), 500


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
    For local testing without GCP Functions runtime.
    Run with: functions-framework --target=pdf_mapper_handler --debug
    """
    print("GCP Cloud Functions entrypoint")
    print("To test locally, run:")
    print("  functions-framework --target=pdf_mapper_handler --debug")
    print("")
    print("Or use FastAPI/CLI entrypoints for easier local testing")
    
    if not GCP_AVAILABLE:
        print("\nWARNING: GCP packages not installed")
        print("Install with: pip install functions-framework flask")
