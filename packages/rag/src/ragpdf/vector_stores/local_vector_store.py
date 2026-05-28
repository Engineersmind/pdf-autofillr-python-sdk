# src/ragpdf/vector_stores/local_vector_store.py
import json
import logging
import os
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


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


class LocalVectorStore(VectorStoreBackend):
    """
    Flat-JSON vector store backed by the local filesystem.
    Perfect for development, testing, and small deployments.

    First-run bootstrap
    -------------------
    On the very first call, if vector_database.json does not exist (or is empty)
    but a source file is present at:

        {data_path}/vectors/source/vector_source.json

    the store automatically generates embeddings for all source vectors using
    the configured embedding backend (RAGPDF_EMBEDDING_BACKEND) and writes
    vector_database.json before returning.

    This means users never need to run a separate init step — the first
    prediction call triggers the embedding automatically.

    For explicit control, use:

        ragpdf init-vectors [--source path] [--backend openai|sentence_transformer]

    Usage:
        store = LocalVectorStore(path="./data/rag")
    """

    def __init__(self, path: str = "./data/rag"):
        self.path = path
        self.db_file = os.path.join(path, "vectors", "vector_database.json")
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)

        # Auto-bootstrap: if DB is missing/empty and source exists, generate embeddings now
        self._maybe_bootstrap(path)

        self.data = self._load()

    # ------------------------------------------------------------------
    # First-run bootstrap
    # ------------------------------------------------------------------

    def _maybe_bootstrap(self, data_path: str) -> None:
        """
        If vector_database.json is missing or empty and a source file exists,
        run the embedding generation pipeline automatically.

        This is a one-time operation — subsequent loads go straight to _load().
        """
        db_path = os.path.join(data_path, "vectors", "vector_database.json")

        # Already have a non-empty DB — nothing to do
        if os.path.exists(db_path):
            try:
                raw = open(db_path, encoding="utf-8").read().strip()
                if raw:
                    db = json.loads(raw)
                    if db.get("vectors"):
                        return
            except Exception:
                pass  # malformed DB — let _load() handle it

        # Try auto-bootstrap
        try:
            from ragpdf.init_vectors import auto_bootstrap

            auto_bootstrap(data_path=data_path, verbose=True)
        except ImportError:
            # init_vectors module not available (shouldn't happen in normal install)
            logger.debug("_maybe_bootstrap: init_vectors module not found — skipping")
        except Exception as e:
            logger.warning(
                "LocalVectorStore._maybe_bootstrap failed: %s — "
                "starting with empty vector DB. "
                "Run 'ragpdf init-vectors' to generate embeddings.",
                e,
            )

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if not os.path.exists(self.db_file):
            logger.info("Vector DB not found — creating empty store.")
            return {
                "metadata": {"total_count": 0, "last_updated": _now()},
                "vectors": [],
            }
        with open(self.db_file, encoding="utf-8") as f:
            data = json.load(f)
        if "metadata" not in data:
            data["metadata"] = {
                "total_count": len(data.get("vectors", [])),
                "last_updated": _now(),
            }
        self._backfill_missing_fields(data["vectors"])
        logger.info(f"Loaded {len(data['vectors'])} vectors from {self.db_file}")
        return data

    def _backfill_missing_fields(self, vectors: list):
        """Add any fields that may be missing from older vector DB versions."""
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

    def save(self) -> None:
        self.data["metadata"]["last_updated"] = _now()
        self.data["metadata"]["total_count"] = len(self.data["vectors"])
        with open(self.db_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def find_similar(
        self,
        query_embedding: list,
        threshold: float = PREDICTION_THRESHOLD,
        top_k: int = TOP_K,
    ) -> dict:
        vectors = self.data["vectors"]
        if not vectors:
            return {
                "matched": False,
                "confidence": 0.0,
                "top_k": [],
                "similarity_margin": 0.0,
            }

        if np.linalg.norm(query_embedding) < 1e-9:
            logger.warning(
                "Zero embedding query rejected — "
                "check RAGPDF_EMBEDDING_BACKEND is not 'noop' in production"
            )
            return {
                "matched": False,
                "confidence": 0.0,
                "top_k": [],
                "similarity_margin": 0.0,
                "best_candidate": None,
            }

        # Guard against vectors with missing embeddings (source-only, not yet embedded)
        embeddable = [
            v
            for v in vectors
            if v.get("embedding")
            and len(v["embedding"]) > 0
            and any(x != 0.0 for x in v["embedding"])
        ]
        if not embeddable:
            logger.warning(
                "No embedded vectors found — run 'ragpdf init-vectors' to generate embeddings"
            )
            return {
                "matched": False,
                "confidence": 0.0,
                "top_k": [],
                "similarity_margin": 0.0,
            }

        embeddings = np.array([v["embedding"] for v in embeddable])
        sims = cosine_similarity([query_embedding], embeddings)[0]
        top_indices = np.argsort(sims)[-top_k:][::-1]

        top_k_results = [
            {
                "field_name": embeddable[i]["field_name"],
                "confidence": float(sims[i]),
                "vector_id": embeddable[i]["vector_id"],
            }
            for i in top_indices
        ]

        best_idx = top_indices[0]
        best_vec = embeddable[best_idx]
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

    # ------------------------------------------------------------------
    # Vector management
    # ------------------------------------------------------------------

    def add_vector(
        self,
        field_name: str,
        context: str,
        section_context: str,
        headers: list,
        embedding: list,
        **metadata,
    ) -> str:
        if not any(x != 0.0 for x in embedding):
            raise ValueError(
                f"Rejected zero embedding for field '{field_name}' — "
                "NoOp embedder must not be used in production"
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
        logger.info(f"Added vector {vector_id}: {field_name}")
        return vector_id

    def update_confidence(
        self, vector_id: str, is_positive: bool, error_info: dict | None = None
    ) -> float | None:
        for vector in self.data["vectors"]:
            if vector["vector_id"] != vector_id:
                continue
            now = _now()
            hist = vector.setdefault("confidence_history", [0.75])
            current = hist[-1]

            if is_positive:
                new_conf = min(current * CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE)
                vector["positive_count"] = vector.get("positive_count", 0) + 1
            else:
                new_conf = max(current * CONFIDENCE_DECAY_RATE, MIN_CONFIDENCE)
                vector["negative_count"] = vector.get("negative_count", 0) + 1
                if error_info:
                    vector.setdefault("error_history", []).append(
                        {
                            "timestamp": now,
                            "pdf_hash": error_info.get("pdf_hash"),
                            "error_type": error_info.get("error_type"),
                            "user_feedback": error_info.get("user_feedback"),
                            "corrected_to": error_info.get("corrected_field_name"),
                            "original_confidence": current,
                        }
                    )
                    self._regenerate_embedding(vector, error_info)

            hist.append(round(new_conf, 6))
            total = vector.get("positive_count", 0) + vector.get("negative_count", 0)
            vector["stability_score"] = (
                round(vector.get("positive_count", 0) / total, 4) if total else 1.0
            )
            vector["avg_confidence"] = round(sum(hist) / len(hist), 6)
            vector["usage_count"] = vector.get("usage_count", 0) + 1
            vector["last_updated"] = now
            vector["last_used"] = now
            logger.info(
                f"Vector {vector_id}: {current:.4f} -> {new_conf:.4f} "
                f"({'pos' if is_positive else 'neg'})"
            )
            return new_conf

        logger.warning(f"Vector {vector_id} not found")
        return None

    def _regenerate_embedding(self, vector: dict, error_info: dict):
        """Regenerate embedding for a vector after a user correction."""
        try:
            from ragpdf.embeddings.factory import EmbeddingFactory

            gen = EmbeddingFactory.create()
            base = gen.create_text_from_field(vector)
            corrected = error_info.get("corrected_field_name", "")
            enriched = f"{base} corrected:{corrected}".strip() if corrected else base
            vector["embedding"] = gen.embed(enriched)
            logger.info(
                f"Regenerated embedding for {vector['vector_id']} -> {corrected}"
            )
        except Exception as e:
            logger.warning(f"Embedding regen failed: {e}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        return len(self.data["vectors"])

    def find_by_name(self, field_name: str) -> str | None:
        for v in self.data["vectors"]:
            if v.get("field_name") == field_name:
                return v["vector_id"]
        return None
