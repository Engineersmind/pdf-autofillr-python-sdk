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
import asyncio
import json
import logging
import sys

from pdf_autofillr_mapper.configs.local import build_operation_config
from pdf_autofillr_mapper.core.logger import setup_logging
from pdf_autofillr_mapper.utils.ini_config import get_ini_config

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


def _copy_result_output(result: dict, output_path: str | None, logger_) -> None:
    """Copy whichever output file key is present in `result` to `output_path`."""
    if not output_path:
        return
    import shutil

    for key in ("filled_pdf", "embedded_pdf", "output_file"):
        src = result.get(key)
        if src:
            shutil.copy2(src, output_path)
            logger_.info(f"Copied {key} -> {output_path}")
            return
    logger_.warning(
        f"No recognized output file key in result to copy to {output_path}"
    )


def extract_command(args):
    """Extract fields from PDF."""
    logger.info(f"Extracting fields from: {args.pdf_path}")

    config = build_operation_config(pdf_path=args.pdf_path, session_id=args.session_id)
    result = asyncio.run(
        handle_extract_operation(config=config, session_id=args.session_id)
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to: {args.output}")
    else:
        print(json.dumps(result, indent=2))

    return result


def map_command(args):
    """Map PDF fields."""
    logger.info(f"Mapping fields for: {args.pdf_path}")

    # Note: handle_map_operation has no direct "mapper_type" switch — mapping
    # strategy comes from mapping_config / investor_type. args.mapper_type is
    # accepted for CLI compatibility but not currently wired through.
    config = build_operation_config(
        pdf_path=args.pdf_path,
        input_json_path=args.input_json,
        session_id=args.session_id,
    )
    mapping_config = get_ini_config().get_mapping_config()
    result = asyncio.run(
        handle_map_operation(
            config=config,
            mapping_config=mapping_config,
            session_id=args.session_id,
        )
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to: {args.output}")
    else:
        print(json.dumps(result, indent=2))

    return result


def embed_command(args):
    """Embed metadata into PDF."""
    logger.info(f"Embedding metadata into: {args.pdf_path}")

    # Reuses the same deterministic output paths extract/map wrote to for
    # this pdf_path — run extract and map first for the same pdf_path.
    config = build_operation_config(pdf_path=args.pdf_path, session_id=args.session_id)
    result = asyncio.run(
        handle_embed_operation(config=config, session_id=args.session_id)
    )
    _copy_result_output(result, args.output, logger)

    logger.info("Metadata embedded successfully")
    print(json.dumps(result, indent=2))

    return result


def fill_command(args):
    """Fill PDF form with data."""
    logger.info(f"Filling PDF: {args.pdf_path}")

    # Load data from JSON file (also validates it's well-formed JSON early)
    if args.data_file:
        with open(args.data_file) as f:
            json.load(f)
    else:
        logger.error("Data file is required for fill operation")
        sys.exit(1)

    config = build_operation_config(
        pdf_path=args.pdf_path,
        input_json_path=args.data_file,
        session_id=args.session_id,
    )
    result = asyncio.run(
        handle_fill_pdf_operation(config=config, session_id=args.session_id)
    )
    _copy_result_output(result, args.output, logger)

    logger.info("PDF filled successfully")
    print(json.dumps(result, indent=2))

    return result


def make_embed_file_command(args):
    """Extract + Map + Embed in one operation."""
    logger.info(f"Creating embed file for: {args.pdf_path}")

    config = build_operation_config(pdf_path=args.pdf_path, session_id=args.session_id)
    mapping_config = get_ini_config().get_mapping_config()
    # handle_make_embed_file_operation requires real user_id/pdf_doc_id (not
    # Optional) — default to 1 for standalone CLI use with no multi-tenant
    # identifiers.
    result = asyncio.run(
        handle_make_embed_file_operation(
            config=config,
            user_id=1,
            pdf_doc_id=1,
            session_id=args.session_id,
            mapping_config=mapping_config,
        )
    )
    _copy_result_output(result, args.output, logger)

    logger.info("Embed file created successfully")
    print(json.dumps(result, indent=2))

    return result


def check_embed_file_command(args):
    """Check if PDF has embedded metadata."""
    logger.info(f"Checking embed status for: {args.pdf_path}")

    config = build_operation_config(pdf_path=args.pdf_path)
    result = asyncio.run(handle_check_embed_file_operation(config=config))

    print(json.dumps(result, indent=2))

    return result


def run_all_command(args):
    """Run complete pipeline."""
    logger.info(f"Running complete pipeline for: {args.pdf_path}")

    mapping_config = get_ini_config().get_mapping_config()
    result = asyncio.run(
        handle_run_all_operation(
            input_pdf=args.pdf_path,
            input_json=args.input_json or "",
            mapping_config=mapping_config,
            session_id=args.session_id,
        )
    )
    _copy_result_output(result, args.output, logger)

    logger.info("Pipeline completed successfully")
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
        """,
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
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
    map_parser.add_argument(
        "--mapper-type",
        default="ensemble",
        choices=["semantic", "rag", "headers", "ensemble"],
        help="Mapper type to use",
    )
    map_parser.add_argument("--session-id", help="Session ID for tracking")
    map_parser.add_argument(
        "--input-json", help="Path to input JSON data to map fields against (required)"
    )
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
    fill_parser.add_argument(
        "-d", "--data-file", required=True, help="JSON file with data"
    )
    fill_parser.add_argument("-o", "--output", required=True, help="Output PDF file")
    fill_parser.add_argument("--session-id", help="Session ID for tracking")
    fill_parser.set_defaults(func=fill_command)

    # Make embed file command
    make_embed_parser = subparsers.add_parser(
        "make-embed-file", help="Extract + Map + Embed"
    )
    make_embed_parser.add_argument("pdf_path", help="Path to input PDF")
    make_embed_parser.add_argument(
        "-o", "--output", required=True, help="Output PDF file"
    )
    make_embed_parser.add_argument("--session-id", help="Session ID for tracking")
    make_embed_parser.set_defaults(func=make_embed_file_command)

    # Check embed file command
    check_embed_parser = subparsers.add_parser(
        "check-embed-file", help="Check if PDF has embedded metadata"
    )
    check_embed_parser.add_argument("pdf_path", help="Path to input PDF")
    check_embed_parser.set_defaults(func=check_embed_file_command)

    # Run all command
    run_all_parser = subparsers.add_parser("run-all", help="Run complete pipeline")
    run_all_parser.add_argument("pdf_path", help="Path to input PDF")
    run_all_parser.add_argument("-o", "--output", required=True, help="Output PDF file")
    run_all_parser.add_argument("--session-id", help="Session ID for tracking")
    run_all_parser.add_argument(
        "--input-json", help="Path to input JSON data (required for the map stage)"
    )
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
        args.func(args)
        sys.exit(0)

    except Exception as e:
        logger.error(f"Command failed: {str(e)}", exc_info=True)
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
