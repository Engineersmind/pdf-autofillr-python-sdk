"""
Command-Line Interface (CLI) for PDF Mapper Module.

This provides a CLI for local testing and development with:
- Command-line arguments for all operations
- Local file processing
- Progress indicators
- Detailed logging

The actual business logic is in src/handlers/operations.py
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

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


def extract_command(args):
    """Extract fields from PDF."""
    logger.info(f"Extracting fields from: {args.pdf_path}")
    
    payload = {
        "pdf_path": args.pdf_path,
        "session_id": args.session_id,
    }
    
    result = handle_extract_operation(payload)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to: {args.output}")
    else:
        print(json.dumps(result, indent=2))
    
    return result


def map_command(args):
    """Map PDF fields."""
    logger.info(f"Mapping fields for: {args.pdf_path}")
    
    payload = {
        "pdf_path": args.pdf_path,
        "session_id": args.session_id,
        "mapper_type": args.mapper_type,
    }
    
    result = handle_map_operation(payload)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to: {args.output}")
    else:
        print(json.dumps(result, indent=2))
    
    return result


def embed_command(args):
    """Embed metadata into PDF."""
    logger.info(f"Embedding metadata into: {args.pdf_path}")
    
    payload = {
        "pdf_path": args.pdf_path,
        "session_id": args.session_id,
        "output_path": args.output,
    }
    
    result = handle_embed_operation(payload)
    
    logger.info(f"Metadata embedded successfully")
    print(json.dumps(result, indent=2))
    
    return result


def fill_command(args):
    """Fill PDF form with data."""
    logger.info(f"Filling PDF: {args.pdf_path}")
    
    # Load data from JSON file
    if args.data_file:
        with open(args.data_file, 'r') as f:
            data = json.load(f)
    else:
        logger.error("Data file is required for fill operation")
        sys.exit(1)
    
    payload = {
        "pdf_path": args.pdf_path,
        "data": data,
        "output_path": args.output,
        "session_id": args.session_id,
    }
    
    result = handle_fill_pdf_operation(payload)
    
    logger.info(f"PDF filled successfully")
    print(json.dumps(result, indent=2))
    
    return result


def make_embed_file_command(args):
    """Extract + Map + Embed in one operation."""
    logger.info(f"Creating embed file for: {args.pdf_path}")
    
    payload = {
        "pdf_path": args.pdf_path,
        "session_id": args.session_id,
        "output_path": args.output,
    }
    
    result = handle_make_embed_file_operation(payload)
    
    logger.info(f"Embed file created successfully")
    print(json.dumps(result, indent=2))
    
    return result


def check_embed_file_command(args):
    """Check if PDF has embedded metadata."""
    logger.info(f"Checking embed status for: {args.pdf_path}")
    
    payload = {
        "pdf_path": args.pdf_path,
    }
    
    result = handle_check_embed_file_operation(payload)
    
    print(json.dumps(result, indent=2))
    
    return result


def run_all_command(args):
    """Run complete pipeline."""
    logger.info(f"Running complete pipeline for: {args.pdf_path}")
    
    payload = {
        "pdf_path": args.pdf_path,
        "session_id": args.session_id,
        "output_path": args.output,
    }
    
    result = handle_run_all_operation(payload)
    
    logger.info(f"Pipeline completed successfully")
    print(json.dumps(result, indent=2))
    
    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PDF Mapper CLI - Extract, Map, Embed, and Fill PDF forms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract fields from PDF
  pdf-mapper extract input.pdf
  
  # Map fields with ensemble mapper
  pdf-mapper map input.pdf --mapper-type ensemble
  
  # Create embed file (extract + map + embed)
  pdf-mapper make-embed-file input.pdf -o output.pdf
  
  # Check if PDF has embedded metadata
  pdf-mapper check-embed-file input.pdf
  
  # Fill PDF with data
  pdf-mapper fill input.pdf --data-file data.json -o filled.pdf
  
  # Run complete pipeline
  pdf-mapper run-all input.pdf -o final.pdf
        """
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract fields from PDF")
    extract_parser.add_argument("pdf_path", help="Path to input PDF")
    extract_parser.add_argument("-o", "--output", help="Output JSON file")
    extract_parser.add_argument("--session-id", help="Session ID for tracking")
    extract_parser.set_defaults(func=extract_command)
    
    # Map command
    map_parser = subparsers.add_parser("map", help="Map PDF fields")
    map_parser.add_argument("pdf_path", help="Path to input PDF")
    map_parser.add_argument("-o", "--output", help="Output JSON file")
    map_parser.add_argument("--mapper-type", default="ensemble", 
                           choices=["semantic", "rag", "headers", "ensemble"],
                           help="Mapper type to use")
    map_parser.add_argument("--session-id", help="Session ID for tracking")
    map_parser.set_defaults(func=map_command)
    
    # Embed command
    embed_parser = subparsers.add_parser("embed", help="Embed metadata into PDF")
    embed_parser.add_argument("pdf_path", help="Path to input PDF")
    embed_parser.add_argument("-o", "--output", required=True, help="Output PDF file")
    embed_parser.add_argument("--session-id", help="Session ID for tracking")
    embed_parser.set_defaults(func=embed_command)
    
    # Fill command
    fill_parser = subparsers.add_parser("fill", help="Fill PDF form with data")
    fill_parser.add_argument("pdf_path", help="Path to input PDF")
    fill_parser.add_argument("-d", "--data-file", required=True, help="JSON file with data")
    fill_parser.add_argument("-o", "--output", required=True, help="Output PDF file")
    fill_parser.add_argument("--session-id", help="Session ID for tracking")
    fill_parser.set_defaults(func=fill_command)
    
    # Make embed file command
    make_embed_parser = subparsers.add_parser("make-embed-file", 
                                               help="Extract + Map + Embed")
    make_embed_parser.add_argument("pdf_path", help="Path to input PDF")
    make_embed_parser.add_argument("-o", "--output", required=True, help="Output PDF file")
    make_embed_parser.add_argument("--session-id", help="Session ID for tracking")
    make_embed_parser.set_defaults(func=make_embed_file_command)
    
    # Check embed file command
    check_embed_parser = subparsers.add_parser("check-embed-file", 
                                                help="Check if PDF has embedded metadata")
    check_embed_parser.add_argument("pdf_path", help="Path to input PDF")
    check_embed_parser.set_defaults(func=check_embed_file_command)
    
    # Run all command
    run_all_parser = subparsers.add_parser("run-all", help="Run complete pipeline")
    run_all_parser.add_argument("pdf_path", help="Path to input PDF")
    run_all_parser.add_argument("-o", "--output", required=True, help="Output PDF file")
    run_all_parser.add_argument("--session-id", help="Session ID for tracking")
    run_all_parser.set_defaults(func=run_all_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        # Execute command
        result = args.func(args)
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Command failed: {str(e)}", exc_info=True)
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
