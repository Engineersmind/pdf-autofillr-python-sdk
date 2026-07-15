# chatbot/storage/local_storage.py
"""
LocalStorage — filesystem backend. Ideal for development and self-hosted deployments.

File layout::

    {data_path}/
    ├── {user_id}/
    │   ├── user_integrated_information.json
    │   ├── session_history.json
    │   └── sessions/
    │       └── {session_id}/
    │           ├── session_state.json
    │           ├── live_fill.json
    │           ├── final_output.json
    │           ├── final_output_flat.json
    │           ├── conversation_log.json
    │           ├── langchain_buffer.json
    │           ├── debug_conversation.json
    │           └── calling_filling_logs.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chatbot.storage.base import StorageBackend


class PathAccessError(PermissionError):
    """Raised when a user_id/session_id would escape the data directory."""


class LocalStorage(StorageBackend):
    """
    Stores all data as JSON files on the local filesystem.

    Args:
        data_path:   Root directory for session and user data.
        config_path: Directory containing form config JSON files (read-only).
    """

    def __init__(
        self, data_path: str = "./data/chatbot", config_path: str = "./configs"
    ):
        self.data_path = Path(data_path).resolve()
        self.config_path = Path(config_path).resolve()
        self.data_path.mkdir(parents=True, exist_ok=True)

    # ── Paths ──────────────────────────────────────────────────────────

    @staticmethod
    def _safe_segment(value: str, *, label: str) -> str:
        """
        user_id/session_id become literal path segments. Reject anything
        that isn't a plain single segment (no "/", "\\", or ".." tricks) so
        these identifiers can never be used to escape data_path
        (CWE-22 path traversal).
        """
        segment = Path(value).name
        if not segment or segment != value or segment in (".", ".."):
            raise PathAccessError(f"Invalid {label}: {value!r}")
        return segment

    def _user_dir(self, user_id: str) -> Path:
        safe_user_id = self._safe_segment(user_id, label="user_id")
        p = self.data_path / safe_user_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _session_dir(self, user_id: str, session_id: str) -> Path:
        safe_session_id = self._safe_segment(session_id, label="session_id")
        p = self._user_dir(user_id) / "sessions" / safe_session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── JSON helpers ───────────────────────────────────────────────────

    def _read(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, path: Path, data: Any) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            print(f"❌ LocalStorage write error {path}: {e}")
            return False

    # ── Session state ──────────────────────────────────────────────────

    def get_session_state(self, user_id, session_id):
        return self._read(self._session_dir(user_id, session_id) / "session_state.json")

    def save_session_state(self, user_id, session_id, state):
        return self._write(
            self._session_dir(user_id, session_id) / "session_state.json", state
        )

    # ── User integrated info ───────────────────────────────────────────

    def get_user_integrated_info(self, user_id):
        data = self._read(self._user_dir(user_id) / "user_integrated_information.json")
        return data.get("data", data) if isinstance(data, dict) else data

    def save_user_integrated_info(self, user_id, data):
        wrapped = {"user_id": user_id, "data": data}
        return self._write(
            self._user_dir(user_id) / "user_integrated_information.json", wrapped
        )

    # ── Final output ───────────────────────────────────────────────────

    def get_final_output(self, user_id, session_id):
        return self._read(self._session_dir(user_id, session_id) / "final_output.json")

    def save_final_output(self, user_id, session_id, data):
        return self._write(
            self._session_dir(user_id, session_id) / "final_output.json", data
        )

    def get_final_output_flat(self, user_id, session_id):
        return self._read(
            self._session_dir(user_id, session_id) / "final_output_flat.json"
        )

    def save_final_output_flat(self, user_id, session_id, data):
        return self._write(
            self._session_dir(user_id, session_id) / "final_output_flat.json", data
        )

    # ── Session history ────────────────────────────────────────────────

    def get_session_history(self, user_id):
        return self._read(self._user_dir(user_id) / "session_history.json")

    def save_session_history(self, user_id, history):
        return self._write(self._user_dir(user_id) / "session_history.json", history)

    # ── Logs ───────────────────────────────────────────────────────────

    def save_conversation_log(self, user_id, session_id, data):
        return self._write(
            self._session_dir(user_id, session_id) / "conversation_log.json", data
        )

    def save_debug_conversation(self, user_id, session_id, data):
        return self._write(
            self._session_dir(user_id, session_id) / "debug_conversation.json", data
        )

    def get_debug_conversation(self, user_id, session_id):
        return self._read(
            self._session_dir(user_id, session_id) / "debug_conversation.json"
        )

    def get_pdf_filling_logs(self, user_id, session_id):
        return self._read(
            self._session_dir(user_id, session_id) / "calling_filling_logs.json"
        )

    def save_pdf_filling_logs(self, user_id, session_id, data):
        return self._write(
            self._session_dir(user_id, session_id) / "calling_filling_logs.json", data
        )

    # ── Fill report ────────────────────────────────────────────────────

    def get_fill_report(self, user_id, session_id):
        return self._read(self._session_dir(user_id, session_id) / "fill_report.json")

    def save_fill_report(self, user_id, session_id, data):
        return self._write(
            self._session_dir(user_id, session_id) / "fill_report.json", data
        )

    # ── Utility ────────────────────────────────────────────────────────

    def list_user_sessions(self, user_id):
        sessions_dir = self._user_dir(user_id) / "sessions"
        if not sessions_dir.exists():
            return []
        return [p.name for p in sessions_dir.iterdir() if p.is_dir()]

    def delete_session(self, user_id, session_id):
        import shutil

        session_dir = self._session_dir(user_id, session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
        return True

    # ── Config file loaders (used by FormConfig) ───────────────────────

    def load_config(self, filename: str) -> dict:
        path = self.config_path / filename
        data = self._read(path)
        if data is None:
            raise FileNotFoundError(f"Config file not found: {path}")
        return data

    def load_investor_type_config(self, filename: str) -> dict:
        path = self.config_path / "global_investor_type_keys" / filename
        data = self._read(path)
        if data is None:
            # fallback to base form_keys
            return self.load_config("form_keys.json")
        return data
