# tests/unit/test_storage_local.py
import os
from unittest.mock import MagicMock

import pytest

from ragpdf.storage.local_storage import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(data_path=str(tmp_path))


# ── LocalStorage tests ────────────────────────────────────────────────────────


def test_save_and_load_json(storage):
    data = {"key": "value", "num": 42}
    storage.save_json("test/data.json", data)
    loaded = storage.load_json("test/data.json")
    assert loaded == data


def test_load_missing_key_returns_none(storage):
    assert storage.load_json("nonexistent/file.json") is None


def test_append_and_load_jsonl(storage):
    # FIX: method is append_to_jsonl(), not append_jsonl()
    storage.append_to_jsonl("logs/events.jsonl", {"event": "a"})
    storage.append_to_jsonl("logs/events.jsonl", {"event": "b"})
    records = storage.load_jsonl("logs/events.jsonl")
    assert len(records) == 2
    assert records[0]["event"] == "a"
    assert records[1]["event"] == "b"


def test_load_missing_jsonl_returns_empty(storage):
    assert storage.load_jsonl("nonexistent/file.jsonl") == []


def test_overwrite_json(storage):
    storage.save_json("file.json", {"v": 1})
    storage.save_json("file.json", {"v": 2})
    assert storage.load_json("file.json")["v"] == 2


def test_nested_paths_created(storage, tmp_path):
    storage.save_json("a/b/c/d/file.json", {"x": 1})
    assert (tmp_path / "a" / "b" / "c" / "d" / "file.json").exists()


def test_exists(storage, tmp_path):
    # FIX: LocalStorage has no exists() method — check with os.path.exists directly
    key = "test/file.json"
    full_path = os.path.join(str(tmp_path), key)
    assert not os.path.exists(full_path)
    storage.save_json(key, {})
    assert os.path.exists(full_path)


# ── helpers tests ─────────────────────────────────────────────────────────────

from ragpdf.utils.helpers import (  # noqa: E402
    calculate_avg,
    generate_submission_id,
    generate_vector_id,
    get_pdf_frequency,
)


def test_submission_id_format():
    # FIX: generate_submission_id takes (user_id, session_id, pdf_id, pdf_hash, storage)
    # and returns (submission_id, frequency, is_duplicate).
    # Format is "{user_id}_{session_id}_{pdf_id}_{frequency}_{unix_timestamp}",
    # NOT "__"-separated and NOT "f1" as the 4th part.
    mock_storage = MagicMock()
    mock_storage.load_json.return_value = None  # no existing mapping -> frequency=1
    submission_id, frequency, is_duplicate = generate_submission_id(
        "user1", "sess1", "pdf1", "somehash", mock_storage
    )
    parts = submission_id.split("_")
    assert parts[0] == "user1"
    assert parts[1] == "sess1"
    assert parts[2] == "pdf1"
    assert parts[3] == "1"  # frequency=1 on first submission
    assert parts[4].isdigit()  # unix timestamp
    assert frequency == 1
    assert is_duplicate is False


def test_submission_id_duplicate():
    # frequency > 1 means is_duplicate=True
    mock_storage = MagicMock()
    mock_storage.load_json.return_value = {"somehash": {"pdf_count": 2}}
    _, frequency, is_duplicate = generate_submission_id(
        "user1", "sess1", "pdf1", "somehash", mock_storage
    )
    assert frequency == 3
    assert is_duplicate is True


def test_generate_vector_id_empty():
    assert generate_vector_id([]) == "vec_001"


def test_generate_vector_id_sequential():
    existing = [{"vector_id": "vec_003"}, {"vector_id": "vec_007"}]
    assert generate_vector_id(existing) == "vec_008"


def test_get_pdf_frequency_new():
    # FIX: get_pdf_frequency takes (pdf_hash, storage_object), not a plain dict.
    mock_storage = MagicMock()
    mock_storage.load_json.return_value = {}  # empty mapping
    assert get_pdf_frequency("abc123", mock_storage) == 1


def test_get_pdf_frequency_none_mapping():
    mock_storage = MagicMock()
    mock_storage.load_json.return_value = None  # no file yet
    assert get_pdf_frequency("abc123", mock_storage) == 1


