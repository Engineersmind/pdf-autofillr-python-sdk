# src/ragpdf/vector_stores/pinecone_store.py
"""
Pinecone vector store plugin.

Install: pip install ragpdf-sdk[pinecone]

Usage:
    from ragpdf.vector_stores import PineconeStore

    store = PineconeStore(
        api_key="your-pinecone-api-key",
        index_name="ragpdf-vectors",
        namespace="production",
    )
"""

import logging

from ragpdf.config.settings import PREDICTION_THRESHOLD, TOP_K
from ragpdf.vector_stores.base import VectorStoreBackend

logger = logging.getLogger(__name__)


class PineconeStore(VectorStoreBackend):
    """
    Pinecone-backed vector store.
    Vectors are upserted to Pinecone on add_vector() and save().
    Metadata (confidence history, counts) is stored in Pinecone metadata fields.
    """

    def __init__(
        self,
        api_key: str = "",
        index_name: str = "ragpdf-vectors",
        namespace: str = "default",
        dimension: int = 384,
    ):
        try:
            from pinecone import Pinecone
        except ImportError as e:
            raise ImportError("pip install ragpdf-sdk[pinecone]") from e
        from ragpdf.config.settings import (
            PINECONE_API_KEY,
            RAGPDF_PINECONE_INDEX,
            RAGPDF_PINECONE_NAMESPACE,
        )

        pc = Pinecone(api_key=api_key or PINECONE_API_KEY)
        self._index = pc.Index(index_name or RAGPDF_PINECONE_INDEX)
        self._namespace = namespace or RAGPDF_PINECONE_NAMESPACE
        self._dimension = dimension
        self._cache: dict = {}  # local cache: vector_id -> metadata
        logger.info(
            f"PineconeStore initialized: index={index_name}, ns={self._namespace}"
        )

    def find_similar(
        self,
        query_embedding: list,
        threshold: float = PREDICTION_THRESHOLD,
        top_k: int = TOP_K,
    ) -> dict:
        results = self._index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=self._namespace,
            include_metadata=True,
        )
        matches = results.get("matches", [])
        if not matches:
            return {
                "matched": False,
                "confidence": 0.0,
                "top_k": [],
                "similarity_margin": 0.0,
            }

        top_k_r = [
            {
                "field_name": m["metadata"].get("field_name", ""),
                "confidence": m["score"],
                "vector_id": m["id"],
            }
            for m in matches
        ]
        best = matches[0]
        bc = best["score"]
        margin = (
            top_k_r[0]["confidence"] - top_k_r[1]["confidence"]
            if len(top_k_r) >= 2
            else 0.0
        )

        if bc >= threshold:
            meta = best["metadata"]
            return {
                "matched": True,
                "vector_id": best["id"],
                "field_name": meta.get("field_name", ""),
                "confidence": bc,
                "vector_confidence": meta.get("current_confidence", 0.75),
                "positive_count": int(meta.get("positive_count", 0)),
                "negative_count": int(meta.get("negative_count", 0)),
                "usage_count": int(meta.get("usage_count", 0)),
                "stability_score": float(meta.get("stability_score", 1.0)),
                "top_k": top_k_r,
                "similarity_margin": float(margin),
            }
        return {
            "matched": False,
            "confidence": bc,
            "best_candidate": matches[0]["metadata"].get("field_name", ""),
            "top_k": top_k_r,
            "similarity_margin": float(margin),
        }

    def add_vector(
        self,
        field_name: str,
        context: str,
        section_context: str,
        headers: list,
        embedding: list,
        **metadata,
    ) -> str:
        import uuid

        vector_id = f"vec_{uuid.uuid4().hex[:8]}"
        self._index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "field_name": field_name,
                        "context": context,
                        "section_context": section_context,
                        "headers": " ".join(headers),
                        "current_confidence": 0.75,
                        "positive_count": 1,
                        "negative_count": 0,
                        "usage_count": 1,
                        "stability_score": 1.0,
                        **{k: str(v) for k, v in metadata.items()},
                    },
                }
            ],
            namespace=self._namespace,
        )
        logger.info(f"Pinecone: added vector {vector_id} for {field_name}")
        return vector_id

    def update_confidence(
        self, vector_id: str, is_positive: bool, error_info: dict | None = None
    ) -> float | None:
        from ragpdf.config.settings import (
            CONFIDENCE_DECAY_RATE,
            CONFIDENCE_GROWTH_RATE,
            MAX_CONFIDENCE,
            MIN_CONFIDENCE,
        )

        result = self._index.fetch(ids=[vector_id], namespace=self._namespace)
        vectors = result.get("vectors", {})
        if vector_id not in vectors:
            return None
        meta = vectors[vector_id]["metadata"]
        curr = float(meta.get("current_confidence", 0.75))
        if is_positive:
            new_c = min(curr * CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE)
            meta["positive_count"] = int(meta.get("positive_count", 0)) + 1
        else:
            new_c = max(curr * CONFIDENCE_DECAY_RATE, MIN_CONFIDENCE)
            meta["negative_count"] = int(meta.get("negative_count", 0)) + 1
        t = int(meta.get("positive_count", 0)) + int(meta.get("negative_count", 0))
        meta["stability_score"] = (
            round(int(meta.get("positive_count", 0)) / t, 4) if t else 1.0
        )
        meta["current_confidence"] = round(new_c, 6)
        self._index.update(id=vector_id, set_metadata=meta, namespace=self._namespace)
        return new_c

    def save(self) -> None:
        pass  # Pinecone is always-persistent — no explicit save needed

    def count(self) -> int:
        stats = self._index.describe_index_stats()
        ns_stats = stats.get("namespaces", {}).get(self._namespace, {})
        return ns_stats.get("vector_count", 0)

    def find_by_name(self, field_name: str):
        """Query Pinecone by metadata filter to find a vector_id by field_name."""
        try:
            results = self._index.query(
                vector=[0.0] * self._dimension,
                top_k=1,
                namespace=self._namespace,
                include_metadata=True,
                filter={"field_name": {"$eq": field_name}},
            )
            matches = results.get("matches", [])
            return matches[0]["id"] if matches else None
        except Exception as e:
            logger.warning(f"Pinecone find_by_name failed: {e}")
            return None
