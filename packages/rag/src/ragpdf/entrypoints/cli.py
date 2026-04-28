# entrypoints/cli.py
"""
Command-line interface for pdf-autofillr-rag.

Usage:
    ragpdf init-vectors
    ragpdf init-vectors --source path/to/vector_source.json
    ragpdf init-vectors --backend sentence_transformer
    ragpdf init-vectors --force
    ragpdf system-info
    ragpdf metrics --type global
    ragpdf predict --user u1 --session s1 --pdf p1 \\
        --fields data/rag/input/fields/lp_subscription_fields.json \\
        --hash abc123 \\
        --category data/rag/input/pdf_category.json
    ragpdf feedback --user u1 --session s1 --pdf p1 --errors errors.json
    ragpdf error-analytics --from 2026-01-01T00:00:00Z

  --category accepts EITHER:
    a) a file path:  --category data/rag/input/pdf_category.json   (recommended on Windows)
    b) inline JSON:  --category '{"category":"Finance",...}'          (Linux/Mac only)
"""
import argparse
import json
import os
import sys
from ragpdf import RAGPDFClient


def _load_category(value: str) -> dict:
    """
    Accept --category as either:
      - a path to a JSON file  (data/rag/input/pdf_category.json)
      - an inline JSON string  ({"category":"Finance",...})
    Returns a dict. Exits with a clear message on failure.
    """
    if not value or value == "{}":
        return {}

    # Try as a file path first
    if os.path.exists(value):
        try:
            with open(value, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                print(f"ERROR: --category file must contain a JSON object, got {type(data).__name__}", file=sys.stderr)
                sys.exit(1)
            return data
        except json.JSONDecodeError as e:
            print(f"ERROR: --category file is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)

    # Otherwise treat as inline JSON string
    try:
        data = json.loads(value)
        if not isinstance(data, dict):
            print("ERROR: --category inline value must be a JSON object", file=sys.stderr)
            sys.exit(1)
        return data
    except json.JSONDecodeError:
        print(
            f"\nERROR: --category could not be parsed.\n"
            f"  Got: {value!r}\n\n"
            f"  On Windows, use a file path instead:\n"
            f"    --category data/rag/input/pdf_category.json\n\n"
            f"  On Linux/Mac, inline JSON works:\n"
            f"    --category '{{\"category\":\"Finance\",\"sub_category\":\"PE\",\"document_type\":\"Sub\"}}'",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="ragpdf", description="pdf-autofillr-rag CLI")
    sub = parser.add_subparsers(dest="command")

    # ── init-vectors ──────────────────────────────────────────────────────────
    iv = sub.add_parser(
        "init-vectors",
        help="Generate embeddings from vector_source.json → vector_database.json",
        description=(
            "Reads your vector source file (field definitions, no embeddings) and "
            "generates embeddings using the configured backend, writing the result "
            "to data/rag/vectors/vector_database.json.\n\n"
            "Run this once after setup, or any time you update vector_source.json "
            "with new fields. Existing vectors keep their confidence history — "
            "only new/missing embeddings are generated.\n\n"
            "The source file location (in order of priority):\n"
            "  1. --source flag\n"
            "  2. RAGPDF_DATA_PATH/vectors/source/vector_source.json\n"
            "  3. RAGPDF_DATA_PATH/vectors/source/vector_base.json  (legacy name)\n"
            "  4. Bundled package data (ragpdf/data/vector_source.json)"
        ),
    )
    iv.add_argument(
        "--source", default="",
        help="Path to your vector source JSON (field definitions without embeddings).",
    )
    iv.add_argument(
        "--backend", default="",
        choices=["openai", "sentence_transformer"],
        help=(
            "Embedding backend to use. "
            "Defaults to RAGPDF_EMBEDDING_BACKEND from .env "
            "(openai uses text-embedding-3-small, sentence_transformer uses all-MiniLM-L6-v2)."
        ),
    )
    iv.add_argument(
        "--model", default="",
        help="Embedding model name. Leave blank to use the backend default.",
    )
    iv.add_argument(
        "--data-path", default="", dest="data_path",
        help="RAGPDF_DATA_PATH folder. Defaults to value in .env.",
    )
    iv.add_argument(
        "--force", action="store_true",
        help="Re-embed ALL vectors, even those already embedded.",
    )
    iv.add_argument(
        "--batch-size", default=50, type=int, dest="batch_size",
        help="Vectors per API call (default: 50).",
    )
    iv.add_argument(
        "--no-sanity-check", action="store_true", dest="no_sanity",
        help="Skip the self-test after embedding.",
    )

    # ── predict ───────────────────────────────────────────────────────────────
    p = sub.add_parser("predict", help="Run RAG predictions on PDF fields")
    p.add_argument("--user",    required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--pdf",     required=True)
    p.add_argument("--fields",  required=True, help="Path to JSON file with fields list")
    p.add_argument("--hash",    required=True, help="PDF hash (md5/sha)")
    p.add_argument(
        "--category", default="{}",
        help=(
            "File path (recommended on Windows): --category data/rag/input/pdf_category.json  "
            "OR inline JSON (Linux/Mac): --category '{\"category\":\"Finance\",...}'"
        ),
    )

    # ── system-info ───────────────────────────────────────────────────────────
    sub.add_parser("system-info", help="Show system overview")

    # ── metrics ───────────────────────────────────────────────────────────────
    m = sub.add_parser("metrics", help="Get metrics")
    m.add_argument("--type", required=True, dest="metric_type",
                   choices=["pdf", "category", "subcategory", "doctype",
                             "global", "compare", "pdf_hash"])
    m.add_argument("--user",        default=None)
    m.add_argument("--session",     default=None)
    m.add_argument("--pdf",         default=None)
    m.add_argument("--category",    default=None)
    m.add_argument("--subcategory", default=None)
    m.add_argument("--doctype",     default=None)
    m.add_argument("--pdf-hash",    default=None, dest="pdf_hash")

    # ── feedback ──────────────────────────────────────────────────────────────
    f = sub.add_parser("feedback", help="Submit user feedback/corrections")
    f.add_argument("--user",    required=True)
    f.add_argument("--session", required=True)
    f.add_argument("--pdf",     required=True)
    f.add_argument("--errors",  required=True, help="Path to JSON file with errors list")

    # ── error-analytics ───────────────────────────────────────────────────────
    ea = sub.add_parser("error-analytics", help="Get error analytics")
    ea.add_argument("--from",     default=None, dest="date_from")
    ea.add_argument("--to",       default=None, dest="date_to")
    ea.add_argument("--category", default=None)

    # ── parse ─────────────────────────────────────────────────────────────────
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # ── init-vectors (does NOT need RAGPDFClient) ─────────────────────────────
    if args.command == "init-vectors":
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        from ragpdf.init_vectors import run_init_vectors
        from ragpdf.config.settings import (
            RAGPDF_DATA_PATH,
            RAGPDF_EMBEDDING_BACKEND,
            RAGPDF_ST_MODEL,
            RAGPDF_OPENAI_EMBEDDING_MODEL,
        )

        data_path = args.data_path or RAGPDF_DATA_PATH
        backend   = args.backend   or RAGPDF_EMBEDDING_BACKEND
        model     = args.model     or (
            RAGPDF_OPENAI_EMBEDDING_MODEL if backend == "openai" else RAGPDF_ST_MODEL
        )

        if backend == "noop":
            print(
                "ERROR: RAGPDF_EMBEDDING_BACKEND=noop cannot generate real embeddings.\n"
                "Set RAGPDF_EMBEDDING_BACKEND=openai or sentence_transformer in your .env.",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            result = run_init_vectors(
                data_path=data_path,
                source_path=args.source or None,
                backend=backend,
                model=model,
                force=args.force,
                batch_size=args.batch_size,
                verbose=True,
                sanity_check=not args.no_sanity,
            )
            print()
            print(f"  vectors_total:    {result['vectors_total']}")
            print(f"  vectors_embedded: {result['vectors_embedded']}")
            print(f"  vectors_skipped:  {result['vectors_skipped']}")
            print(f"  model_used:       {result['model_used']}")
            print(f"  runtime_path:     {result['runtime_path']}")
            print()
        except FileNotFoundError as e:
            print(f"\nERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except EnvironmentError as e:
            print(f"\nERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\nERROR: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # ── all other commands need RAGPDFClient ──────────────────────────────────
    client = RAGPDFClient.from_env()

    if args.command == "predict":
        with open(args.fields, encoding="utf-8") as fh:
            fields = json.load(fh)
        if isinstance(fields, dict) and "fields" in fields:
            fields = fields["fields"]

        cat = _load_category(args.category)

        result = client.get_predictions(
            args.user, args.session, args.pdf, fields, args.hash, cat
        )
        print(json.dumps(result, indent=2))

    elif args.command == "system-info":
        print(json.dumps(client.get_system_info(), indent=2))

    elif args.command == "metrics":
        raw   = {k: v for k, v in vars(args).items()
                 if k not in ("command", "metric_type") and v is not None}
        remap = {"user": "user_id", "session": "session_id", "pdf": "pdf_id"}
        kwargs = {remap.get(k, k): v for k, v in raw.items()}
        print(json.dumps(client.get_metrics(args.metric_type, **kwargs), indent=2))

    elif args.command == "feedback":
        with open(args.errors, encoding="utf-8") as fh:
            errors = json.load(fh)
        if isinstance(errors, dict) and "errors" in errors:
            errors = errors["errors"]
        print(json.dumps(
            client.submit_feedback(args.user, args.session, args.pdf, errors),
            indent=2
        ))

    elif args.command == "error-analytics":
        print(json.dumps(
            client.get_error_analytics(
                date_from=args.date_from,
                date_to=args.date_to,
                category=args.category,
            ),
            indent=2
        ))


if __name__ == "__main__":
    main()