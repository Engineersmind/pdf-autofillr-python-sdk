# src/ragpdf/services/metrics_service.py
import logging
from datetime import datetime
from ragpdf.storage.base import StorageBackend
from ragpdf.config.settings import AMBIGUITY_THRESHOLD

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Calculate accuracy, coverage, confidence, recovery, agreement metrics
    from RAG + LLM + final prediction files and case classification.
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def calculate_metrics(self, user_id, session_id, pdf_id, submission_id,
                          pdf_hash, rag_preds, llm_preds, final_preds,
                          case_classification, pdf_category) -> dict:

        total = case_classification["total_fields"]
        fp = final_preds.get("final_predictions", {})
        rp = rag_preds.get("predictions", {})
        lp = llm_preds.get("predictions", {})
        cb = case_classification["case_breakdown"]

        pred_llm = sum(1 for p in lp.values() if p and isinstance(p, dict))
        pred_rag = sum(1 for p in rp.values() if p and isinstance(p, dict))
        pred_ens = sum(1 for p in fp.values() if isinstance(p, dict) and p.get("selected_field_name"))

        both = cb["CASE_A"]["count"] + cb["CASE_B"]["count"]
        same = cb["CASE_A"]["count"]
        diff = cb["CASE_B"]["count"]
        llm_only = cb["CASE_C"]["count"]
        rag_only = cb["CASE_D"]["count"]
        neither = cb["CASE_E"]["count"]

        cov_llm = _safe_div(pred_llm, total)
        cov_rag = _safe_div(pred_rag, total)
        cov_ens = _safe_div(pred_ens, total)

        agree = _safe_div(same, both)
        conflict = _safe_div(diff, both)

        llm_missed = total - pred_llm
        rag_missed = total - pred_rag
        rag_rec = _safe_div(rag_only, llm_missed)
        llm_rec = _safe_div(llm_only, rag_missed)

        llm_confs = [p["confidence"] for p in lp.values() if p and isinstance(p, dict) and "confidence" in p]
        rag_confs = [p["confidence"] for p in rp.values() if p and isinstance(p, dict) and "confidence" in p]
        ens_confs = []
        for p in fp.values():
            if not isinstance(p, dict): continue
            if p.get("selected_from") == "rag" and p.get("rag_confidence"):
                ens_confs.append(p["rag_confidence"])
            elif p.get("selected_from") == "llm" and p.get("llm_confidence"):
                ens_confs.append(p["llm_confidence"])

        all_margins = [p.get("similarity_margin", 0) for ps in [lp.values(), rp.values()]
                       for p in ps if p and isinstance(p, dict)]
        ambig = sum(1 for m in all_margins if m < AMBIGUITY_THRESHOLD)

        return {
            "user_id": user_id, "session_id": session_id, "pdf_id": pdf_id,
            "submission_id": submission_id, "pdf_hash": pdf_hash,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pdf_category": pdf_category,
            "field_counts": {
                "total_fields": total, "predicted_llm": pred_llm,
                "predicted_rag": pred_rag, "predicted_ensemble": pred_ens,
                "both_predicted": both, "same_predictions": same,
                "different_predictions": diff, "llm_only": llm_only,
                "rag_only": rag_only, "neither_predicted": neither,
            },
            "coverage": {"coverage_llm": cov_llm, "coverage_rag": cov_rag, "coverage_ensemble": cov_ens},
            "agreement": {"agreement_rate": agree, "conflict_rate": conflict},
            "recovery": {"rag_recovery": rag_rec, "llm_recovery": llm_rec},
            "confidence": {
                "avg_conf_llm": _avg(llm_confs), "avg_conf_rag": _avg(rag_confs),
                "avg_conf_ensemble": _avg(ens_confs),
                "confidence_margin_avg": _avg(all_margins),
                "ambiguity_rate": _safe_div(ambig, len(all_margins)),
            },
            "accuracy": {
                "accuracy_llm": 1.0, "accuracy_rag": 1.0, "accuracy_ensemble": 1.0,
                "errors_llm": 0, "errors_rag": 0, "errors_ensemble": 0,
            },
            "case_distribution": {
                "CASE_A_percentage": _safe_div(same, total),
                "CASE_B_percentage": _safe_div(diff, total),
                "CASE_C_percentage": _safe_div(llm_only, total),
                "CASE_D_percentage": _safe_div(rag_only, total),
                "CASE_E_percentage": _safe_div(neither, total),
            },
        }

    def recalculate_accuracy_after_errors(self, user_id, session_id, pdf_id, errors) -> dict:
        base = f"predictions/{user_id}/{session_id}/{pdf_id}"
        metrics = self.storage.load_json(f"{base}/analysis/metrics_snapshot.json")
        final_preds = self.storage.load_json(f"{base}/predictions/final_predictions.json")
        if not metrics or not final_preds:
            logger.error("Missing metrics or final_predictions for recalculation")
            return None

        err_llm = err_rag = 0
        for error in errors:
            fn = error.get("field_name")
            for fid, fp in final_preds.get("final_predictions", {}).items():
                if isinstance(fp, dict) and fp.get("selected_field_name") == fn:
                    if fp.get("selected_from") == "llm": err_llm += 1
                    elif fp.get("selected_from") == "rag": err_rag += 1

        acc = metrics["accuracy"]
        acc["errors_llm"] += err_llm
        acc["errors_rag"] += err_rag
        acc["errors_ensemble"] += len(errors)
        fc = metrics["field_counts"]
        acc["accuracy_llm"] = _safe_div(fc["predicted_llm"] - acc["errors_llm"], fc["predicted_llm"])
        acc["accuracy_rag"] = _safe_div(fc["predicted_rag"] - acc["errors_rag"], fc["predicted_rag"])
        acc["accuracy_ensemble"] = _safe_div(fc["predicted_ensemble"] - acc["errors_ensemble"], fc["predicted_ensemble"])
        metrics["timestamp"] = datetime.utcnow().isoformat() + "Z"
        return metrics


def _safe_div(a, b): return round(a / b, 4) if b else 0.0
def _avg(vals): return round(sum(vals) / len(vals), 4) if vals else 0.0
