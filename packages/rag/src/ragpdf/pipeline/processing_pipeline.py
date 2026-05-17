# src/ragpdf/pipeline/processing_pipeline.py
import logging
from datetime import datetime
from ragpdf.storage.base import StorageBackend
from ragpdf.services.case_classifier import CaseClassifier
from ragpdf.services.metrics_service import MetricsService
from ragpdf.services.time_series_service import TimeSeriesService
from ragpdf.vector_stores.base import VectorStoreBackend
from ragpdf.embeddings.base import EmbeddingBackend
from ragpdf.utils.constants import CASE_A, CASE_B, CASE_C, CASE_D, SOURCE_RAG, SOURCE_LLM

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """
    Orchestrates API 2: saving_filled_pdf.
    Runs the full post-fill pipeline:
      1. Load all 3 prediction files (rag, llm, final)
      2. Case classification
      3. Metrics calculation
      4. Vector DB update
      5. Time series update (5 levels)
    """

    def __init__(self, storage: StorageBackend, vector_store: VectorStoreBackend,
                 embedding_backend: EmbeddingBackend):
        self.storage = storage
        self.vector_store = vector_store
        self.embedding_backend = embedding_backend
        self.classifier = CaseClassifier()
        self.metrics_svc = MetricsService(storage)
        self.ts_svc = TimeSeriesService(storage)

    def run(self, user_id: str, session_id: str, pdf_id: str,
            llm_predictions: dict, final_predictions: dict) -> dict:

        base = f"predictions/{user_id}/{session_id}/{pdf_id}"
        rag_preds = self.storage.load_json(f"{base}/predictions/rag_predictions.json")
        pdf_info  = self.storage.load_json(f"{base}/metadata/pdf_info.json")
        sub_info  = self.storage.load_json(f"{base}/metadata/submission_info.json")

        if not rag_preds:
            raise ValueError("RAG predictions not found. Call get_predictions() first.")

        submission_id = sub_info.get("submission_id", "unknown") if sub_info else "unknown"
        pdf_hash  = pdf_info.get("pdf_hash", "")
        pdf_cat   = pdf_info.get("pdf_category", {})

        # Save LLM + final predictions
        self.storage.save_json(f"{base}/predictions/llm_predictions.json", llm_predictions)
        self.storage.save_json(f"{base}/predictions/final_predictions.json", final_predictions)

        fp = final_predictions.get("final_predictions", {})
        rp = rag_preds.get("predictions", {})
        lp = llm_predictions.get("predictions", {})

        # Case classification
        cc = self.classifier.classify(user_id, session_id, pdf_id, rp, lp, fp)
        self.storage.save_json(f"{base}/analysis/case_classification.json", cc)

        # Metrics
        metrics = self.metrics_svc.calculate_metrics(
            user_id, session_id, pdf_id, submission_id, pdf_hash,
            rag_preds, llm_predictions, final_predictions, cc, pdf_cat
        )
        self.storage.save_json(f"{base}/analysis/metrics_snapshot.json", metrics)

        # Vector updates
        vector_summary = self._update_vectors(
            user_id, session_id, pdf_id, cc, fp, rp, lp,
            pdf_hash, submission_id, pdf_cat
        )
        self.storage.save_json(f"{base}/analysis/vector_update_summary.json", vector_summary)

        # Time series
        self.ts_svc.update_all_time_series(
            pdf_hash=pdf_hash,
            category=pdf_cat.get("category", "unknown"),
            subcategory=pdf_cat.get("sub_category", "unknown"),
            doctype=pdf_cat.get("document_type", "unknown"),
            metrics=metrics,
        )

        logger.info(f"Processing pipeline complete for {user_id}/{session_id}/{pdf_id}")
        return {
            "submission_id": submission_id,
            "case_classification": cc.get("case_breakdown"),
            "metrics_summary": {
                "accuracy_ensemble":  metrics["accuracy"]["accuracy_ensemble"],
                "coverage_ensemble":  metrics["coverage"]["coverage_ensemble"],
                "agreement_rate":     metrics["agreement"]["agreement_rate"],
            },
            "vector_updates": vector_summary.get("summary"),
        }

    def _update_vectors(self, user_id, session_id, pdf_id, cc, fp, rp, lp,
                         pdf_hash, submission_id, pdf_cat):
        cat = pdf_cat.get("category"); sub = pdf_cat.get("sub_category"); doc = pdf_cat.get("document_type")
        updates = []; updated = 0; created = 0

        for case_type, case_data in cc["case_breakdown"].items():
            for fid in case_data["field_ids"]:
                fin = fp.get(fid)
                if not fin: continue

                if case_type == CASE_A:
                    rp_fid = rp.get(fid)
                    if rp_fid and rp_fid.get("vector_id"):
                        self.vector_store.update_confidence(rp_fid["vector_id"], True)
                        updates.append({"field_id": fid, "action": "boosted", "reason": "CASE_A"}); updated+=1

                elif case_type == CASE_B:
                    sel = fin.get("selected_from") if isinstance(fin, dict) else None
                    if sel == SOURCE_RAG:
                        rp_fid = rp.get(fid)
                        if rp_fid and rp_fid.get("vector_id"):
                            self.vector_store.update_confidence(rp_fid["vector_id"], True)
                            updates.append({"field_id": fid, "action": "boosted", "reason": "CASE_B RAG selected"}); updated+=1
                    elif sel == SOURCE_LLM:
                        lp_fid = lp.get(fid)
                        if lp_fid and isinstance(lp_fid, dict):
                            ctx = self._field_context(fid, user_id, session_id, pdf_id)
                            if ctx:
                                emb = self.embedding_backend.embed(self.embedding_backend.create_text_from_field(ctx))
                                vid = self.vector_store.add_vector(
                                    field_name=lp_fid.get("predicted_field_name",""),
                                    context=ctx.get("context",""), section_context=ctx.get("section_context",""),
                                    headers=ctx.get("headers",[]), embedding=emb,
                                    pdf_hash=pdf_hash, submission_id=submission_id,
                                    category=cat, sub_category=sub, document_type=doc, prediction_source=SOURCE_LLM)
                                updates.append({"field_id": fid, "vector_id": vid, "action": "created", "reason": "CASE_B LLM selected"}); created+=1

                elif case_type == CASE_C:
                    lp_fid = lp.get(fid)
                    if lp_fid and isinstance(lp_fid, dict):
                        ctx = self._field_context(fid, user_id, session_id, pdf_id)
                        if ctx:
                            emb = self.embedding_backend.embed(self.embedding_backend.create_text_from_field(ctx))
                            vid = self.vector_store.add_vector(
                                field_name=lp_fid.get("predicted_field_name",""),
                                context=ctx.get("context",""), section_context=ctx.get("section_context",""),
                                headers=ctx.get("headers",[]), embedding=emb,
                                pdf_hash=pdf_hash, submission_id=submission_id,
                                category=cat, sub_category=sub, document_type=doc, prediction_source=SOURCE_LLM)
                            updates.append({"field_id": fid, "vector_id": vid, "action": "created", "reason": "CASE_C LLM only"}); created+=1

                elif case_type == CASE_D:
                    rp_fid = rp.get(fid)
                    if rp_fid and rp_fid.get("vector_id"):
                        self.vector_store.update_confidence(rp_fid["vector_id"], True)
                        updates.append({"field_id": fid, "action": "boosted", "reason": "CASE_D"}); updated+=1

        self.vector_store.save()
        return {"timestamp": datetime.utcnow().isoformat()+"Z",
                "summary": {"vectors_updated": updated, "vectors_created": created, "total": self.vector_store.count()},
                "updates": updates}

    def _field_context(self, field_id, user_id, session_id, pdf_id):
        data = self.storage.load_json(f"predictions/{user_id}/{session_id}/{pdf_id}/predictions/input.json")
        if not data: return None
        for f in data.get("fields", []):
            if f.get("field_id") == field_id:
                return f
        return None
