# entrypoints/cli.py
"""
Command-line interface for pdf-autofillr-rag.

Usage:
    ragpdf system-info
    ragpdf metrics --type global
    ragpdf predict --user u1 --session s1 --pdf p1 \
        --fields data/input/fields/lp_subscription_fields.json \
        --hash abc123 \
        --category data/input/pdf_category.json
    ragpdf feedback --user u1 --session s1 --pdf p1 --errors errors.json
    ragpdf error-analytics --from 2026-01-01T00:00:00Z

  --category accepts EITHER:
    a) a file path:  --category data/input/pdf_category.json   (recommended on Windows)
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
      - a path to a JSON file  (data/input/pdf_category.json)
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
                print(
                    f"ERROR: --category file must contain a JSON object, got {type(data).__name__}",
                    file=sys.stderr,
                )
                sys.exit(1)
            return data
        except json.JSONDecodeError as e:
            print(f"ERROR: --category file is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)

    # Otherwise treat as inline JSON string
    try:
        data = json.loads(value)
        if not isinstance(data, dict):
            print(
                "ERROR: --category inline value must be a JSON object", file=sys.stderr
            )
            sys.exit(1)
        return data
    except json.JSONDecodeError:
        print(
            f"\nERROR: --category could not be parsed.\n"
            f"  Got: {value!r}\n\n"
            f"  On Windows, use a file path instead:\n"
            f"    --category data/input/pdf_category.json\n\n"
            f"  On Linux/Mac, inline JSON works:\n"
            f'    --category \'{{"category":"Finance","sub_category":"PE","document_type":"Sub"}}\'',
            file=sys.stderr,
        )
        sys.exit(1)
    return {}


def main():
    parser = argparse.ArgumentParser(prog="ragpdf", description="pdf-autofillr-rag CLI")
    sub = parser.add_subparsers(dest="command")

    # predict
    p = sub.add_parser("predict", help="Run RAG predictions on PDF fields")
    p.add_argument("--user", required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--pdf", required=True)
    p.add_argument("--fields", required=True, help="Path to JSON file with fields list")
    p.add_argument("--hash", required=True, help="PDF hash (md5/sha)")
    p.add_argument(
        "--category",
        default="{}",
        help=(
            "File path (recommended on Windows): --category data/input/pdf_category.json  "
            'OR inline JSON (Linux/Mac): --category \'{"category":"Finance",...}\''
        ),
    )

    # system-info
    sub.add_parser("system-info", help="Show system overview")

    # metrics
    m = sub.add_parser("metrics", help="Get metrics")
    m.add_argument(
        "--type",
        required=True,
        dest="metric_type",
        choices=[
            "pdf",
            "category",
            "subcategory",
            "doctype",
            "global",
            "compare",
            "pdf_hash",
        ],
    )
    m.add_argument("--user", default=None)
    m.add_argument("--session", default=None)
    m.add_argument("--pdf", default=None)
    m.add_argument("--category", default=None)
    m.add_argument("--subcategory", default=None)
    m.add_argument("--doctype", default=None)
    m.add_argument("--pdf-hash", default=None, dest="pdf_hash")

    # feedback
    f = sub.add_parser("feedback", help="Submit user feedback/corrections")
    f.add_argument("--user", required=True)
    f.add_argument("--session", required=True)
    f.add_argument("--pdf", required=True)
    f.add_argument("--errors", required=True, help="Path to JSON file with errors list")

    # error-analytics
    ea = sub.add_parser("error-analytics", help="Get error analytics")
    ea.add_argument("--from", default=None, dest="date_from")
    ea.add_argument("--to", default=None, dest="date_to")
    ea.add_argument("--category", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

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
        kwargs = {
            k: v
            for k, v in vars(args).items()
            if k not in ("command", "metric_type") and v is not None
        }
        print(json.dumps(client.get_metrics(args.metric_type, **kwargs), indent=2))

    elif args.command == "feedback":
        with open(args.errors, encoding="utf-8") as fh:
            errors = json.load(fh)
        if isinstance(errors, dict) and "errors" in errors:
            errors = errors["errors"]
        print(
            json.dumps(
                client.submit_feedback(args.user, args.session, args.pdf, errors),
                indent=2,
            )
        )

    elif args.command == "error-analytics":
        print(
            json.dumps(
                client.get_error_analytics(
                    date_from=args.date_from,
                    date_to=args.date_to,
                    category=args.category,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
