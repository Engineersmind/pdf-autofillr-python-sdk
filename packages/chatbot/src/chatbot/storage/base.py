# chatbot/storage/base.py
"""
StorageBackend — abstract class all storage implementations extend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class StorageBackend(ABC):
    """
    Abstract interface for all storage backends.

    Implement this to plug in any storage system — PostgreSQL, MongoDB,
    Redis, GCS, Azure Blob, etc.
    """

    # ── Session state ──────────────────────────────────────────────────

    @abstractmethod
    def get_session_state(self, user_id: str, session_id: str) -> Optional[dict]: ...

    @abstractmethod
    def save_session_state(self, user_id: str, session_id: str, state: dict) -> bool: ...

    # ── User integrated info ───────────────────────────────────────────

    @abstractmethod
    def get_user_integrated_info(self, user_id: str) -> Optional[dict]: ...

    @abstractmethod
    def save_user_integrated_info(self, user_id: str, data: dict) -> bool: ...

    # ── Final output ───────────────────────────────────────────────────

    @abstractmethod
    def get_final_output(self, user_id: str, session_id: str) -> Optional[dict]: ...

    @abstractmethod
    def save_final_output(self, user_id: str, session_id: str, data: dict) -> bool: ...

    @abstractmethod
    def get_final_output_flat(self, user_id: str, session_id: str) -> Optional[dict]: ...

    @abstractmethod
    def save_final_output_flat(self, user_id: str, session_id: str, data: dict) -> bool: ...

    # ── Session history ────────────────────────────────────────────────

    @abstractmethod
    def get_session_history(self, user_id: str) -> Optional[list]: ...

    @abstractmethod
    def save_session_history(self, user_id: str, history: list) -> bool: ...

    # ── Conversation / debug logs ──────────────────────────────────────

    @abstractmethod
    def save_conversation_log(self, user_id: str, session_id: str, data: dict) -> bool: ...

    @abstractmethod
    def save_debug_conversation(self, user_id: str, session_id: str, data: dict) -> bool: ...

    @abstractmethod
    def get_debug_conversation(self, user_id: str, session_id: str) -> Optional[dict]: ...

    # ── PDF workflow logs ──────────────────────────────────────────────

    @abstractmethod
    def get_pdf_filling_logs(self, user_id: str, session_id: str) -> Optional[dict]: ...

    @abstractmethod
    def save_pdf_filling_logs(self, user_id: str, session_id: str, data: dict) -> bool: ...

    # ── Utility ────────────────────────────────────────────────────────

    @abstractmethod
    def list_user_sessions(self, user_id: str) -> List[str]: ...

    @abstractmethod
    def delete_session(self, user_id: str, session_id: str) -> bool: ...

    # ── Fill report ────────────────────────────────────────────────────

    @abstractmethod
    def save_fill_report(self, user_id: str, session_id: str, data: dict) -> bool: ...

    @abstractmethod
    def get_fill_report(self, user_id: str, session_id: str) -> Optional[dict]: ...

    # ── Config loaders (used by FormConfig.from_storage) ──────────────
    # FIX D: these were missing from the abstract contract. Both LocalStorage
    # and S3Storage already implement them, but without this declaration any
    # custom storage backend had no contract to follow and would fail silently
    # at runtime when FormConfig.from_storage() called storage.load_config().

    @abstractmethod
    def load_config(self, filename: str) -> dict: ...

    @abstractmethod
    def load_investor_type_config(self, filename: str) -> dict: ...