def test_get_pdf_frequency_existing():
    # FIX: mapping key is pdf_hash -> {"pdf_count": N}, not "total_submissions"
    mock_storage = MagicMock()
    mock_storage.load_json.return_value = {"abc123": {"pdf_count": 4}}
    assert get_pdf_frequency("abc123", mock_storage) == 5


def test_calculate_avg():
    assert calculate_avg([1.0, 2.0, 3.0]) == 2.0
    assert calculate_avg([]) == 0.0


# ── MetricsService tests ──────────────────────────────────────────────────────

from ragpdf.services.metrics_service import MetricsService  # noqa: E402


@pytest.fixture
def metrics_service(tmp_path):
    # FIX: MetricsService requires a storage argument
    storage = LocalStorage(data_path=str(tmp_path))
    return MetricsService(storage)


def _make_preds(fields, predicted=True, confidence=0.9):
    return {
        "predictions": {
            f["field_id"]: (
                {
                    "predicted_field_name": f"mapped_{f['field_id']}",
                    "confidence": confidence,
                }
                if predicted
                else None
            )
            for f in fields
        }
    }


def _make_final(fields, selected_from="rag"):
    return {
        "final_predictions": {
            f["field_id"]: {
                "selected_field_name": f"mapped_{f['field_id']}",
                "selected_from": selected_from,
                f"{selected_from}_confidence": 0.9,
            }
            for f in fields
        }
    }


def _make_case_cls(fields):
    from ragpdf.utils.constants import CASE_A, CASE_B, CASE_C, CASE_D, CASE_E

    return {
        "total_fields": len(fields),
        "case_breakdown": {
            CASE_A: {
                "count": len(fields),
                "field_ids": [f["field_id"] for f in fields],
            },
            CASE_B: {"count": 0, "field_ids": []},
            CASE_C: {"count": 0, "field_ids": []},
            CASE_D: {"count": 0, "field_ids": []},
            CASE_E: {"count": 0, "field_ids": []},
        },
    }


def test_metrics_initial_accuracy_is_1(metrics_service):
    fields = [{"field_id": "f1"}, {"field_id": "f2"}]
    # FIX: calculate_metrics takes 10 keyword args — no "model" positional arg
    metrics = metrics_service.calculate_metrics(
        user_id="u1",
        session_id="s1",
        pdf_id="p1",
        submission_id="sub1",
        pdf_hash="hash1",
        rag_preds=_make_preds(fields),
        llm_preds=_make_preds(fields),
        final_preds=_make_final(fields),
        case_classification=_make_case_cls(fields),
        pdf_category={"category": "PE", "sub_category": "LP", "document_type": "Sub"},
    )
    assert metrics["accuracy"]["accuracy_ensemble"] == 1.0
    assert metrics["accuracy"]["accuracy_rag"] == 1.0


def test_metrics_recalculate_after_errors(metrics_service, tmp_path):
    fields = [{"field_id": "f1"}, {"field_id": "f2"}]
    rag_p = _make_preds(fields)
    llm_p = _make_preds(fields)
    fin_p = _make_final(fields, "rag")
    cc = _make_case_cls(fields)
    cat = {"category": "PE", "sub_category": "LP", "document_type": "Sub"}

    # First calculate and persist metrics + final_preds so recalculate can load them
    metrics = metrics_service.calculate_metrics(
        user_id="u1",
        session_id="s1",
        pdf_id="p1",
        submission_id="sub1",
        pdf_hash="hash1",
        rag_preds=rag_p,
        llm_preds=llm_p,
        final_preds=fin_p,
        case_classification=cc,
        pdf_category=cat,
    )
    # Persist the files that recalculate_accuracy_after_errors loads internally
    metrics_service.storage.save_json(
        "predictions/u1/s1/p1/analysis/metrics_snapshot.json", metrics
    )
    metrics_service.storage.save_json(
        "predictions/u1/s1/p1/predictions/final_predictions.json", fin_p
    )

    # FIX: recalculate_accuracy_after_errors takes (user_id, session_id, pdf_id, errors)
    # and loads metrics + final_preds from storage itself — no kwargs for those
    updated = metrics_service.recalculate_accuracy_after_errors(
        "u1",
        "s1",
        "p1",
        errors=[{"field_name": "mapped_f1"}],
    )
    assert updated["accuracy"]["errors_ensemble"] == 1
    assert updated["accuracy"]["accuracy_ensemble"] < 1.0
