# src/ragpdf/embeddings/base.py
from abc import ABC, abstractmethod


class EmbeddingBackend(ABC):
    """
    Abstract embedding backend. Implement this to plug in any embedding model.

    Example:
        class MyEmbedder(EmbeddingBackend):
            def embed(self, text: str) -> list[float]:
                return my_model.encode(text).tolist()

            def embed_batch(self, texts: list[str]) -> list[list[float]]:
                return my_model.encode(texts).tolist()

            def create_text_from_field(self, field_data: dict) -> str:
                parts = [
                    field_data.get("field_name", ""),
                    field_data.get("context", ""),
                    field_data.get("section_context", ""),
                    " ".join(field_data.get("headers", [])),
                ]
                return " ".join(filter(None, parts)).strip()
    """

    @abstractmethod
    def embed(self, text: str) -> list:
        """Generate an embedding vector for a single text."""

    @abstractmethod
    def embed_batch(self, texts: list) -> list:
        """Generate embedding vectors for multiple texts (batch, faster)."""

    def create_text_from_field(self, field_data: dict) -> str:
        """
        Build a single string from field metadata for embedding.
        Including field_name ensures semantically-different fields
        with similar descriptions get distinct embeddings.
        """
        parts = [
            field_data.get("field_name", ""),
            field_data.get("context", ""),
            field_data.get("section_context", ""),
            " ".join(field_data.get("headers", [])),
        ]
        return " ".join(filter(None, parts)).strip()
