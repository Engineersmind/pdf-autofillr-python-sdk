# chatbot/entrypoints/local.py
"""
Local deployment entrypoint.

Python-callable interface and interactive REPL — no FastAPI server needed.

Usage::

    from entrypoints.local import run_session

    for msg in ["", "Alice Johnson", "alice@example.com"]:
        response, complete, data = run_session("user_1", "sess_1", msg)
        print(f"Bot: {response}")
        if complete:
            print("Filled data:", data)
            break

Or run interactively::

    python -m entrypoints.local
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Suppress Python warnings (e.g. fitz/pymupdf UserWarning)
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

# ── Silence third-party noise so only Bot/You lines reach the terminal ──────
# The mapper emits WARNING-level logs (duplicate key notices etc.) that are
# informational only — route them to the session log file, not the terminal.
logging.basicConfig(level=logging.WARNING)
logging.getLogger("pdf_autofillr_mapper").setLevel(logging.ERROR)
logging.getLogger("pymupdf").setLevel(logging.ERROR)
logging.getLogger("fitz").setLevel(logging.ERROR)


# ── Suppress pymupdf's "Consider using pymupdf_layout" print() at import ────
# fitz/__init__.py calls print() (not warnings.warn) so filterwarnings can't
# catch it. We suppress stdout briefly while forcing the first fitz import so
# the message never reaches the terminal during the session.
def _silence_fitz_import() -> None:
    import io

    _real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        import fitz  # noqa: F401  — triggers the print inside fitz/__init__.py
    except ImportError:
        pass  # intentional
    finally:
        sys.stdout = _real_stdout


_silence_fitz_import()


# ── Terminal log helpers ─────────────────────────────────────────────────────


def _terminal_log_path(data_path: str, user_id: str, session_id: str) -> Path:
    """Returns the path for this session's terminal_log.json."""
    p = Path(data_path) / user_id / "sessions" / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p / "terminal_log.json"


def _save_terminal_log(log_path: Path, entries: list) -> None:
    """Write the terminal log entries to disk (overwrites each time)."""
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "entries": entries,
                },
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
    except Exception:
        pass  # Non-fatal — never crash the session over logging


def _append_log(entries: list, role: str, text: str) -> None:
    """Append one entry to the in-memory terminal log list."""
    entries.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,  # "bot" | "user" | "system"
            "text": text,
        }
    )


# ── Client builder ───────────────────────────────────────────────────────────


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


# ── Public programmatic API ──────────────────────────────────────────────────


def run_session(
    user_id: str,
    session_id: str,
    message: str,
    pdf_path: str | None = None,
    client=None,
) -> tuple[str, bool, dict | None]:
    if client is None:
        client = _build_client()
    if pdf_path:
        client.create_session(user_id, session_id, pdf_path=pdf_path)
    return client.send_message(user_id=user_id, session_id=session_id, message=message)


# ── Interactive REPL ─────────────────────────────────────────────────────────


def run_interactive() -> None:
    print("\n" + "=" * 60)
    print("  chatbot — Interactive Local Session")
    print("=" * 60)
    print("Type your responses and press Enter. Type 'exit' to quit.\n")

    client = _build_client()
    user_id = "local_user"
    session_id = str(uuid.uuid4())
    pdf_path = os.getenv("chatbot_PDF_PATH", "")

    # Resolve data_path for the terminal log file
    data_path = os.getenv("chatbot_DATA_PATH", "./chatbot_data")
    log_path = _terminal_log_path(data_path, user_id, session_id)
    terminal_entries: list[dict] = []

    if pdf_path:
        client.create_session(user_id, session_id, pdf_path=pdf_path)
        print(f"PDF: {pdf_path}\n")

    print("-" * 60)

    try:
        response, complete, data = client.send_message(user_id, session_id, "")
        print(f"Bot: {response}\n")
        _append_log(terminal_entries, "bot", response)
        _save_terminal_log(log_path, terminal_entries)

        while not complete:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                msg = "Session ended."
                print(f"\n\n{msg}")
                _append_log(terminal_entries, "system", msg)
                _save_terminal_log(log_path, terminal_entries)
                break

            if user_input.lower() in ("exit", "quit", "q"):
                msg = "Session ended."
                print(msg)
                _append_log(terminal_entries, "system", msg)
                _save_terminal_log(log_path, terminal_entries)
                break

            _append_log(terminal_entries, "user", user_input)

            response, complete, data = client.send_message(
                user_id, session_id, user_input
            )
            print(f"\nBot: {response}\n")
            _append_log(terminal_entries, "bot", response)
            _save_terminal_log(log_path, terminal_entries)

        if complete:
            print("\n" + "=" * 60)
            print("  Session complete!")
            print("=" * 60)
            if data:
                print(json.dumps(data, indent=2, default=str))
            report = client.get_fill_report_text(user_id, session_id)
            if report:
                print("\nFill Report:\n" + report)

            # Wait for background PDF fill thread (daemon) to finish before exit
            if os.getenv("chatbot_PDF_FILLER", "none").lower() != "none":
                import time

                wait_msg = "Waiting for PDF fill to complete..."
                print(f"\n{wait_msg}")
                _append_log(terminal_entries, "system", wait_msg)
                _save_terminal_log(log_path, terminal_entries)

                for _ in range(120):
                    time.sleep(1)
                    state = client.storage.get_session_state(user_id, session_id) or {}

                    # Prefer the clean output copy path; fall back to filled_pdf_path
                    filled = state.get("filled_pdf_output") or state.get(
                        "filled_pdf_path"
                    )
                    if filled:
                        success_msg = f"✅ PDF filled: {filled}"
                        print(success_msg)
                        _append_log(terminal_entries, "system", success_msg)
                        _save_terminal_log(log_path, terminal_entries)
                        break
                else:
                    warn_msg = (
                        "⚠️  PDF fill still running — check calling_filling_logs.json"
                    )
                    print(warn_msg)
                    _append_log(terminal_entries, "system", warn_msg)
                    _save_terminal_log(log_path, terminal_entries)

    except OSError as e:
        print(f"\n❌ Configuration error:\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    run_interactive()
