# tests/unit/test_metrics_service.py
import pytest
from unittest.mock import MagicMock
from ragpdf.services.metrics_service import MetricsService


@pytest.fixture
def svc():
    mock_storage = MagicMock()
    return MetricsService(mock_storage)


def _make_preds(n=5):
    rag = {"predictions": {f"f{i}": {"predicted_field_name": f"field_{i}", "confidence": 0.85} for i in range(n)}}
    llm = {"predictions": {f"f{i}": {"predicted_field_name": f"field_{i}", "confidence": 0.90} for i in range(n)}}
    fin = {"final_predictions": {f"f{i}": {"selected_field_name": f"field_{i}", "selected_from": "rag", "rag_confidence": 0.85} for i in range(n)}}
    return rag, llm, fin


def _make_cc(n=5):
    from ragpdf.utils.constants import CASE_A, CASE_B, CASE_C, CASE_D, CASE_E
    return {
        "total_fields": n,
        "case_breakdown": {
            CASE_A: {"count": n, "field_ids": [f"f{i}" for i in range(n)]},
            CASE_B: {"count": 0, "field_ids": []},
            CASE_C: {"count": 0, "field_ids": []},
            CASE_D: {"count": 0, "field_ids": []},
            CASE_E: {"count": 0, "field_ids": []},
        }
    }


def test_calculate_metrics_structure(svc):
    rag, llm, fin = _make_preds()
    cc = _make_cc()
    cat = {"category": "PE", "sub_category": "LP", "document_type": "Sub Agreement"}
    # FIX: calculate_metrics takes exactly 10 args — removed the stray "rag" positional arg
    m = svc.calculate_metrics("u", "s", "p", "sub_1", "hash", rag, llm, fin, cc, cat)
    assert "accuracy" in m
    assert "coverage" in m
    assert "field_counts" in m
    assert m["accuracy"]["accuracy_ensemble"] == 1.0
    assert m["field_counts"]["total_fields"] == 5


def test_coverage_calculation(svc):
    rag, llm, fin = _make_preds(4)
    cc = _make_cc(4)
    cat = {"category": "PE", "sub_category": "LP", "document_type": "Sub"}
    # FIX: same as above — no stray "rag" arg
    m = svc.calculate_metrics("u", "s", "p", "sub_1", "hash", rag, llm, fin, cc, cat)
    assert m["coverage"]["coverage_ensemble"] == 1.0


def test_recalculate_accuracy_after_errors(tmp_path):
    # FIX: recalculate_accuracy_after_errors(user_id, session_id, pdf_id, errors)
    # loads metrics and final_preds from storage — must be pre-saved.
    from ragpdf.storage.local_storage import LocalStorage
    storage = LocalStorage(data_path=str(tmp_path))
    svc = MetricsService(storage)

    fields = [{"field_id": "f1"}, {"field_id": "f2"}]
    rag, llm, fin = _make_preds(2)
    cc  = _make_cc(2)
    cat = {"category": "PE", "sub_category": "LP", "document_type": "Sub"}

    # Calculate initial metrics
    metrics = svc.calculate_metrics("u1", "s1", "p1", "sub1", "hash1", rag, llm, fin, cc, cat)

    # Persist what recalculate needs
    storage.save_json("predictions/u1/s1/p1/analysis/metrics_snapshot.json", metrics)
    storage.save_json("predictions/u1/s1/p1/predictions/final_predictions.json", fin)

    # Now recalculate — positional args only, no kwargs
    updated = svc.recalculate_accuracy_after_errors(
        "u1", "s1", "p1",
        errors=[{"field_name": "field_0"}],
    )
    assert updated is not None
    assert updated["accuracy"]["errors_ensemble"] == 1
    assert updated["accuracy"]["accuracy_ensemble"] < 1.0