"""
Unit tests for SessionManager and _empty_session.

Covers Issue 9 fix: langchain_buffer removed from _empty_session.
"""

from chatbot.core.session import SessionManager, _empty_session
from chatbot.core.states import State


def test_empty_session_has_required_keys():
    session = _empty_session("u1", "s1")
    required = [
        "user_id",
        "session_id",
        "state",
        "investor_type",
        "live_fill_flat",
        "mandatory_flat",
        "fields_being_asked",
        "current_group",
        "pdf_path",
        "pdf_doc_id",
        "pdf_workflow_status",
        "conversation_log",
        "created_at",
        "updated_at",
    ]
    for key in required:
        assert key in session, f"Missing key: {key}"


def test_empty_session_no_langchain_buffer():
    """FIX Issue 9: langchain_buffer must NOT be in the empty session."""
    session = _empty_session("u1", "s1")
    assert "langchain_buffer" not in session, (
        "langchain_buffer should have been removed — it was a dead field "
        "with no corresponding storage methods."
    )


def test_empty_session_state_is_init():
    session = _empty_session("u1", "s1")
    assert session["state"] == State.INIT.value


def test_empty_session_pdf_path():
    session = _empty_session("u1", "s1", pdf_path="/tmp/form.pdf")
    assert session["pdf_path"] == "/tmp/form.pdf"


def test_empty_session_default_pdf_path_is_none():
    session = _empty_session("u1", "s1")
    assert session["pdf_path"] is None


def test_session_manager_create_new(local_storage):
    mgr = SessionManager(storage=local_storage)
    session = mgr.create_session("u1", "s1")
    assert session["user_id"] == "u1"
    assert session["session_id"] == "s1"
    assert session["state"] == State.INIT.value


def test_session_manager_create_is_idempotent(local_storage):
    """Creating the same session twice returns the existing one."""
    mgr = SessionManager(storage=local_storage)
    s1 = mgr.create_session("u1", "sess")
    s1["state"] = State.DATA_COLLECTION.value
    mgr.save("u1", "sess", s1)

    s2 = mgr.create_session("u1", "sess")
    assert s2["state"] == State.DATA_COLLECTION.value


def test_session_manager_load_or_create_creates_if_missing(local_storage):
    mgr = SessionManager(storage=local_storage)
    session = mgr.load_or_create("u1", "brand_new")
    assert session is not None
    assert session["state"] == State.INIT.value


def test_session_manager_save_updates_timestamp(local_storage):
    mgr = SessionManager(storage=local_storage)
    session = mgr.create_session("u1", "s1")
    old_ts = session["updated_at"]

    import time

    time.sleep(0.01)
    mgr.save("u1", "s1", session)
    reloaded = mgr.get("u1", "s1")
    assert reloaded["updated_at"] >= old_ts


def test_session_manager_delete(local_storage):
    mgr = SessionManager(storage=local_storage)
    mgr.create_session("u1", "s1")
    mgr.delete("u1", "s1")
    assert mgr.get("u1", "s1") is None
