# examples/plugin_examples.py
"""
Demonstrates all available plugin combinations.
Each section shows a different configuration.
"""

import os

# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE A: OpenAI Embeddings + S3 Storage + Anthropic Corrector
# pip install ragpdf-sdk[openai-embeddings,s3,anthropic]
# ─────────────────────────────────────────────────────────────────────────────


def example_a_openai_s3_anthropic():
    from ragpdf import RAGPDFClient
    from ragpdf.correctors.anthropic_corrector import AnthropicCorrectorBackend
    from ragpdf.embeddings.openai_embeddings import OpenAIEmbeddingBackend
    from ragpdf.storage.s3_storage import S3Storage
    from ragpdf.vector_stores.s3_vector_store import S3VectorStore

    client = RAGPDFClient(
        storage=S3Storage(bucket="my-ragpdf-data"),
        vector_store=S3VectorStore(bucket="my-ragpdf-data"),
        embedding_backend=OpenAIEmbeddingBackend(
            api_key=os.environ["OPENAI_API_KEY"],
            model="text-embedding-3-small",  # 1536-dim, very cost-effective
        ),
        corrector=AnthropicCorrectorBackend(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model="claude-sonnet-4-20250514",
        ),
    )
    return client


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE B: SentenceTransformers + Pinecone + OpenAI Corrector
# pip install ragpdf-sdk[transformers,pinecone,openai-corrector]
# ─────────────────────────────────────────────────────────────────────────────


def example_b_st_pinecone_openai():
    from ragpdf import RAGPDFClient
    from ragpdf.correctors.openai_corrector import OpenAICorrectorBackend
    from ragpdf.embeddings.sentence_transformer import SentenceTransformerBackend
    from ragpdf.storage.s3_storage import S3Storage
    from ragpdf.vector_stores.pinecone_store import PineconeStore

    client = RAGPDFClient(
        storage=S3Storage(bucket="my-ragpdf-data"),
        vector_store=PineconeStore(
            api_key=os.environ["PINECONE_API_KEY"],
            index_name="ragpdf-vectors",
            namespace="production",
        ),
        embedding_backend=SentenceTransformerBackend(
            "all-mpnet-base-v2"  # 768-dim, higher quality than MiniLM
        ),
        corrector=OpenAICorrectorBackend(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4-turbo-preview",
        ),
    )
    return client


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE C: Local dev — ChromaDB + SentenceTransformers + NoOp corrector
# pip install ragpdf-sdk[transformers,chroma]
# ─────────────────────────────────────────────────────────────────────────────


def example_c_local_chroma():
    from ragpdf import LocalStorage, RAGPDFClient
    from ragpdf.correctors.noop_corrector import NoOpCorrectorBackend
    from ragpdf.embeddings.sentence_transformer import SentenceTransformerBackend
    from ragpdf.vector_stores.chroma_store import ChromaStore

    client = RAGPDFClient(
        storage=LocalStorage(data_path="./data/rag"),
        vector_store=ChromaStore(
            path="./chroma_data",
            collection="ragpdf_vectors",  # fixed: was collection_name=
        ),
        embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
        corrector=NoOpCorrectorBackend(),
    )
    return client
    return client


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE D: Custom embedding backend (bring your own model)
# ─────────────────────────────────────────────────────────────────────────────


def example_d_custom_embedding():
    from ragpdf import LocalStorage, RAGPDFClient
    from ragpdf.correctors import NoOpCorrectorBackend
    from ragpdf.embeddings.base import EmbeddingBackend
    from ragpdf.vector_stores import LocalVectorStore

    class MyCustomEmbedder(EmbeddingBackend):
        """Plug in any model — HuggingFace, Cohere, custom fine-tuned, etc."""

        def __init__(self):
            # Example: loading a HuggingFace model directly
            # from transformers import AutoTokenizer, AutoModel
            # self.tokenizer = AutoTokenizer.from_pretrained("your-org/your-model")
            # self.model = AutoModel.from_pretrained("your-org/your-model")
            pass

        def embed(self, text: str) -> list[float]:
            # Replace with your actual inference code
            return [0.1] * 768

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            return [[0.1] * 768 for _ in texts]

        @property
        def dimension(self) -> int:
            return 768

    client = RAGPDFClient(
        storage=LocalStorage(),
        vector_store=LocalVectorStore(),
        embedding_backend=MyCustomEmbedder(),
        corrector=NoOpCorrectorBackend(),
    )
    return client


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE E: Custom corrector backend (bring your own LLM)
# ─────────────────────────────────────────────────────────────────────────────


