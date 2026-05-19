# src/ragpdf/config/validator.py
"""
Validates env/config at startup and raises clear errors
telling the user exactly what to set and how to install it.
"""
import os


class ConfigValidationError(Exception):
    pass


def validate():
    """
    Call this once at client init. Checks that all required env vars
    are set for the chosen backends, and that the right packages are installed.
    Raises ConfigValidationError with a clear actionable message.
    """
    errors = []

    storage         = os.getenv("RAGPDF_STORAGE", "local")
    embedding       = os.getenv("RAGPDF_EMBEDDING_BACKEND", "sentence_transformer")
    vector_store    = os.getenv("RAGPDF_VECTOR_STORE", "local")
    corrector       = os.getenv("RAGPDF_CORRECTOR_BACKEND", "noop")

    # ── Storage checks ────────────────────────────────────────
    if storage == "s3":
        if not os.getenv("RAGPDF_S3_BUCKET"):
            errors.append(
                "[S3 Storage] RAGPDF_S3_BUCKET is not set.\n"
                "  Fix: add RAGPDF_S3_BUCKET=your-bucket-name to your .env\n"
                "  Install: pip install pdf-autofillr-rag[s3]"
            )
        try:
            import boto3
        except ImportError:
            errors.append(
                "[S3 Storage] boto3 is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[s3]"
            )

    # ── Embedding checks ──────────────────────────────────────
    if embedding == "sentence_transformer":
        try:
            import sentence_transformers
        except ImportError:
            errors.append(
                "[Embeddings] sentence-transformers is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[transformers]\n"
                "  Or switch to: RAGPDF_EMBEDDING_BACKEND=noop (for testing)"
            )

    if embedding == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            errors.append(
                "[Embeddings] OPENAI_API_KEY is not set.\n"
                "  Fix: add OPENAI_API_KEY=sk-... to your .env"
            )
        try:
            import openai
        except ImportError:
            errors.append(
                "[Embeddings] openai package is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[openai]"
            )

    # ── Vector store checks ───────────────────────────────────
    if vector_store == "s3":
        if not os.getenv("RAGPDF_S3_BUCKET"):
            errors.append(
                "[Vector Store] RAGPDF_S3_BUCKET is not set (required for RAGPDF_VECTOR_STORE=s3).\n"
                "  Fix: add RAGPDF_S3_BUCKET=your-bucket-name to your .env"
            )

    if vector_store == "pinecone":
        if not os.getenv("PINECONE_API_KEY"):
            errors.append(
                "[Vector Store] PINECONE_API_KEY is not set.\n"
                "  Fix: add PINECONE_API_KEY=your-key to your .env"
            )
        if not os.getenv("RAGPDF_PINECONE_INDEX"):
            errors.append(
                "[Vector Store] RAGPDF_PINECONE_INDEX is not set.\n"
                "  Fix: add RAGPDF_PINECONE_INDEX=ragpdf-vectors to your .env"
            )
        try:
            import pinecone
        except ImportError:
            errors.append(
                "[Vector Store] pinecone-client is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[pinecone]"
            )

    if vector_store == "chroma":
        try:
            import chromadb
        except ImportError:
            errors.append(
                "[Vector Store] chromadb is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[chroma]"
            )

    if vector_store == "weaviate":
        if not os.getenv("RAGPDF_WEAVIATE_URL"):
            errors.append(
                "[Vector Store] RAGPDF_WEAVIATE_URL is not set.\n"
                "  Fix: add RAGPDF_WEAVIATE_URL=http://localhost:8080 to your .env"
            )
        try:
            import weaviate
        except ImportError:
            errors.append(
                "[Vector Store] weaviate-client is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[weaviate]"
            )

    # ── Corrector checks ──────────────────────────────────────
    if corrector == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            errors.append(
                "[Corrector] OPENAI_API_KEY is not set (required for RAGPDF_CORRECTOR_BACKEND=openai).\n"
                "  Fix: add OPENAI_API_KEY=sk-... to your .env"
            )
        try:
            import openai
        except ImportError:
            errors.append(
                "[Corrector] openai package is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[openai]"
            )

    if corrector == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            errors.append(
                "[Corrector] ANTHROPIC_API_KEY is not set.\n"
                "  Fix: add ANTHROPIC_API_KEY=sk-ant-... to your .env"
            )
        try:
            import anthropic
        except ImportError:
            errors.append(
                "[Corrector] anthropic package is not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[anthropic]"
            )

    # ── Server checks (only when running server) ──────────────
    server_mode = os.getenv("RAGPDF_SERVER_MODE", "false").lower() == "true"
    if server_mode:
        try:
            import fastapi
            import uvicorn
        except ImportError:
            errors.append(
                "[Server] fastapi/uvicorn are not installed.\n"
                "  Fix: pip install pdf-autofillr-rag[server]"
            )

    if errors:
        msg = "\n\n".join(errors)
        raise ConfigValidationError(
            f"\n\n{'='*60}\n"
            f"pdf-autofillr-rag — Configuration Error\n"
            f"{'='*60}\n\n"
            f"{msg}\n\n"
            f"{'='*60}\n"
            f"Full docs: https://docs.ragpdf.io\n"
            f"{'='*60}\n"
        )