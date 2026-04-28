# src/ragpdf/vector_stores/weaviate_store.py
"""
Weaviate vector store plugin.

Install: pip install ragpdf-sdk[weaviate]

Usage:
    from ragpdf.vector_stores import WeaviateStore

    store = WeaviateStore(
        url="http://localhost:8080",
        class_name="RagpdfVector",
    )
"""
import logging
from typing import Optional

from ragpdf.vector_stores.base import VectorStoreBackend
from ragpdf.config.settings import PREDICTION_THRESHOLD, TOP_K

logger = logging.getLogger(__name__)


class WeaviateStore(VectorStoreBackend):
    """Weaviate-backed vector store (v4 client)."""

    def __init__(self, url: str = "", api_key: str = "", class_name: str = "RagpdfVector"):
        try:
            import weaviate
        except ImportError:
            raise ImportError("pip install ragpdf-sdk[weaviate]")
        from ragpdf.config.settings import RAGPDF_WEAVIATE_URL, RAGPDF_WEAVIATE_API_KEY, RAGPDF_WEAVIATE_CLASS
        auth = weaviate.auth.AuthApiKey(api_key or RAGPDF_WEAVIATE_API_KEY) if (api_key or RAGPDF_WEAVIATE_API_KEY) else None
        self._client = weaviate.connect_to_custom(http_host=url or RAGPDF_WEAVIATE_URL, auth_credentials=auth)
        self._class = class_name or RAGPDF_WEAVIATE_CLASS
        self._ensure_schema()
        logger.info(f"WeaviateStore initialized: class={self._class}")

    def _ensure_schema(self):
        try:
            self._client.collections.get(self._class)
        except Exception:
            from weaviate.classes.config import Configure, Property, DataType
            self._client.collections.create(
                name=self._class,
                vectorizer_config=Configure.Vectorizer.none(),
                properties=[
                    Property(name="field_name", data_type=DataType.TEXT),
                    Property(name="context", data_type=DataType.TEXT),
                    Property(name="section_context", data_type=DataType.TEXT),
                    Property(name="current_confidence", data_type=DataType.NUMBER),
                    Property(name="positive_count", data_type=DataType.INT),
                    Property(name="negative_count", data_type=DataType.INT),
                    Property(name="usage_count", data_type=DataType.INT),
                    Property(name="stability_score", data_type=DataType.NUMBER),
                ]
            )

    def find_similar(self, query_embedding, threshold=PREDICTION_THRESHOLD, top_k=TOP_K):
        col = self._client.collections.get(self._class)
        from weaviate.classes.query import MetadataQuery
        res = col.query.near_vector(near_vector=query_embedding, limit=top_k,
                                     return_metadata=MetadataQuery(certainty=True))
        objs = res.objects
        if not objs:
            return {"matched": False, "confidence": 0.0, "top_k": [], "similarity_margin": 0.0}
        top_k_r = [{"field_name": o.properties.get("field_name", ""),
                     "confidence": o.metadata.certainty or 0.0,
                     "vector_id": str(o.uuid)} for o in objs]
        bc = top_k_r[0]["confidence"]; best = objs[0]
        margin = top_k_r[0]["confidence"] - top_k_r[1]["confidence"] if len(top_k_r) >= 2 else 0.0
        if bc >= threshold:
            p = best.properties
            return {"matched": True, "vector_id": str(best.uuid), "field_name": p.get("field_name", ""),
                    "confidence": bc, "vector_confidence": float(p.get("current_confidence", 0.75)),
                    "positive_count": int(p.get("positive_count", 0)),
                    "negative_count": int(p.get("negative_count", 0)),
                    "usage_count": int(p.get("usage_count", 0)),
                    "stability_score": float(p.get("stability_score", 1.0)),
                    "top_k": top_k_r, "similarity_margin": float(margin)}
        return {"matched": False, "confidence": bc, "best_candidate": top_k_r[0]["field_name"],
                "top_k": top_k_r, "similarity_margin": float(margin)}

    def add_vector(self, field_name, context, section_context, headers, embedding, **metadata):
        import uuid
        col = self._client.collections.get(self._class)
        vid = str(uuid.uuid4())
        col.data.insert(properties={"field_name": field_name, "context": context,
                                     "section_context": section_context,
                                     "current_confidence": 0.75, "positive_count": 1,
                                     "negative_count": 0, "usage_count": 1, "stability_score": 1.0},
                        vector=embedding, uuid=vid)
        return vid

    def update_confidence(self, vector_id, is_positive, error_info=None):
        from ragpdf.config.settings import CONFIDENCE_DECAY_RATE, CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE, MIN_CONFIDENCE
        import uuid
        col = self._client.collections.get(self._class)
        obj = col.query.fetch_object_by_id(uuid.UUID(vector_id))
        if not obj: return None
        p = obj.properties; curr = float(p.get("current_confidence", 0.75))
        if is_positive:
            new_c = min(curr * CONFIDENCE_GROWTH_RATE, MAX_CONFIDENCE)
            new_pos = int(p.get("positive_count", 0)) + 1; new_neg = int(p.get("negative_count", 0))
        else:
            new_c = max(curr * CONFIDENCE_DECAY_RATE, MIN_CONFIDENCE)
            new_pos = int(p.get("positive_count", 0)); new_neg = int(p.get("negative_count", 0)) + 1
        t = new_pos + new_neg
        col.data.update(uuid=uuid.UUID(vector_id), properties={"current_confidence": round(new_c, 6),
            "positive_count": new_pos, "negative_count": new_neg,
            "stability_score": round(new_pos / t, 4) if t else 1.0,
            "usage_count": int(p.get("usage_count", 0)) + 1})
        return new_c

    def save(self): pass
    def count(self):
        col = self._client.collections.get(self._class)
        return col.aggregate.over_all(total_count=True).total_count

    def find_by_name(self, field_name: str):
        """Query Weaviate by field_name property filter."""
        try:
            from weaviate.classes.query import Filter
            col = self._client.collections.get(self._class)
            res = col.query.fetch_objects(
                filters=Filter.by_property("field_name").equal(field_name),
                limit=1,
            )
            objs = res.objects
            return str(objs[0].uuid) if objs else None
        except Exception as e:
            logger.warning(f"WeaviateStore find_by_name failed: {e}")
            return None
