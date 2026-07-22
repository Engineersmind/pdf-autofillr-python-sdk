# tests/unit/test_helpers.py
from ragpdf.utils.helpers import calculate_avg, generate_vector_id, safe_for_log


def test_generate_vector_id_empty():
    assert generate_vector_id([]) == "vec_001"


def test_generate_vector_id_sequential():
    existing = [{"vector_id": "vec_001"}, {"vector_id": "vec_005"}]
    assert generate_vector_id(existing) == "vec_006"


def test_calculate_avg_empty():
    assert calculate_avg([]) == 0.0


def test_calculate_avg_normal():
    assert calculate_avg([0.8, 0.9, 1.0]) == pytest.approx(0.9, rel=1e-4)


import pytest  # noqa: E402


def test_safe_for_log_no_special_chars():
    assert safe_for_log("alice") == "alice"


def test_safe_for_log_newline():
    assert safe_for_log("a\nb") == "a\\nb"


def test_safe_for_log_carriage_return():
    assert safe_for_log("a\rb") == "a\\rb"


def test_safe_for_log_crlf():
    assert safe_for_log("a\r\nb") == "a\\r\\nb"


def test_safe_for_log_mixed_lf_then_cr():
    # LF followed by CR (not a CRLF pair) — each character escaped in turn.
    assert safe_for_log("a\n\rb") == "a\\n\\rb"


def test_safe_for_log_forged_log_line():
    malicious = "alice\n2026-01-01 00:00:00 CRITICAL Fake admin login succeeded"
    result = safe_for_log(malicious)
    assert "\n" not in result
    assert result == (
        "alice\\n2026-01-01 00:00:00 CRITICAL Fake admin login succeeded"
    )


def test_safe_for_log_non_string_input():
    # Callers may pass non-string values (e.g. an int count) — must not
    # raise, and must still return a str.
    assert safe_for_log(42) == "42"
