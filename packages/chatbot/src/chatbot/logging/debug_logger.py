# chatbot/logging/debug_logger.py
"""Thread-safe per-session debug logger."""

from __future__ import annotations

import threading
import traceback
from datetime import datetime


class DebugLogger:
    """Thread-safe debug log for comprehensive session tracking."""

    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.entries: list[dict] = []
        self.started_at = datetime.now().isoformat()
        self._lock = threading.Lock()

    def log(
        self,
        category: str,
        message: str,
        level: str = "info",
        data: dict | None = None,
        exception: Exception | None = None,
    ) -> None:
        with self._lock:
            entry = {
                "entry_id": len(self.entries) + 1,
                "timestamp": datetime.now().isoformat(),
                "category": category,
                "level": level,
                "message": message,
            }
            if data:
                entry["data"] = data
            if exception:
                entry["exception"] = {
                    "type": type(exception).__name__,
                    "message": str(exception),
                    "traceback": traceback.format_exc(),
                }
            self.entries.append(entry)
            # Internal debug entries are written to debug_conversation.json only.
            # They are NOT printed to terminal — the local entrypoint handles
            # terminal output exclusively through its own terminal_log.json writer.

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "user_id": self.user_id,
                "session_id": self.session_id,
                "started_at": self.started_at,
                "total_entries": len(self.entries),
                "entries": list(self.entries),
            }

    def get_summary(self) -> dict:
        with self._lock:
            counts = {"info": 0, "warning": 0, "error": 0}
            for e in self.entries:
                counts[e.get("level", "info")] += 1
            return {"total": len(self.entries), **counts}
