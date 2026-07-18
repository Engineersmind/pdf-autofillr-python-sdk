# tests/unit/test_local_storage.py

import os

import pytest

from ragpdf.storage.local_storage import LocalStorage, PathAccessError


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


# ── Path traversal / symlink escape (CWE-22) ────────────────────────────────


def test_save_json_rejects_dotdot_traversal(storage):
    with pytest.raises(PathAccessError):
        storage.save_json("../../../etc/evil.json", {"pwned": True})


def test_load_json_rejects_dotdot_traversal(storage):
    with pytest.raises(PathAccessError):
        storage.load_json("../../../etc/passwd")


def test_load_jsonl_rejects_dotdot_traversal(storage):
    with pytest.raises(PathAccessError):
        storage.load_jsonl("../../../etc/passwd")


def test_copy_file_rejects_dotdot_traversal(storage):
    with pytest.raises(PathAccessError):
        storage.copy_file("../../../etc/passwd", "safe/dest.json")


def test_rejects_absolute_path_outside_data_path(storage, tmp_path):
    outside = tmp_path.parent / "outside.json"
    with pytest.raises(PathAccessError):
        storage.save_json(str(outside), {"pwned": True})


def test_legitimate_multi_segment_key_still_works(storage):
    # Keys are legitimately deep, e.g. predictions/{user_id}/{session_id}/
    # {pdf_id}/metadata.json — confinement must not reject normal nesting.
    key = "predictions/user123/session456/pdf789/metadata.json"
    storage.save_json(key, {"ok": True})
    assert storage.load_json(key) == {"ok": True}


def test_symlink_escape_is_rejected(storage, tmp_path):
    # A symlink *inside* data_path whose target points *outside* it. The
    # symlink's own name is a perfectly ordinary, single-segment key with
    # no ".." or "/" in it — only following the symlink (which
    # Path.resolve() does, and os.path.normpath deliberately does not)
    # reveals that it escapes data_path. This is exactly the CWE-22
    # variant that motivated using resolve() instead of normpath.
    outside_dir = tmp_path.parent / "outside_target"
    outside_dir.mkdir()
    (outside_dir / "secret.json").write_text('{"leaked": true}')

    escape_link = tmp_path / "evil_link"
    try:
        escape_link.symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported in this test environment")

    with pytest.raises(PathAccessError):
        storage.load_json("evil_link/secret.json")
