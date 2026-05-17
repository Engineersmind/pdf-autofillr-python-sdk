# tests/unit/test_helpers.py
from ragpdf.utils.helpers import generate_vector_id, calculate_avg


def test_generate_vector_id_empty():
    assert generate_vector_id([]) == "vec_001"


def test_generate_vector_id_sequential():
    existing = [{"vector_id": "vec_001"}, {"vector_id": "vec_005"}]
    assert generate_vector_id(existing) == "vec_006"


def test_calculate_avg_empty():
    assert calculate_avg([]) == 0.0


def test_calculate_avg_normal():
    assert calculate_avg([0.8, 0.9, 1.0]) == pytest.approx(0.9, rel=1e-4)


import pytest
