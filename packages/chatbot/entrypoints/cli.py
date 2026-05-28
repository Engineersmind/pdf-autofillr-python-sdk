# chatbot/entrypoints/cli.py
"""
Command-line interface for the chatbot module.

Usage::

    # Interactive session (default)
    chatbot-cli

    # Single turn
    chatbot-cli --message "Hello"

    # With PDF
    chatbot-cli --pdf-path /path/to/blank.pdf

    # Save output and print fill report
    chatbot-cli --output filled_data.json --report

Options:
    --user-id     USER_ID     (default: cli_user)
    --session-id  SESSION_ID  (default: random UUID)
    --message     MESSAGE     Single message — non-interactive
    --pdf-path    PATH        Path to blank PDF
    --output      PATH        Save final JSON data to file
    --report                  Print fill report at end
    --log-level   LEVEL       (default: WARNING)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv()


def _build_client():
    from chatbot import FormConfig, chatbotClient
    from chatbot.storage.factory import StorageFactory

    storage = StorageFactory.create()
    config_path = os.getenv("chatbot_CONFIG_PATH", "./config_samples")
    form_config = FormConfig.from_directory(config_path)

    pdf_filler = None
    if os.getenv("chatbot_PDF_FILLER", "none").lower() in ("mapper", "managed"):
        from chatbot.pdf.mapper_filler import MapperPDFFiller

        pdf_filler = MapperPDFFiller(
            mapper_api_url=os.getenv("MAPPER_API_URL", ""),
            mapper_api_key=os.getenv("MAPPER_API_KEY", ""),
        )

    return chatbotClient(
        # api_key read from CHATBOT_LLM_API_KEY env var automatically
        storage=storage,
        form_config=form_config,
        pdf_filler=pdf_filler,
    )


def _parse_args():
    parser = argparse.ArgumentParser(prog="chatbot-cli", description="chatbot CLI")
    parser.add_argument("--user-id", default="cli_user")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--message", default=None)
    parser.add_argument("--pdf-path", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--log-level", default="WARNING")
    return parser.parse_args()


def _run_single(args, client, session_id):
    pdf_path = args.pdf_path or os.getenv("chatbot_PDF_PATH", "")
    if pdf_path:
        client.create_session(args.user_id, session_id, pdf_path=pdf_path)
    response, complete, data = client.send_message(
        args.user_id, session_id, args.message
    )
    print(response)
    if complete:
        if args.output and data:
            Path(args.output).write_text(json.dumps(data, indent=2, default=str))
            print(f"\n✅ Saved to: {args.output}", file=sys.stderr)
        if args.report:
            text = client.get_fill_report_text(args.user_id, session_id)
            if text:
                print("\n" + text, file=sys.stderr)


def _run_interactive(args, client, session_id):
    import time

    pdf_path = args.pdf_path or os.getenv("chatbot_PDF_PATH", "")
    print("\n" + "=" * 60)
    print("  chatbot — Interactive CLI")
    print("=" * 60)
    if pdf_path:
        print(f"  PDF: {pdf_path}")
        client.create_session(args.user_id, session_id, pdf_path=pdf_path)
    print(f"  Session: {session_id}")
    print("  Type 'exit' to quit.\n" + "-" * 60 + "\n")

    response, complete, data = client.send_message(args.user_id, session_id, "")
    print(f"Bot: {response}\n")

    while not complete:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break
        if user_input.lower() in ("exit", "quit", "q"):
            print("Session ended.")
            break
        response, complete, data = client.send_message(
            args.user_id, session_id, user_input
        )
        print(f"\nBot: {response}\n")

    if complete:
        print("\n" + "=" * 60 + "\n  Session complete!\n" + "=" * 60)
        if data:
            print(json.dumps(data, indent=2, default=str))
        if args.output and data:
            Path(args.output).write_text(json.dumps(data, indent=2, default=str))
            print(f"\n✅ Saved to: {args.output}")
        if args.report:
            text = client.get_fill_report_text(args.user_id, session_id)
            if text:
                print("\nFill Report:\n" + text)
        # Wait for background PDF fill thread (daemon) to finish before exit
        if os.getenv("chatbot_PDF_FILLER", "none").lower() != "none":
            print("\nWaiting for PDF fill to complete...")
            for _ in range(120):
                time.sleep(1)
                state = client.storage.get_session_state(args.user_id, session_id) or {}
                if state.get("filled_pdf_path"):
                    print(f"✅ PDF filled: {state['filled_pdf_path']}")
                    break
            else:
                print("⚠️  PDF fill still running — check calling_filling_logs.json")


def main():
    args = _parse_args()
    logging.basicConfig(level=args.log_level)
    try:
        client = _build_client()
        session_id = args.session_id or str(uuid.uuid4())
        if args.message is not None:
            _run_single(args, client, session_id)
        else:
            _run_interactive(args, client, session_id)
    except OSError as e:
        print(f"\n❌ Configuration error:\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
