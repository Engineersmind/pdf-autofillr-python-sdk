# tests/unit/test_storage.py
"""Unit tests for LocalStorage — no cloud deps, pure filesystem."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def tmp_storage(tmp_path):
    from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

    return LocalStorage(
        data_path=str(tmp_path / "data"), config_path=str(tmp_path / "configs")
    )


class TestLocalStorageJobState:
    def test_roundtrip(self, tmp_storage):
        tmp_storage.save_job_state("job1", {"status": "running", "step": 3})
        result = tmp_storage.get_job_state("job1")
        assert result["status"] == "running"
        assert result["step"] == 3

    def test_get_nonexistent_returns_none(self, tmp_storage):
        assert tmp_storage.get_job_state("missing_job") is None


class TestLocalStorageOutput:
    def test_nested_roundtrip(self, tmp_storage):
        data = {"name": "John", "address": {"city": "London"}}
        tmp_storage.save_output("job1", data)
        result = tmp_storage.get_output("job1")
        assert result["name"] == "John"
        assert result["address"]["city"] == "London"

    def test_flat_roundtrip(self, tmp_storage):
        flat = {"name": "Jane", "address.city": "Paris"}
        tmp_storage.save_output_flat("job1", flat)
        result = tmp_storage.get_output_flat("job1")
        assert result["address.city"] == "Paris"

    def test_get_output_missing_returns_none(self, tmp_storage):
        assert tmp_storage.get_output("no_such_job") is None


class TestLocalStorageExecutionLog:
    def test_roundtrip(self, tmp_storage):
        log = {"job_id": "j1", "steps": 5, "errors": []}
        tmp_storage.save_execution_log("j1", log)
        result = tmp_storage.get_execution_log("j1")
        assert result["steps"] == 5
        assert result["errors"] == []


class TestLocalStorageSchema:
    def test_load_schema_from_path(self, tmp_path):
        from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

        schema = {"field_a": "", "field_b": False}
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(json.dumps(schema))

        storage = LocalStorage(
            data_path=str(tmp_path / "data"), config_path=str(tmp_path)
        )
        loaded = storage.load_schema("schema.json")
        assert loaded["field_a"] == ""
        assert loaded["field_b"] is False

    def test_load_schema_absolute_path(self, tmp_path):
        from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

        schema = {"x": "val"}
        schema_file = tmp_path / "abs_schema.json"
        schema_file.write_text(json.dumps(schema))

        storage = LocalStorage(
            data_path=str(tmp_path / "data"), config_path=str(tmp_path)
        )
        loaded = storage.load_schema(str(schema_file))
        assert loaded["x"] == "val"


class TestLocalStorageDocument:
    def test_download_local_copies_file(self, tmp_path):
        from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

        src = tmp_path / "doc.txt"
        src.write_text("document content")
        dst = str(tmp_path / "copy.txt")

        storage = LocalStorage(data_path=str(tmp_path / "data"))
        result = storage.download_document(str(src), dst)
        assert result == dst
        assert open(dst).read() == "document content"

    def test_upload_copies_file(self, tmp_path):
        from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

        src = tmp_path / "output.json"
        src.write_text('{"k": "v"}')
        dst = str(tmp_path / "uploaded" / "output.json")

        storage = LocalStorage(data_path=str(tmp_path / "data"))
        assert storage.upload_file(str(src), dst) is True
        assert json.loads(open(dst).read())["k"] == "v"
