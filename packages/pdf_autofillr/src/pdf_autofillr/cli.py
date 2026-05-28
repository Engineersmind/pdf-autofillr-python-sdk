"""
pdf-autofillr CLI — the one command to rule them all.

    pdf-autofillr setup    write .env.example, configs/, data/ for your combo
    pdf-autofillr status   check what is installed and configured
    pdf-autofillr check    alias for status
    pdf-autofillr chatbot  start the chatbot FastAPI server
    pdf-autofillr doc-upload  start the doc_upload FastAPI server
    pdf-autofillr mapper   start the mapper FastAPI server
    pdf-autofillr rag      start the RAG FastAPI server
    pdf-autofillr help     show this message
"""

from __future__ import annotations

import sys


def _start_chatbot():
    try:
        from chatbot.entrypoints.server import main

        main()
    except ImportError:
        print("❌  pdf-autofillr-chatbot is not installed.")
        print("    pip install pdf-autofillr[chatbot]")
        sys.exit(1)


def _start_doc_upload():
    try:
        from pdf_autofillr_doc_upload.entrypoints.server import main

        main()
    except ImportError:
        print("❌  pdf-autofillr-doc-upload is not installed.")
        print("    pip install pdf-autofillr[doc-upload]")
        sys.exit(1)


def _start_mapper():
    try:
        from pdf_autofillr_mapper.entrypoints.server import main

        main()
    except ImportError:
        print("❌  pdf-autofillr-mapper is not installed.")
        print("    pip install pdf-autofillr[mapper]")
        sys.exit(1)


def _start_rag():
    try:
        from ragpdf.entrypoints.fastapi_app import main

        main()
    except ImportError:
        print("❌  pdf-autofillr-rag is not installed.")
        print("    pip install pdf-autofillr[rag]")
        sys.exit(1)


def _show_help():
    print(__doc__)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("help", "--help", "-h"):
        _show_help()
        return

    cmd = args[0].lower()

    if cmd == "setup":
        from pdf_autofillr.setup import run_setup

        dest = args[1] if len(args) > 1 else "."
        run_setup(dest)

    elif cmd in ("status", "check"):
        from pdf_autofillr.status import run_status

        dest = args[1] if len(args) > 1 else "."
        run_status(dest)

    elif cmd == "chatbot":
        _start_chatbot()

    elif cmd in ("doc-upload", "doc_upload", "docupload"):
        _start_doc_upload()

    elif cmd == "mapper":
        _start_mapper()

    elif cmd == "rag":
        _start_rag()

    else:
        print(f"❌  Unknown command: {cmd!r}")
        print("    Run: pdf-autofillr help")
        sys.exit(1)


if __name__ == "__main__":
    main()
