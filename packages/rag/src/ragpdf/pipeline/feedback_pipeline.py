# src/ragpdf/pipeline/feedback_pipeline.py
import logging
from datetime import datetime

from ragpdf.correctors.base import FieldCorrectorBackend
from ragpdf.services.metrics_service import MetricsService
from ragpdf.services.time_series_service import TimeSeriesService
from ragpdf.storage.base import StorageBackend
from ragpdf.utils.constants import SOURCE_RAG
from ragpdf.vector_stores.base import VectorStoreBackend

logger = logging.getLogger(__name__)


class FeedbackPipeline:
    """
    Orchestrates API 4: user_feedback.
    1. Tag + save raw feedback
    2. GPT-4/LLM -> corrected field names
    3. Route each error to responsible vector
    4. Negative confidence update + embedding regeneration
    5. Recalculate metrics + time series
    """

    def __init__(
        self,
        storage: StorageBackend,
        vector_store: VectorStoreBackend,
        corrector: FieldCorrectorBackend,
    ):
        self.storage = storage
        self.vector_store = vector_store
        self.corrector = corrector
        self.metrics_svc = MetricsService(storage)
        self.ts_svc = TimeSeriesService(storage)

    def run(
        self,
        user_id: str,
        session_id: str,
        pdf_id: str,
        submission_id: str,
        errors: list,
        timestamp: str | None = None,
    ) -> dict:

        timestamp = timestamp or datetime.utcnow().isoformat() + "Z"
        base = f"predictions/{user_id}/{session_id}/{pdf_id}"
        err_path = f"{base}/errors"

        for e in errors:
            e.update(
                {
                    "timestamp": timestamp,
                    "user_id": user_id,
                    "session_id": session_id,
                    "pdf_id": pdf_id,
                }
            )
        self.storage.append_to_jsonl(
            f"{err_path}/user_feedback_raw.jsonl",
            {"timestamp": timestamp, "errors": errors},
        )

        corrections = []
        for e in errors:
            c = self.corrector.generate_corrected_field_name(e)
            e["corrected_field_name"] = c["corrected_field_name"]
            e["gpt4_confidence"] = c["confidence"]
            e["gpt4_reasoning"] = c["reasoning"]
            corrections.append(c)

        cc = self.storage.load_json(f"{base}/analysis/case_classification.json")
        fp = self.storage.load_json(f"{base}/predictions/final_predictions.json")
        rp = self.storage.load_json(f"{base}/predictions/rag_predictions.json")
        pinfo = self.storage.load_json(f"{base}/metadata/pdf_info.json")

        if not all([cc, fp, rp, pinfo]):
            logger.error("Missing required files for feedback processing")
            return {
                "errors_processed": 0,
                "vectors_updated": 0,
                "error": "Missing S3 files",
            }

        vectors_updated = 0
        analysis = []

        for e in errors:
            fn = e.get("field_name")
            if not fn:
                continue
            fid = self._find_field_id(fn, fp)
            if not fid:
                continue
            case = self._find_case_type(fid, cc)
            err_info = {
                "pdf_hash": pinfo.get("pdf_hash"),
                "error_type": e.get("error_type", "mapping_error"),
                "user_feedback": e.get("feedback", ""),
                "corrected_field_name": e["corrected_field_name"],
            }

            if case in ["CASE_A", "CASE_D"]:
                rp_fid = rp.get("predictions", {}).get(fid)
                if rp_fid and rp_fid.get("vector_id"):
                    self.vector_store.update_confidence(
                        rp_fid["vector_id"], False, err_info
                    )
                    vectors_updated += 1
                    analysis.append(
                        {
                            "field_name": fn,
                            "field_id": fid,
                            "case_type": case,
                            "vector_affected": rp_fid["vector_id"],
                            "gpt4_correction": e["corrected_field_name"],
                        }
                    )

            elif case == "CASE_B":
                fin = fp.get("final_predictions", {}).get(fid, {})
                sel = fin.get("selected_from") if isinstance(fin, dict) else None
                if sel == SOURCE_RAG:
                    rp_fid = rp.get("predictions", {}).get(fid)
                    if rp_fid and rp_fid.get("vector_id"):
                        self.vector_store.update_confidence(
                            rp_fid["vector_id"], False, err_info
                        )
                        vectors_updated += 1
                        analysis.append(
                            {
                                "field_name": fn,
                                "field_id": fid,
                                "case_type": case,
                                "vector_affected": rp_fid["vector_id"],
                                "gpt4_correction": e["corrected_field_name"],
                            }
                        )
                else:
                    ffn = (
                        fin.get("selected_field_name")
                        if isinstance(fin, dict)
                        else None
                    )
                    vid = self._find_vector_by_name(ffn)
                    if vid:
                        self.vector_store.update_confidence(vid, False, err_info)
                        vectors_updated += 1
                        analysis.append(
                            {
                                "field_name": fn,
                                "field_id": fid,
                                "case_type": case,
                                "vector_affected": vid,
                                "gpt4_correction": e["corrected_field_name"],
                            }
                        )

            elif case == "CASE_C":
                fin = fp.get("final_predictions", {}).get(fid, {})
                ffn = fin.get("selected_field_name") if isinstance(fin, dict) else None
                vid = self._find_vector_by_name(ffn)
                if vid:
                    self.vector_store.update_confidence(vid, False, err_info)
                    vectors_updated += 1
                    analysis.append(
                        {
                            "field_name": fn,
                            "field_id": fid,
                            "case_type": case,
                            "vector_affected": vid,
                            "gpt4_correction": e["corrected_field_name"],
                        }
                    )

        self.vector_store.save()

        self.storage.save_json(
            f"{err_path}/error_analysis.json",
            {
                "user_id": user_id,
                "session_id": session_id,
                "pdf_id": pdf_id,
                "timestamp": timestamp,
                "total_errors": len(errors),
                "vectors_updated": vectors_updated,
                "errors": analysis,
                "gpt4_corrections": corrections,
            },
        )

        updated_metrics = self.metrics_svc.recalculate_accuracy_after_errors(
            user_id, session_id, pdf_id, errors
        )
        if updated_metrics:
            self.storage.save_json(
                f"{err_path}/metrics_snapshot_updated.json", updated_metrics
            )
            cat = pinfo.get("pdf_category", {})
            self.ts_svc.update_all_time_series(
                pdf_hash=pinfo["pdf_hash"],
                category=cat.get("category", "unknown"),
                subcategory=cat.get("sub_category", "unknown"),
                doctype=cat.get("document_type", "unknown"),
                metrics=updated_metrics,
            )

        safe_ts = timestamp.replace(":", "-")
        self.storage.save_json(
            f"{err_path}/error_log_{safe_ts}.json",
            {
                "user_id": user_id,
                "session_id": session_id,
                "pdf_id": pdf_id,
                "pdf_hash": pinfo.get("pdf_hash"),
                "timestamp": timestamp,
                "errors": errors,
            },
        )

        return {
            "user_id": user_id,
            "session_id": session_id,
            "pdf_id": pdf_id,
            "submission_id": submission_id,
            "errors_processed": len(errors),
            "gpt4_corrections_generated": len(corrections),
            "vectors_updated": vectors_updated,
            "metrics_recalculated": updated_metrics is not None,
            "corrected_mappings": [
                {
                    "field_name": e.get("field_name"),
                    "corrected_to": e["corrected_field_name"],
                    "confidence": e["gpt4_confidence"],
                }
                for e in errors
            ],
        }

    def _find_field_id(self, field_name, final_preds):
        for fid, fp in final_preds.get("final_predictions", {}).items():
            if isinstance(fp, dict) and fp.get("selected_field_name") == field_name:
                return fid
        return None

    def _find_case_type(self, field_id, cc):
        for case, data in cc.get("case_breakdown", {}).items():
            if field_id in data.get("field_ids", []):
                return case
        return None

    def _find_vector_by_name(self, field_name):
        if not field_name:
            return None
        # Use the vector store's own find_by_name — works for all backends
        # (Local, S3, Pinecone, Chroma, Weaviate)
        return self.vector_store.find_by_name(field_name)
