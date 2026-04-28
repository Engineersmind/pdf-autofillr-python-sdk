# tests/unit/test_case_classifier.py
import pytest
from ragpdf.services.case_classifier import CaseClassifier
from ragpdf.utils.constants import CASE_A, CASE_B, CASE_C, CASE_D, CASE_E


@pytest.fixture
def clf():
    return CaseClassifier()


def _pred(name, conf=0.90):
    return {"predicted_field_name": name, "confidence": conf}


def test_case_a_both_agree(clf):
    rag = {"f1": _pred("investor_name"), "f2": _pred("investor_email")}
    llm = {"f1": _pred("investor_name"), "f2": _pred("investor_email")}
    fin = {"f1": {"selected_field_name": "investor_name", "selected_from": "rag"},
           "f2": {"selected_field_name": "investor_email", "selected_from": "rag"}}
    r = clf.classify("u", "s", "p", rag, llm, fin)
    assert r["case_breakdown"][CASE_A]["count"] == 2
    assert r["case_breakdown"][CASE_B]["count"] == 0


def test_case_b_conflict(clf):
    rag = {"f1": _pred("investor_name")}
    llm = {"f1": _pred("full_legal_name")}
    fin = {"f1": {"selected_field_name": "full_legal_name", "selected_from": "llm"}}
    r = clf.classify("u", "s", "p", rag, llm, fin)
    assert r["case_breakdown"][CASE_B]["count"] == 1
    assert r["case_breakdown"][CASE_B]["selections"]["llm_selected"] == 1


def test_case_c_llm_only(clf):
    rag = {"f1": None}
    llm = {"f1": _pred("tax_id")}
    fin = {"f1": {"selected_field_name": "tax_id", "selected_from": "llm"}}
    r = clf.classify("u", "s", "p", rag, llm, fin)
    assert r["case_breakdown"][CASE_C]["count"] == 1


def test_case_d_rag_only(clf):
    rag = {"f1": _pred("address_line1")}
    llm = {"f1": None}
    fin = {"f1": {"selected_field_name": "address_line1", "selected_from": "rag"}}
    r = clf.classify("u", "s", "p", rag, llm, fin)
    assert r["case_breakdown"][CASE_D]["count"] == 1


def test_case_e_neither(clf):
    rag = {"f1": {"predicted_field_name": "name", "confidence": 0.3}}  # below threshold
    llm = {"f1": None}
    fin = {"f1": None}
    r = clf.classify("u", "s", "p", rag, llm, fin)
    assert r["case_breakdown"][CASE_E]["count"] == 1


def test_total_fields(clf):
    rag = {f"f{i}": _pred(f"field_{i}") for i in range(5)}
    llm = {f"f{i}": _pred(f"field_{i}") for i in range(5)}
    fin = {f"f{i}": {"selected_field_name": f"field_{i}", "selected_from": "rag"} for i in range(5)}
    r = clf.classify("u", "s", "p", rag, llm, fin)
    total = sum(cb["count"] for cb in r["case_breakdown"].values())
    assert total == r["total_fields"] == 5
