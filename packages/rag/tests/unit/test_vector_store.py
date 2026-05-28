# tests/unit/test_vector_store.py
import pytest

from ragpdf.vector_stores.local_vector_store import LocalVectorStore


@pytest.fixture
def store(tmp_path):
    # FIX: LocalVectorStore takes a folder path, not a file path.
    # It appends "vectors/vector_database.json" internally.
    return LocalVectorStore(path=str(tmp_path))


def make_embedding(val: float, dim: int = 4) -> list:
    return [val] * dim


def test_empty_store_returns_no_match(store):
    # FIX: find_similar() returns a plain dict, not an object with attribute access.
    match = store.find_similar([0.1, 0.2, 0.3, 0.4], threshold=0.75, top_k=5)
    assert match["matched"] is False
    assert match["confidence"] == 0.0


def test_add_and_find_vector(store):
    embedding = make_embedding(1.0)
    # FIX: add_vector() does not accept initial_confidence as a kwarg —
    # it always starts at 0.75 (from config). Pass only the documented args.
    vid = store.add_vector(
        "investor_name", "Name field", "Identity", ["Investor"], embedding
    )
    store.save()

    match = store.find_similar(make_embedding(1.0), threshold=0.75, top_k=5)
    assert match["matched"] is True
    assert match["field_name"] == "investor_name"
    assert match["vector_id"] == vid
    assert match["confidence"] >= 0.99


def test_below_threshold_no_match(store):
    store.add_vector("investor_name", "", "", [], make_embedding(1.0))
    # A zero vector has undefined cosine similarity to a unit vector — use a
    # clearly orthogonal embedding in the same small dimension space.
    match = store.find_similar([0.0, 0.0, 0.0, 1.0], threshold=0.99, top_k=5)
    assert match["matched"] is False
    assert match["best_candidate"] == "investor_name"


def test_confidence_boost(store):
    # FIX: update_confidence() uses settings constants, not passed-in rates.
    # Just verify the new value is *higher* than the starting value.
    vid = store.add_vector("investor_name", "", "", [], make_embedding(1.0))
    initial = store.data["vectors"][0]["confidence_history"][-1]
    new_conf = store.update_confidence(vid, is_positive=True)
    assert new_conf > initial


def test_confidence_decay(store):
    vid = store.add_vector("investor_name", "", "", [], make_embedding(1.0))
    initial = store.data["vectors"][0]["confidence_history"][-1]
    new_conf = store.update_confidence(vid, is_positive=False)
    assert new_conf < initial


def test_confidence_clamped_to_min(store):
    from ragpdf.config.settings import MIN_CONFIDENCE

    vid = store.add_vector("investor_name", "", "", [], make_embedding(1.0))
    for _ in range(200):
        new_conf = store.update_confidence(vid, is_positive=False)
    assert new_conf >= MIN_CONFIDENCE


def test_confidence_clamped_to_max(store):
    from ragpdf.config.settings import MAX_CONFIDENCE

    vid = store.add_vector("investor_name", "", "", [], make_embedding(1.0))
    for _ in range(200):
        new_conf = store.update_confidence(vid, is_positive=True)
    assert new_conf <= MAX_CONFIDENCE


def test_update_nonexistent_vector_returns_none(store):
    result = store.update_confidence("vec_999", is_positive=True)
    assert result is None


def test_top_k_results(store):
    for i in range(5):
        store.add_vector(f"field_{i}", "", "", [], make_embedding(float(i + 1) / 10.0))
    match = store.find_similar(make_embedding(0.4), threshold=0.0, top_k=3)
    # FIX: access top_k via dict key, not attribute
    assert len(match["top_k"]) == 3


def test_persist_and_reload(tmp_path):
    store1 = LocalVectorStore(path=str(tmp_path))
    store1.add_vector(
        "investor_name", "context", "section", ["h1"], make_embedding(1.0)
    )
    store1.save()

    store2 = LocalVectorStore(path=str(tmp_path))
    # FIX: method is count(), not total_vectors().
    # Access vectors list directly for content checks.
    assert store2.count() == 1
    assert store2.data["vectors"][0]["field_name"] == "investor_name"


def test_count(store):
    # FIX: method is count(), not total_vectors()
    assert store.count() == 0
    store.add_vector("f1", "", "", [], make_embedding(1.0))
    store.add_vector("f2", "", "", [], make_embedding(0.5))
    assert store.count() == 2
