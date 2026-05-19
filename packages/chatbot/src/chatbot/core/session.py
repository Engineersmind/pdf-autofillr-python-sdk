# chatbot/core/session.py
"""
SessionManager — CRUD only.  No business logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from chatbot.core.states import State
from chatbot.storage.base import StorageBackend


def _empty_session(user_id: str, session_id: str, pdf_path: Optional[str] = None) -> dict:
    return {
        "user_id": user_id,
        "session_id": session_id,
        "state": State.INIT.value,          # store plain string, not enum object
        "investor_type": None,
        "live_fill_flat": {},
        "mandatory_flat": {},
        "fields_being_asked": [],
        "current_group": None,
        "pdf_path": pdf_path,
        "pdf_doc_id": None,
        "pdf_workflow_status": None,
        "conversation_log": [],
        # FIX: removed "langchain_buffer" — it was initialised here but never
        # read or written through storage (no save_langchain_buffer /
        # get_langchain_buffer methods exist on StorageBackend).  Keeping it
        # was dead weight that created confusion about what was actually
        # persisted.  LangChain message history is reconstructed from
        # conversation_log when needed.
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


class SessionManager:
    """Thin wrapper around StorageBackend for session CRUD."""

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    def create_session(
        self,
        user_id: str,
        session_id: str,
        pdf_path: Optional[str] = None,
    ) -> dict:
        existing = self.storage.get_session_state(user_id, session_id)
        if existing:
            return existing
        session = _empty_session(user_id, session_id, pdf_path)
        self.storage.save_session_state(user_id, session_id, session)
        return session

    def load_or_create(
        self,
        user_id: str,
        session_id: str,
        pdf_path: Optional[str] = None,
    ) -> dict:
        session = self.storage.get_session_state(user_id, session_id)
        if session is None:
            session = self.create_session(user_id, session_id, pdf_path)
        return session

    def save(self, user_id: str, session_id: str, session: dict) -> None:
        session["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.storage.save_session_state(user_id, session_id, session)

    def get(self, user_id: str, session_id: str) -> Optional[dict]:
        return self.storage.get_session_state(user_id, session_id)

    def delete(self, user_id: str, session_id: str) -> bool:
        return self.storage.delete_session(user_id, session_id)
