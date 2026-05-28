# chatbot/src/chatbot/entrypoints/cli.py
"""
chatbot-cli — interactive terminal session.

After `pip install pdf-autofillr-chatbot`:
    chatbot-cli
    chatbot-cli --pdf-path /path/to/blank.pdf --output filled.json --report
    chatbot-cli --message "Hello" --user-id u1 --session-id s1
"""

from __future__ import annotations

import os
import sys

# ── UTF-8 fix for Windows ─────────────────────────────────────────────────────
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ── Logging: all detail to file, terminal stays clean ────────────────────────
def _setup_logging(log_level: str = "WARNING") -> None:
    log_dir = Path(os.getcwd()) / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "chatbot.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    # Silence on terminal — WARNING level
    for name in [
        "LiteLLM",
        "litellm",
        "httpx",
        "httpcore",
        "openai",
        "chatbot",
        "ragpdf",
        "urllib3",
        "asyncio",
    ]:
        logging.getLogger(name).setLevel(logging.WARNING)

    # Mapper is very noisy — suppress to ERROR only
    for name in [
        "pdf_autofillr_mapper",
        "pdf_autofillr_mapper.mappers.semantic_mapper",
        "pdf_autofillr_mapper.extractors.detailed_fitz",
        "pdf_autofillr_mapper.orchestrator.PDFPipeline",
        "pdf_autofillr_mapper.embedders.embed_keys",
        "pdf_autofillr_mapper.groupers.group_by_llm",
        "pdf_autofillr_mapper.clients.unified_llm_client",
        "pdf_autofillr_mapper.utils.storage",
        "pdf_autofillr_mapper.chunkers",
        "pdf_autofillr_mapper.inprocess_filler",
    ]:
        logging.getLogger(name).setLevel(logging.ERROR)

    # Only show WARNING+ on terminal
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    root.addHandler(console)


logger = logging.getLogger(__name__)


def _parse_args():
    p = argparse.ArgumentParser(
        prog="chatbot-cli",
        description="pdf-autofillr-chatbot — conversational investor onboarding",
    )
    p.add_argument("--user-id", default="cli_user")
    p.add_argument("--session-id", default=None)
    p.add_argument("--message", default=None, help="Single message (non-interactive)")
    p.add_argument("--pdf-path", default=None)
    p.add_argument("--output", default=None, help="Save filled data to JSON file")
    p.add_argument("--report", action="store_true")
    p.add_argument("--log-level", default="WARNING")
    return p.parse_args()


def _build_client():
    from chatbot import FormConfig, chatbotClient
    from chatbot.storage.factory import StorageFactory

    storage = StorageFactory.create()
    config_path = os.getenv("chatbot_CONFIG_PATH", "./configs")
    form_config = FormConfig.from_directory(config_path)

    pdf_filler = None
    if os.getenv("chatbot_PDF_FILLER", "none").lower() in ("mapper", "managed"):
        from chatbot.pdf.mapper_filler import MapperPDFFiller

        pdf_filler = MapperPDFFiller(
            mapper_api_url=os.getenv("MAPPER_API_URL", ""),
            mapper_api_key=os.getenv("MAPPER_API_KEY", ""),
        )

    return chatbotClient(
        storage=storage,
        form_config=form_config,
        pdf_filler=pdf_filler,
    )


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
    pdf_path = args.pdf_path or os.getenv("chatbot_PDF_PATH", "")
    print("\n" + "=" * 60)
    print("  pdf-autofillr-chatbot")
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


def main():
    args = _parse_args()
    _setup_logging(args.log_level)
    try:
        client = _build_client()
        session_id = args.session_id or str(uuid.uuid4())
        if args.message is not None:
            _run_single(args, client, session_id)
        else:
            _run_interactive(args, client, session_id)
    except OSError as e:
        print(f"\n❌ Config error:\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
