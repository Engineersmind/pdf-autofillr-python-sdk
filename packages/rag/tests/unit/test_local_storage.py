# tests/unit/test_local_storage.py
import os, json, tempfile, pytest
from ragpdf.storage.local_storage import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(data_path=str(tmp_path))


def test_save_and_load(storage):
    storage.save_json("test/data.json", {"key": "value"})
    result = storage.load_json("test/data.json")
    assert result == {"key": "value"}


def test_load_missing_returns_none(storage):
    assert storage.load_json("does/not/exist.json") is None


def test_append_and_load_jsonl(storage):
    storage.append_to_jsonl("test/feed.jsonl", {"a": 1})
    storage.append_to_jsonl("test/feed.jsonl", {"a": 2})
    lines = storage.load_jsonl("test/feed.jsonl")
    assert len(lines) == 2
    assert lines[0] == {"a": 1}
    assert lines[1] == {"a": 2}


def test_load_jsonl_missing_returns_empty(storage):
    assert storage.load_jsonl("missing.jsonl") == []
