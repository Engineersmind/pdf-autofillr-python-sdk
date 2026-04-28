# tests/unit/test_noop_corrector.py
from ragpdf.correctors.noop_corrector import NoOpCorrectorBackend


def test_noop_cleans_field_name():
    c = NoOpCorrectorBackend()
    result = c.generate_corrected_field_name({"field_name": "Investor Full Name"})
    assert result["corrected_field_name"] == "investor_full_name"
    assert 0 < result["confidence"] <= 1.0
    assert "reasoning" in result


def test_noop_handles_empty():
    c = NoOpCorrectorBackend()
    result = c.generate_corrected_field_name({})
    assert result["corrected_field_name"] == "unknown_field"
