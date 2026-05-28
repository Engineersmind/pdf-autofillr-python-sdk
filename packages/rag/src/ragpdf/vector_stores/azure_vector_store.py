"""
Azure Blob flat-JSON vector store.
Identical logic to LocalVectorStore but persists to Azure Blob Storage.

Install: pip install ragpdf-sdk[azure]
"""

import logging
from datetime import datetime

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ragpdf.config.settings import (
    CONFIDENCE_DECAY_RATE,
    CONFIDENCE_GROWTH_RATE,
    MAX_CONFIDENCE,
    MIN_CONFIDENCE,
    PREDICTION_THRESHOLD,
    TOP_K,
)
from ragpdf.utils.helpers import generate_vector_id
from ragpdf.vector_stores.base import VectorStoreBackend

logger = logging.getLogger(__name__)
_DB_KEY = "vectors/vector_database.json"


def _now():
    return datetime.utcnow().isoformat() + "Z"


class AzureVectorStore(VectorStoreBackend):
    def __init__(
        self,
        account: str = "",
        container: str = "",
        conn_str: str = "",
        prefix: str = "",
    ):
        from ragpdf.storage.azure_storage import AzureStorage

        self._storage = AzureStorage(
            account=account, container=container, conn_str=conn_str, prefix=prefix
        )
        self.data = self._load()

    def _load(self):
        data = self._storage.load_json(_DB_KEY)
        if data is None:
            return {
                "metadata": {"total_count": 0, "last_updated": _now()},
                "vectors": [],
            }
        if "metadata" not in data:
            data["metadata"] = {
                "total_count": len(data.get("vectors", [])),
                "last_updated": _now(),
            }
        self._backfill(data["vectors"])
        logger.info(f"AzureVectorStore: loaded {len(data['vectors'])} vectors")
        return data

    def _backfill(self, vectors):
        now = _now()
        for v in vectors:
            v.setdefault("confidence_history", [v.get("confidence", 0.75)])
            v.setdefault("positive_count", 0)
            v.setdefault("negative_count", 0)
            v.setdefault("usage_count", 0)
            v.setdefault("stability_score", 1.0)
            v.setdefault("avg_confidence", v["confidence_history"][-1])
            v.setdefault("error_history", [])
            v.setdefault("created_at", now)
            v.setdefault("last_updated", now)
            v.setdefault("last_used", now)

    def save(self):
        self.data["metadata"]["last_updated"] = _now()
        self.data["metadata"]["total_count"] = len(self.data["vectors"])
        self._storage.save_json(_DB_KEY, self.data)

    def find_similar(
        self, query_embedding, threshold=PREDICTION_THRESHOLD, top_k=TOP_K
    ):
        vectors = self.data["vectors"]
        if not vectors:
            return {
                "matched": False,
                "confidence": 0.0,
                "top_k": [],
                "similarity_margin": 0.0,
            }
        if np.linalg.norm(query_embedding) < 1e-9:
            logger.warning("Zero embedding query rejected — returning no match")
            return {
                "matched": False,
                "confidence": 0.0,
                "top_k": [],
                "similarity_margin": 0.0,
                "best_candidate": None,
            }
        embeddings = np.array([v["embedding"] for v in vectors])
        sims = cosine_similarity([query_embedding], embeddings)[0]
        top_indices = np.argsort(sims)[-top_k:][::-1]
        top_k_results = [
            {
                "field_name": vectors[i]["field_name"],
                "confidence": float(sims[i]),
                "vector_id": vectors[i]["vector_id"],
            }
            for i in top_indices
        ]
        best_idx = top_indices[0]
        best_vec = vectors[best_idx]
        best_conf = float(sims[best_idx])
        margin = (
            top_k_results[0]["confidence"] - top_k_results[1]["confidence"]
            if len(top_k_results) >= 2
            else 0.0
        )
        if best_conf >= threshold:
            best_vec["usage_count"] = best_vec.get("usage_count", 0) + 1
            best_vec["last_used"] = _now()
            return {
                "matched": True,
                "vector_id": best_vec["vector_id"],
                "field_name": best_vec["field_name"],
                "confidence": best_conf,
                "vector_confidence": best_vec.get("confidence_history", [0.75])[-1],
                "positive_count": best_vec.get("positive_count", 0),
                "negative_count": best_vec.get("negative_count", 0),
                "usage_count": best_vec.get("usage_count", 0),
                "stability_score": best_vec.get("stability_score", 1.0),
                "top_k": top_k_results,
                "similarity_margin": float(margin),
            }
        return {
            "matched": False,
            "confidence": best_conf,
            "best_candidate": best_vec["field_name"],
            "top_k": top_k_results,
            "similarity_margin": float(margin),
        }

    def add_vector(
        self, field_name, context, section_context, headers, embedding, **metadata
    ):
        if not any(x != 0.0 for x in embedding):
            raise ValueError(
                f"Rejected zero embedding for field '{field_name}' — NoOp embedder must not be used in production"
            )
        vector_id = generate_vector_id(self.data["vectors"])
        now = _now()
        self.data["vectors"].append(
            {
                "vector_id": vector_id,
                "field_name": field_name,
                "context": context,
                "section_context": section_context,
                "headers": headers,
                "embedding": embedding,
                "confidence_history": [0.75],
                "positive_count": 1,
                "negative_count": 0,
                "usage_count": 1,
                "stability_score": 1.0,
                "avg_confidence": 0.75,
                "error_history": [],
                "created_at": now,
                "last_updated": now,
                "last_used": now,
                **metadata,
            }
        )
        return vector_id

    def update_confidence(self, vector_id, is_positive, error_info=None):
        for v in self.data["vectors"]:
            if v["vector_id"] != vector_id:
                continue
            hist = v.setdefault("confidence_history", [0.75])
            current = hist[-1]
            now = _now()
            if is_positive:
                new_conf = min(current * CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE)
                v["positive_count"] = v.get("positive_count", 0) + 1
            else:
                new_conf = max(current * CONFIDENCE_DECAY_RATE, MIN_CONFIDENCE)
                v["negative_count"] = v.get("negative_count", 0) + 1
                if error_info:
                    v.setdefault("error_history", []).append(
                        {
                            "timestamp": now,
                            "pdf_hash": error_info.get("pdf_hash"),
                            "error_type": error_info.get("error_type"),
                            "user_feedback": error_info.get("user_feedback"),
                            "corrected_to": error_info.get("corrected_field_name"),
                            "original_confidence": current,
                        }
                    )
            hist.append(round(new_conf, 6))
            total = v.get("positive_count", 0) + v.get("negative_count", 0)
            v["stability_score"] = (
                round(v.get("positive_count", 0) / total, 4) if total else 1.0
            )
            v["avg_confidence"] = round(sum(hist) / len(hist), 6)
            v["usage_count"] = v.get("usage_count", 0) + 1
            v["last_updated"] = now
            v["last_used"] = now
            return new_conf
        return None

    def count(self):
        return len(self.data["vectors"])

    def find_by_name(self, field_name):
        for v in self.data["vectors"]:
            if v.get("field_name") == field_name:
                return v["vector_id"]
        return None