def example_e_custom_corrector():
    from ragpdf import LocalStorage, RAGPDFClient
    from ragpdf.correctors.base import FieldCorrectorBackend
    from ragpdf.embeddings import SentenceTransformerBackend
    from ragpdf.vector_stores import LocalVectorStore

    class LlamaLocalCorrector(FieldCorrectorBackend):
        """Example: call a local Llama server via ollama or llama.cpp."""

        def generate_corrected_field_name(self, error_data: dict) -> dict:
            import json

            import requests

            prompt = (
                f"Convert this wrong PDF field name to snake_case: "
                f"{error_data.get('field_name')}. "
                f"Feedback: {error_data.get('feedback')}. "
                f'Reply with JSON only: {{"corrected_field_name": "...", "confidence": 0.9, "reasoning": "..."}}'
            )
            try:
                resp = requests.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "llama3.2", "prompt": prompt, "stream": False},
                    timeout=30,
                )
                data = json.loads(resp.json()["response"])
                return {
                    "corrected_field_name": data["corrected_field_name"],
                    "confidence": data.get("confidence", 0.8),
                    "reasoning": data.get("reasoning", ""),
                }
            except Exception as e:
                fallback = (
                    error_data.get("field_name", "unknown").lower().replace(" ", "_")
                )
                return {
                    "corrected_field_name": fallback,
                    "confidence": 0.5,
                    "reasoning": str(e),
                }

    client = RAGPDFClient(
        storage=LocalStorage(),
        vector_store=LocalVectorStore(),
        embedding_backend=SentenceTransformerBackend(),
        corrector=LlamaLocalCorrector(),
    )
    return client


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE F: Custom storage backend (PostgreSQL)
# ─────────────────────────────────────────────────────────────────────────────


def example_f_postgres_storage():
    import json
    from typing import Any

    from ragpdf.storage.base import StorageBackend

    class PostgresStorage(StorageBackend):
        """Example Postgres-backed storage using psycopg2."""

        def __init__(self, dsn: str):
            import psycopg2

            self.conn = psycopg2.connect(dsn)
            self._ensure_table()

        def _ensure_table(self):
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ragpdf_store (
                        key TEXT PRIMARY KEY,
                        value JSONB,
                        updated_at TIMESTAMPTZ DEFAULT now()
                    )
                """)
            self.conn.commit()

        def save_json(self, key: str, data: Any) -> None:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ragpdf_store(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=%s, updated_at=now()",
                    (key, json.dumps(data), json.dumps(data)),
                )
            self.conn.commit()

        def load_json(self, key: str) -> Any | None:
            with self.conn.cursor() as cur:
                cur.execute("SELECT value FROM ragpdf_store WHERE key = %s", (key,))
                row = cur.fetchone()
            return row[0] if row else None

        def append_jsonl(self, key: str, record: Any) -> None:
            existing = self.load_json(key) or []
            existing.append(record)
            self.save_json(key, existing)

        def load_jsonl(self, key: str) -> list[Any]:
            return self.load_json(key) or []

        def copy_blob(self, source_uri: str, dest_key: str) -> bool:
            return False  # not supported in this example

    # client = RAGPDFClient(
    #     storage=PostgresStorage(dsn="postgresql://user:pass@localhost/ragpdf"),
    #     vector_store=LocalVectorStore(),
    #     embedding_backend=SentenceTransformerBackend(),
    #     corrector=NoOpCorrectorBackend(),
    # )
    print("PostgresStorage example defined (not connected in this example)")


if __name__ == "__main__":
    print(
        "Plugin examples loaded. Each function demonstrates a different configuration."
    )
    print("Uncomment and run the one that matches your setup.")
