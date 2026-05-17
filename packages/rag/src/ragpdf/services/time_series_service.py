# src/ragpdf/services/time_series_service.py
import logging
from datetime import datetime
from ragpdf.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class TimeSeriesService:
    """
    Append metrics snapshots to 5 hierarchical time series:
      1. pdf_hash level
      2. category level
      3. subcategory level
      4. doctype level
      5. global level
    """

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def update_all_time_series(self, pdf_hash: str, category: str,
                                subcategory: str, doctype: str, metrics: dict):
        levels = [
            ("pdf_hash",    pdf_hash,                        f"metrics/time_series/pdf_hash/{pdf_hash}/time_series.json"),
            ("category",    category,                        f"metrics/time_series/category/{category}/time_series.json"),
            ("subcategory", f"{category}/{subcategory}",     f"metrics/time_series/subcategory/{category}/{subcategory}/time_series.json"),
            ("doctype",     f"{category}/{subcategory}/{doctype}", f"metrics/time_series/doctype/{category}/{subcategory}/{doctype}/time_series.json"),
            ("global",      "global",                        "metrics/time_series/global/time_series.json"),
        ]
        for level, identifier, path in levels:
            self._append(level, identifier, path, metrics)
        logger.info("Time series updated at all 5 levels")

    def _append(self, level: str, identifier: str, path: str, metrics: dict):
        ts = self.storage.load_json(path) or {
            "level": level, "identifier": identifier, "entries": [],
            "metadata": {"total_entries": 0, "first_entry": None, "last_entry": None},
        }
        entry = {
            "timestamp": metrics["timestamp"],
            "submission_id": metrics.get("submission_id"),
            "user_id": metrics.get("user_id"),
            "session_id": metrics.get("session_id"),
            "pdf_id": metrics.get("pdf_id"),
            "metrics": {
                "total_fields":        metrics["field_counts"]["total_fields"],
                "predicted_llm":       metrics["field_counts"]["predicted_llm"],
                "predicted_rag":       metrics["field_counts"]["predicted_rag"],
                "predicted_ensemble":  metrics["field_counts"]["predicted_ensemble"],
                "coverage_llm":        metrics["coverage"]["coverage_llm"],
                "coverage_rag":        metrics["coverage"]["coverage_rag"],
                "coverage_ensemble":   metrics["coverage"]["coverage_ensemble"],
                "accuracy_llm":        metrics["accuracy"]["accuracy_llm"],
                "accuracy_rag":        metrics["accuracy"]["accuracy_rag"],
                "accuracy_ensemble":   metrics["accuracy"]["accuracy_ensemble"],
                "avg_conf_llm":        metrics["confidence"]["avg_conf_llm"],
                "avg_conf_rag":        metrics["confidence"]["avg_conf_rag"],
                "avg_conf_ensemble":   metrics["confidence"]["avg_conf_ensemble"],
                "agreement_rate":      metrics["agreement"]["agreement_rate"],
                "conflict_rate":       metrics["agreement"]["conflict_rate"],
                "rag_recovery":        metrics["recovery"]["rag_recovery"],
                "llm_recovery":        metrics["recovery"]["llm_recovery"],
                "errors_llm":          metrics["accuracy"]["errors_llm"],
                "errors_rag":          metrics["accuracy"]["errors_rag"],
                "errors_ensemble":     metrics["accuracy"]["errors_ensemble"],
            },
        }
        ts["entries"].append(entry)
        ts["metadata"]["total_entries"] += 1
        ts["metadata"]["last_entry"] = metrics["timestamp"]
        if not ts["metadata"]["first_entry"]:
            ts["metadata"]["first_entry"] = metrics["timestamp"]
        self.storage.save_json(path, ts)
