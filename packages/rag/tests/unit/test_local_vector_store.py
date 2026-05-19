# tests/unit/test_local_vector_store.py
import pytest
from ragpdf.vector_stores.local_vector_store import LocalVectorStore


@pytest.fixture
def store(tmp_path):
    return LocalVectorStore(path=str(tmp_path))


def test_empty_store_returns_no_match(store):
    result = store.find_similar([0.1] * 384, threshold=0.75, top_k=5)
    assert result["matched"] is False


def test_add_and_find(store):
    emb = [1.0] + [0.0] * 383
    vid = store.add_vector("investor_name", "name context", "identity", ["header1"], emb)
    assert vid.startswith("vec_")
    result = store.find_similar(emb, threshold=0.5, top_k=5)
    assert result["matched"] is True
    assert result["field_name"] == "investor_name"
    assert result["vector_id"] == vid


def test_update_confidence_positive(store):
    emb = [1.0] + [0.0] * 383
    vid = store.add_vector("test_field", "", "", [], emb)
    store.save()
    initial = store.data["vectors"][0]["confidence_history"][-1]
    new_conf = store.update_confidence(vid, is_positive=True)
    assert new_conf > initial


def test_update_confidence_negative(store):
    emb = [1.0] + [0.0] * 383
    vid = store.add_vector("test_field", "", "", [], emb)
    store.save()
    initial = store.data["vectors"][0]["confidence_history"][-1]
    new_conf = store.update_confidence(vid, is_positive=False)
    assert new_conf < initial


def test_count(store):
    assert store.count() == 0
    store.add_vector("f1", "", "", [], [0.1]*384)
    store.add_vector("f2", "", "", [], [0.2]*384)
    assert store.count() == 2
