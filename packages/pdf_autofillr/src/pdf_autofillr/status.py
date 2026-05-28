"""
pdf-autofillr status — checks what is installed and configured.

    pdf-autofillr status
"""

from __future__ import annotations

import os
from pathlib import Path


def _installed(pkg: str) -> tuple[bool, str]:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "?")
        return True, ver
    except ImportError:
        return False, ""


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _check(cond: bool, ok: str, fail: str) -> str:
    return f"✅  {ok}" if cond else f"✗   {fail}"


def run_status(dest_str: str = ".") -> None:
    dest = Path(dest_str).resolve()

    print("\n" + "=" * 64)
    print("  pdf-autofillr status")
    print("=" * 64)

    # ── Modules ──────────────────────────────────────────────────
    print("\nModules")
    print("-" * 64)
    modules = [
        ("chatbot", "chatbot", "pdf-autofillr-chatbot"),
        ("pdf_autofillr_doc_upload", "doc_upload", "pdf-autofillr-doc-upload"),
        ("pdf_autofillr_mapper", "mapper", "pdf-autofillr-mapper"),
        ("ragpdf", "rag", "pdf-autofillr-rag"),
    ]
    installed_combo: set[str] = set()
    for pkg, label, install_name in modules:
        ok, ver = _installed(pkg)
        if ok:
            installed_combo.add(label)
            print(f"  ✅  {label:<12} v{ver}")
        else:
            print(f"  ✗   {label:<12} not installed  ->  pip install {install_name}")

    if not installed_combo:
        print("\n  No modules installed. Run: pip install pdf-autofillr[all]")
        return

    # ── Critical files ────────────────────────────────────────────
    print("\nFiles")
    print("-" * 64)

    files_to_check = [
        (dest / "configs" / "form_keys.json", "configs/form_keys.json"),
        (dest / "configs" / "mapper_config.ini", "configs/mapper_config.ini"),
        (dest / ".env", ".env"),
        (dest / ".env.example", ".env.example"),
    ]
    if "chatbot" in installed_combo or "doc_upload" in installed_combo:
        files_to_check.append(
            (dest / "data" / "input" / "blank_form.pdf", "data/input/blank_form.pdf")
        )
    if "rag" in installed_combo:
        files_to_check.append(
            (
                dest / "data" / "rag" / "vectors" / "vector_database.json",
                "data/rag/vectors/vector_database.json",
            )
        )

    all_files_ok = True
    for path, label in files_to_check:
        exists = path.exists()
        if not exists:
            all_files_ok = False
        note = ""
        if exists and path.suffix == ".json":
            try:
                import json

                data = json.loads(path.read_text())
                if isinstance(data, dict) and label == "configs/form_keys.json":
                    note = f"  ({len(data)} top-level keys)"
                elif isinstance(data, dict) and "vectors" in data:
                    n = len(data.get("vectors", []))
                    note = f"  ({n} vectors{'  — will grow on use' if n == 0 else ''})"
            except Exception:
                pass
        print(f"  {'✅' if exists else '✗ '} {label}{note}")

    # ── Env vars ──────────────────────────────────────────────────
    print("\nEnv configuration")
    print("-" * 64)

    warnings = []

    if "chatbot" in installed_combo:
        model = _env("CHATBOT_LLM_MODEL", "openai/gpt-4o-mini")
        storage = _env("chatbot_STORAGE", "local")
        filler = _env("chatbot_PDF_FILLER", "none")
        pdf_path = _env("chatbot_PDF_PATH", "")
        print(f"  chatbot   LLM: {model}   storage: {storage}   pdf_filler: {filler}")
        if filler != "none" and not pdf_path:
            warnings.append("chatbot_PDF_FILLER is set but chatbot_PDF_PATH is empty")
        if filler != "none" and pdf_path and not Path(pdf_path).exists():
            warnings.append(f"chatbot_PDF_PATH set but file not found: {pdf_path}")

    if "doc_upload" in installed_combo:
        model = _env("DOC_UPLOAD_LLM_MODEL", "openai/gpt-4.1-mini")
        storage = _env("DOC_UPLOAD_STORAGE", "local")
        filler = _env("DOC_UPLOAD_PDF_FILLER", "none")
        pdf_path = _env("DOC_UPLOAD_PDF_PATH", "")
        print(f"  doc_upload  LLM: {model}   storage: {storage}   pdf_filler: {filler}")
        if filler != "none" and not pdf_path:
            warnings.append(
                "DOC_UPLOAD_PDF_FILLER is set but DOC_UPLOAD_PDF_PATH is empty"
            )

    if "mapper" in installed_combo:
        mapper_url = _env("MAPPER_API_URL", "")
        rag_enabled_str = _env("RAG_ENABLED", "false")
        rag_mode = _env("RAG_MODE", "inprocess")
        mode_str = "inprocess" if not mapper_url else f"http -> {mapper_url}"
        print(f"  mapper    connection: {mode_str}")
        if rag_enabled_str.lower() == "true":
            print(f"  mapper->rag  enabled  mode: {rag_mode}")
        else:
            if "rag" in installed_combo:
                warnings.append(
                    "rag is installed but RAG_ENABLED=false — set RAG_ENABLED=true in .env to activate"
                )

    if "rag" in installed_combo:
        storage = _env("RAGPDF_STORAGE", "local")
        embed = _env("RAGPDF_EMBEDDING_BACKEND", "sentence_transformer")
        vstore = _env("RAGPDF_VECTOR_STORE", "local")
        corrector = _env("RAGPDF_CORRECTOR_BACKEND", "noop")
        print(
            f"  rag       storage: {storage}   embeddings: {embed}   vectors: {vstore}   corrector: {corrector}"
        )

    # ── Connections ───────────────────────────────────────────────
    print("\nConnections")
    print("-" * 64)
    mapper_url = _env("MAPPER_API_URL", "")
    if "chatbot" in installed_combo and "mapper" in installed_combo:
        mode = "inprocess" if not mapper_url else f"http -> {mapper_url}"
        print(f"  chatbot -> mapper   {mode}")
    if "doc_upload" in installed_combo and "mapper" in installed_combo:
        mode = "inprocess" if not mapper_url else f"http -> {mapper_url}"
        print(f"  doc_upload -> mapper   {mode}")
    if "mapper" in installed_combo and "rag" in installed_combo:
        rag_enabled_bool: bool = _env("RAG_ENABLED", "false").lower() == "true"
        rag_mode = _env("RAG_MODE", "inprocess")
        status = (
            f"ENABLED ({rag_mode})"
            if rag_enabled_bool
            else "DISABLED (set RAG_ENABLED=true)"
        )
        print(f"  mapper -> rag   {status}")

    # ── Warnings ──────────────────────────────────────────────────
    if warnings:
        print("\n⚠  Warnings")
        print("-" * 64)
        for w in warnings:
            print(f"  ⚠  {w}")

    if all_files_ok and not warnings:
        print("\n✅  Everything looks good — you're ready to run!\n")
    else:
        print("\n   Fix the items above, then run: pdf-autofillr status\n")
        print("   Run pdf-autofillr setup to create missing files.\n")
