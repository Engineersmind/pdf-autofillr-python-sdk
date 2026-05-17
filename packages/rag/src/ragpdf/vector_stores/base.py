# src/ragpdf/vector_stores/base.py
from abc import ABC, abstractmethod
from typing import Optional


class VectorStoreBackend(ABC):
    """
    Abstract vector store backend. Implement this to plug in Pinecone,
    Weaviate, Qdrant, Milvus, Redis, pgvector, or any other store.

    The SDK ships with:
      - LocalVectorStore   (flat JSON on disk — for dev/testing)
      - S3VectorStore      (flat JSON in S3 — production, no extra deps)
      - PineconeStore      (pip install ragpdf-sdk[pinecone])
      - ChromaStore        (pip install ragpdf-sdk[chroma])
      - WeaviateStore      (pip install ragpdf-sdk[weaviate])
    """

    @abstractmethod
    def find_similar(self, query_embedding: list, threshold: float, top_k: int) -> dict:
        """
        Find the most similar vectors to query_embedding.

        Returns:
            If match found above threshold:
                {
                    "matched": True,
                    "vector_id": str,
                    "field_name": str,
                    "confidence": float,       # cosine similarity
                    "vector_confidence": float, # learned confidence
                    "positive_count": int,
                    "negative_count": int,
                    "usage_count": int,
                    "stability_score": float,
                    "top_k": [...],
                    "similarity_margin": float
                }
            If no match:
                {
                    "matched": False,
                    "confidence": float,
                    "best_candidate": str,
                    "top_k": [...],
                    "similarity_margin": float
                }
        """

    @abstractmethod
    def add_vector(self, field_name: str, context: str, section_context: str,
                   headers: list, embedding: list, **metadata) -> str:
        """Add a new vector. Returns vector_id."""

    @abstractmethod
    def update_confidence(self, vector_id: str, is_positive: bool,
                          error_info: Optional[dict] = None) -> Optional[float]:
        """
        Update a vector's learned confidence score.
        is_positive=True  -> multiply by CONFIDENCE_GROWTH_RATE
        is_positive=False -> multiply by CONFIDENCE_DECAY_RATE + log error + regen embedding
        Returns new confidence value.
        """

    @abstractmethod
    def save(self) -> None:
        """Persist any in-memory state."""

    @abstractmethod
    def count(self) -> int:
        """Total number of vectors in the store."""

    def find_by_name(self, field_name: str) -> Optional[str]:
        """
        Find a vector_id by exact field_name match.
        Used by FeedbackPipeline to route errors to the responsible vector
        for Pinecone/Chroma/Weaviate stores.

        Default implementation returns None — override in each backend.
        LocalVectorStore and S3VectorStore override this automatically.
        """
        return None
