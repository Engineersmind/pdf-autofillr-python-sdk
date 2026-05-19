# src/ragpdf/vector_stores/s3_vector_store.py
"""
S3-backed flat-JSON vector store.
Identical logic to LocalVectorStore but persists to your S3 bucket.

Usage:
    store = S3VectorStore(bucket="my-ragpdf-bucket", region="us-east-1")
"""
import logging
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ragpdf.vector_stores.base import VectorStoreBackend
from ragpdf.utils.helpers import generate_vector_id
from ragpdf.config.settings import (
    PREDICTION_THRESHOLD, TOP_K,
    CONFIDENCE_DECAY_RATE, CONFIDENCE_GROWTH_RATE,
    MAX_CONFIDENCE, MIN_CONFIDENCE,
)

logger = logging.getLogger(__name__)
_DB_KEY = "vectors/vector_database.json"


def _now(): return datetime.utcnow().isoformat() + "Z"


class S3VectorStore(VectorStoreBackend):
    def __init__(self, bucket: str, region: str = "us-east-1", prefix: str = ""):
        try:
            import boto3
            from botocore.exceptions import ClientError
            self._ClientError = ClientError
        except ImportError:
            raise ImportError("pip install ragpdf-sdk[s3]")
        self._s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.data = self._load()

    def _key(self, k): return f"{self.prefix}{k}"

    def _load(self):
        import json
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(_DB_KEY))
            data = json.loads(obj["Body"].read().decode("utf-8"))
            if "metadata" not in data:
                data["metadata"] = {"total_count": len(data.get("vectors", [])), "last_updated": _now()}
            self._backfill(data["vectors"])
            logger.info(f"Loaded {len(data['vectors'])} vectors from S3")
            return data
        except self._ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return {"metadata": {"total_count": 0, "last_updated": _now()}, "vectors": []}
            raise

    def _backfill(self, vectors):
        now = _now()
        for v in vectors:
            v.setdefault("confidence_history", [v.get("confidence", 0.75)])
            v.setdefault("positive_count", 0); v.setdefault("negative_count", 0)
            v.setdefault("usage_count", 0); v.setdefault("stability_score", 1.0)
            v.setdefault("avg_confidence", v["confidence_history"][-1])
            v.setdefault("error_history", [])
            v.setdefault("created_at", now); v.setdefault("last_updated", now); v.setdefault("last_used", now)

    def save(self):
        import json
        self.data["metadata"]["last_updated"] = _now()
        self.data["metadata"]["total_count"] = len(self.data["vectors"])
        self._s3.put_object(
            Bucket=self.bucket, Key=self._key(_DB_KEY),
            Body=json.dumps(self.data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

    def find_similar(self, query_embedding, threshold=PREDICTION_THRESHOLD, top_k=TOP_K):
        vectors = self.data["vectors"]
        if not vectors:
            return {"matched": False, "confidence": 0.0, "top_k": [], "similarity_margin": 0.0}
        embs = np.array([v["embedding"] for v in vectors])
        sims = cosine_similarity([query_embedding], embs)[0]
        idxs = np.argsort(sims)[-top_k:][::-1]
        top_k_r = [{"field_name": vectors[i]["field_name"], "confidence": float(sims[i]), "vector_id": vectors[i]["vector_id"]} for i in idxs]
        bv = vectors[idxs[0]]; bc = float(sims[idxs[0]])
        margin = top_k_r[0]["confidence"] - top_k_r[1]["confidence"] if len(top_k_r) >= 2 else 0.0
        if bc >= threshold:
            bv["usage_count"] = bv.get("usage_count", 0) + 1; bv["last_used"] = _now()
            return {"matched": True, "vector_id": bv["vector_id"], "field_name": bv["field_name"], "confidence": bc,
                    "vector_confidence": bv.get("confidence_history", [0.75])[-1],
                    "positive_count": bv.get("positive_count", 0), "negative_count": bv.get("negative_count", 0),
                    "usage_count": bv.get("usage_count", 0), "stability_score": bv.get("stability_score", 1.0),
                    "top_k": top_k_r, "similarity_margin": float(margin)}
        return {"matched": False, "confidence": bc, "best_candidate": bv["field_name"], "top_k": top_k_r, "similarity_margin": float(margin)}

    def add_vector(self, field_name, context, section_context, headers, embedding, **metadata):
        vid = generate_vector_id(self.data["vectors"]); now = _now()
        self.data["vectors"].append({"vector_id": vid, "field_name": field_name, "context": context,
            "section_context": section_context, "headers": headers, "embedding": embedding,
            "confidence_history": [0.75], "positive_count": 1, "negative_count": 0, "usage_count": 1,
            "stability_score": 1.0, "avg_confidence": 0.75, "error_history": [],
            "created_at": now, "last_updated": now, "last_used": now, **metadata})
        return vid

    def update_confidence(self, vector_id, is_positive, error_info=None):
        for v in self.data["vectors"]:
            if v["vector_id"] != vector_id: continue
            now = _now(); hist = v.setdefault("confidence_history", [0.75]); curr = hist[-1]
            if is_positive:
                new_c = min(curr * CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE)
                v["positive_count"] = v.get("positive_count", 0) + 1
            else:
                new_c = max(curr * CONFIDENCE_DECAY_RATE, MIN_CONFIDENCE)
                v["negative_count"] = v.get("negative_count", 0) + 1
                if error_info:
                    v.setdefault("error_history", []).append({"timestamp": now, **error_info})
            hist.append(round(new_c, 6))
            t = v.get("positive_count", 0) + v.get("negative_count", 0)
            v["stability_score"] = round(v.get("positive_count", 0) / t, 4) if t else 1.0
            v["avg_confidence"] = round(sum(hist) / len(hist), 6)
            v["usage_count"] = v.get("usage_count", 0) + 1
            v["last_updated"] = now; v["last_used"] = now
            return new_c
        return None

    def count(self): return len(self.data["vectors"])

    def find_by_name(self, field_name: str):
        """Find vector_id by exact field_name match."""
        for v in self.data.get("vectors", []):
            if v.get("field_name") == field_name:
                return v["vector_id"]
        return None
