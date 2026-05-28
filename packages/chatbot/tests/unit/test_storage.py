"""
Unit tests for LocalStorage backend.

Tests all CRUD operations defined in StorageBackend against
the LocalStorage implementation using a temp directory.
"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def storage(temp_dir):
    from chatbot.storage.local_storage import LocalStorage

    return LocalStorage(
        data_path=str(temp_dir / "data"),
        config_path=str(temp_dir / "configs"),
    )


# ── session state ──────────────────────────────────────────────────────


def test_save_and_get_session_state(storage):
    state = {"state": "INIT", "live_fill_flat": {}}
    storage.save_session_state("u1", "s1", state)
    loaded = storage.get_session_state("u1", "s1")
    assert loaded["state"] == "INIT"


def test_get_session_state_missing_returns_none(storage):
    assert storage.get_session_state("nobody", "nosession") is None


def test_save_session_state_overwrites(storage):
    storage.save_session_state("u1", "s1", {"state": "INIT"})
    storage.save_session_state("u1", "s1", {"state": "DATA_COLLECTION"})
    loaded = storage.get_session_state("u1", "s1")
    assert loaded["state"] == "DATA_COLLECTION"


# ── user integrated info ───────────────────────────────────────────────


def test_save_and_get_user_integrated_info(storage):
    data = {"full_name": "Alice", "email": "alice@test.com"}
    storage.save_user_integrated_info("u1", data)
    loaded = storage.get_user_integrated_info("u1")
    assert loaded["full_name"] == "Alice"


def test_user_integrated_info_missing_returns_none(storage):
    assert storage.get_user_integrated_info("nobody") is None


# ── final output ───────────────────────────────────────────────────────


def test_save_and_get_final_output(storage):
    data = {"name": {"first": "Alice"}}
    storage.save_final_output("u1", "s1", data)
    assert storage.get_final_output("u1", "s1") == data


def test_save_and_get_final_output_flat(storage):
    data = {"full_name": "Alice", "email": "alice@test.com"}
    storage.save_final_output_flat("u1", "s1", data)
    loaded = storage.get_final_output_flat("u1", "s1")
    assert loaded["full_name"] == "Alice"


# ── conversation log ───────────────────────────────────────────────────


def test_save_conversation_log(storage):
    """Issue 7 fix: save_conversation_log must persist to its own file."""
    log = [{"turn": 1, "user": "Hello", "bot": "Hi!"}]
    result = storage.save_conversation_log("u1", "s1", log)
    assert result is True

    # Verify the file was actually written
    session_dir = Path(storage.data_path) / "u1" / "sessions" / "s1"
    log_file = session_dir / "conversation_log.json"
    assert log_file.exists(), "conversation_log.json was not created"
    content = json.loads(log_file.read_text())
    assert content[0]["user"] == "Hello"


# ── debug conversation ─────────────────────────────────────────────────


def test_save_and_get_debug_conversation(storage):
    debug = {"entries": [{"level": "info", "message": "test"}]}
    storage.save_debug_conversation("u1", "s1", debug)
    loaded = storage.get_debug_conversation("u1", "s1")
    assert loaded["entries"][0]["message"] == "test"


# ── pdf filling logs ───────────────────────────────────────────────────


def test_save_and_get_pdf_filling_logs(storage):
    logs = {"steps": [{"step": "prepare", "status": "complete"}]}
    storage.save_pdf_filling_logs("u1", "s1", logs)
    loaded = storage.get_pdf_filling_logs("u1", "s1")
    assert loaded["steps"][0]["step"] == "prepare"


# ── fill report ────────────────────────────────────────────────────────


def test_save_and_get_fill_report(storage):
    report = {"summary": {"total_fields_filled": 10, "fill_rate_pct": 80.0}}
    storage.save_fill_report("u1", "s1", report)
    loaded = storage.get_fill_report("u1", "s1")
    assert loaded["summary"]["fill_rate_pct"] == 80.0


# ── list / delete sessions ─────────────────────────────────────────────


def test_list_user_sessions(storage):
    storage.save_session_state("u1", "s1", {"state": "INIT"})
    storage.save_session_state("u1", "s2", {"state": "INIT"})
    sessions = storage.list_user_sessions("u1")
    assert set(sessions) >= {"s1", "s2"}


def test_delete_session(storage):
    storage.save_session_state("u1", "s1", {"state": "INIT"})
    storage.delete_session("u1", "s1")
    assert storage.get_session_state("u1", "s1") is None
