# src/ragpdf/vector_stores/chroma_store.py
"""
ChromaDB vector store plugin.

Install: pip install ragpdf-sdk[chroma]

Usage:
    from ragpdf.vector_stores import ChromaStore

    store = ChromaStore(
        path="./chroma_data",           # local persistent storage
        collection="ragpdf_vectors",
    )

    # Or in-memory (for testing):
    store = ChromaStore(in_memory=True)
"""
import logging
from typing import Optional

from ragpdf.vector_stores.base import VectorStoreBackend
from ragpdf.config.settings import PREDICTION_THRESHOLD, TOP_K

logger = logging.getLogger(__name__)


class ChromaStore(VectorStoreBackend):
    """
    ChromaDB-backed vector store.
    Great for local/embedded deployments — no external service needed.
    Supports persistent disk storage or in-memory mode.
    """

    def __init__(self, path: str = "./chroma_data",
                 collection: str = "ragpdf_vectors",
                 in_memory: bool = False):
        try:
            import chromadb
        except ImportError:
            raise ImportError("pip install ragpdf-sdk[chroma]")
        from ragpdf.config.settings import RAGPDF_CHROMA_PATH, RAGPDF_CHROMA_COLLECTION
        if in_memory:
            client = chromadb.EphemeralClient()
        else:
            client = chromadb.PersistentClient(path=path or RAGPDF_CHROMA_PATH)
        self._col = client.get_or_create_collection(
            name=collection or RAGPDF_CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
        self._meta_cache: dict = {}
        logger.info(f"ChromaStore initialized: {self._col.name} ({self._col.count()} vectors)")

    def find_similar(self, query_embedding: list,
                     threshold: float = PREDICTION_THRESHOLD,
                     top_k: int = TOP_K) -> dict:
        if self._col.count() == 0:
            return {"matched": False, "confidence": 0.0, "top_k": [], "similarity_margin": 0.0}
        k = min(top_k, self._col.count())
        results = self._col.query(query_embeddings=[query_embedding], n_results=k, include=["metadatas", "distances"])
        ids = results["ids"][0]; dists = results["distances"][0]; metas = results["metadatas"][0]
        # Chroma cosine distance = 1 - similarity
        sims = [1.0 - d for d in dists]
        top_k_r = [{"field_name": metas[i].get("field_name", ""), "confidence": sims[i], "vector_id": ids[i]}
                   for i in range(len(ids))]
        bc = sims[0]; best_meta = metas[0]; best_id = ids[0]
        margin = sims[0] - sims[1] if len(sims) >= 2 else 0.0
        if bc >= threshold:
            return {"matched": True, "vector_id": best_id,
                    "field_name": best_meta.get("field_name", ""),
                    "confidence": bc,
                    "vector_confidence": float(best_meta.get("current_confidence", 0.75)),
                    "positive_count": int(best_meta.get("positive_count", 0)),
                    "negative_count": int(best_meta.get("negative_count", 0)),
                    "usage_count": int(best_meta.get("usage_count", 0)),
                    "stability_score": float(best_meta.get("stability_score", 1.0)),
                    "top_k": top_k_r, "similarity_margin": float(margin)}
        return {"matched": False, "confidence": bc, "best_candidate": best_meta.get("field_name", ""),
                "top_k": top_k_r, "similarity_margin": float(margin)}

    def add_vector(self, field_name: str, context: str, section_context: str,
                   headers: list, embedding: list, **metadata) -> str:
        import uuid
        vid = f"vec_{uuid.uuid4().hex[:8]}"
        self._col.upsert(
            ids=[vid], embeddings=[embedding],
            metadatas=[{"field_name": field_name, "context": context,
                        "section_context": section_context,
                        "headers": " ".join(headers),
                        "current_confidence": 0.75,
                        "positive_count": 1, "negative_count": 0,
                        "usage_count": 1, "stability_score": 1.0,
                        **{k: str(v) for k, v in metadata.items()}}]
        )
        return vid

    def update_confidence(self, vector_id: str, is_positive: bool,
                          error_info: Optional[dict] = None) -> Optional[float]:
        from ragpdf.config.settings import CONFIDENCE_DECAY_RATE, CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE, MIN_CONFIDENCE
        res = self._col.get(ids=[vector_id], include=["metadatas"])
        if not res["ids"]:
            return None
        meta = dict(res["metadatas"][0])
        curr = float(meta.get("current_confidence", 0.75))
        if is_positive:
            new_c = min(curr * CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE)
            meta["positive_count"] = int(meta.get("positive_count", 0)) + 1
        else:
            new_c = max(curr * CONFIDENCE_DECAY_RATE, MIN_CONFIDENCE)
            meta["negative_count"] = int(meta.get("negative_count", 0)) + 1
        t = int(meta.get("positive_count", 0)) + int(meta.get("negative_count", 0))
        meta["stability_score"] = round(int(meta.get("positive_count", 0)) / t, 4) if t else 1.0
        meta["current_confidence"] = round(new_c, 6)
        self._col.update(ids=[vector_id], metadatas=[meta])
        return new_c

    def save(self) -> None:
        pass  # ChromaDB persists automatically

    def count(self) -> int:
        return self._col.count()

    def find_by_name(self, field_name: str):
        """Query Chroma by metadata filter to find a vector_id by field_name."""
        try:
            results = self._col.get(where={"field_name": field_name}, limit=1)
            ids = results.get("ids", [])
            return ids[0] if ids else None
        except Exception as e:
            logger.warning(f"ChromaStore find_by_name failed: {e}")
            return None
