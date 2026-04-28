# src/ragpdf/pipeline/prediction_pipeline.py
import logging
from datetime import datetime
from ragpdf.models.predictor import FieldPredictor
from ragpdf.storage.base import StorageBackend
from ragpdf.utils.helpers import generate_submission_id
from ragpdf.utils.constants import PDF_HASH_MAPPING_KEY

logger = logging.getLogger(__name__)


class PredictionPipeline:
    """
    Orchestrates API 1: get_rag_predictions.
    Generates RAG predictions for a set of PDF fields, saves results to storage.
    """

    def __init__(self, predictor: FieldPredictor, storage: StorageBackend):
        self.predictor = predictor
        self.storage = storage

    def run(self, user_id: str, session_id: str, pdf_id: str,
            fields: list, pdf_hash: str, pdf_category: dict) -> dict:

        submission_id, frequency, is_duplicate = generate_submission_id(
            user_id, session_id, pdf_id, pdf_hash, self.storage
        )
        logger.info(f"Submission {submission_id} (freq={frequency}, dup={is_duplicate})")

        meta_path = f"predictions/{user_id}/{session_id}/{pdf_id}/metadata"
        self.storage.save_json(f"{meta_path}/submission_info.json", {
            "submission_id": submission_id, "user_id": user_id,
            "session_id": session_id, "pdf_id": pdf_id,
            "frequency": frequency, "is_duplicate": is_duplicate,
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
        self.storage.save_json(f"{meta_path}/pdf_info.json", {
            "pdf_hash": pdf_hash, "pdf_category": pdf_category,
            "total_fields": len(fields),
        })

        # Save raw input for later vector creation (CASE_B/C)
        pred_path = f"predictions/{user_id}/{session_id}/{pdf_id}/predictions"
        self.storage.save_json(f"{pred_path}/input.json", {
            "user_id": user_id, "session_id": session_id, "pdf_id": pdf_id,
            "fields": fields,
        })

        results = self.predictor.predict(fields)

        predictions: dict = {}
        for r in results:
            fid = r["field_id"]
            if r.get("matched"):
                predictions[fid] = {
                    "predicted_field_name": r["field_name"],
                    "confidence": r["confidence"],
                    "vector_id": r["vector_id"],
                    "top_k": r.get("top_k", []),
                    "similarity_margin": r.get("similarity_margin", 0.0),
                }
            else:
                predictions[fid] = None

        matched = sum(1 for p in results if p.get("matched"))
        avg_conf = round(sum(r["confidence"] for r in results if r.get("matched")) / matched, 4) if matched else 0.0

        rag_output = {
            "user_id": user_id, "session_id": session_id, "pdf_id": pdf_id,
            "model": "rag", "timestamp": datetime.utcnow().isoformat() + "Z",
            "pdf_hash": pdf_hash, "predictions": predictions,
            "summary": {
                "total_fields": len(fields),
                "predicted_fields": matched,
                "unpredicted_fields": len(fields) - matched,
                "avg_confidence": avg_conf,
            },
        }
        self.storage.save_json(f"{pred_path}/rag_predictions.json", rag_output)
        self._update_pdf_hash_mapping(pdf_hash, submission_id, user_id, session_id,
                                       pdf_id, pdf_category, len(fields), frequency)

        return {
            "user_id": user_id, "session_id": session_id, "pdf_id": pdf_id,
            "submission_id": submission_id, "pdf_hash": pdf_hash,
            "frequency": frequency, "is_duplicate": is_duplicate,
            "summary": rag_output["summary"],
        }

    def _update_pdf_hash_mapping(self, pdf_hash, submission_id, user_id,
                                  session_id, pdf_id, pdf_category, total_fields, frequency):
        mapping = self.storage.load_json(PDF_HASH_MAPPING_KEY) or {}
        now = datetime.utcnow().isoformat() + "Z"
        if pdf_hash not in mapping:
            mapping[pdf_hash] = {
                "pdf_hash": pdf_hash, "pdf_id": pdf_id,
                "category": pdf_category.get("category"),
                "sub_category": pdf_category.get("sub_category"),
                "document_type": pdf_category.get("document_type"),
                "pdf_count": 0, "total_submissions": 0,
                "submissions": [], "first_seen": now, "last_seen": now,
            }
        mapping[pdf_hash]["pdf_count"] += 1
        mapping[pdf_hash]["total_submissions"] += 1
        mapping[pdf_hash]["last_seen"] = now
        mapping[pdf_hash]["submissions"].append({
            "submission_id": submission_id, "user_id": user_id,
            "session_id": session_id, "pdf_id": pdf_id,
            "frequency": frequency, "timestamp": now, "total_fields": total_fields,
        })
        self.storage.save_json(PDF_HASH_MAPPING_KEY, mapping)
