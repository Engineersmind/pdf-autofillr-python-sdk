# pdf_autofillr_doc_upload/telemetry/collector.py
"""
TelemetryCollector — no-op if disabled, writes to local file or remote endpoint.

Modes:
  off      — all calls are no-ops (default)
  local    — append JSON events to {DOC_UPLOAD_TELEMETRY_PATH}/events.jsonl
  managed  — (stub) HTTP POST to DOC_UPLOAD_TELEMETRY_ENDPOINT
  self-hosted — (stub) same as managed with self-hosted endpoint

Privacy:
  - Field VALUES are never included in any event.
  - job_id is one-way SHA-256 hashed before transmission.
  - Only metadata (counts, latencies, file extensions) is logged.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pdf_autofillr_doc_upload.telemetry.config import TelemetryConfig


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


class TelemetryCollector:
    """
    Collects and ships telemetry events.

    Usage::

        from pdf_autofillr_doc_upload.telemetry import TelemetryCollector, TelemetryConfig

        # From env vars:
        collector = TelemetryCollector(TelemetryConfig())

        # Manual:
        collector = TelemetryCollector(TelemetryConfig(enabled=True, mode="local"))
        collector.record_job_start(job_id="abc", file_ext=".pdf")
        collector.record_job_complete(job_id="abc", duration=2.3, fields_extracted=42)
    """

    def __init__(self, config: Optional[TelemetryConfig] = None):
        self.config = config or TelemetryConfig()
        self._enabled = self.config.enabled
        self._mode = self.config.mode
        self._queue: deque = deque()
        self._lock = threading.Lock()
        self._debug = os.getenv("DOC_UPLOAD_DEBUG_LOGGING", "").lower() == "true"

        if self._enabled and self._mode == "local":
            Path(self.config.local_path).mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────

    def log(self, message: str) -> None:
        """Simple process log (always no-op here — use ExecutionLogger for that)."""
        pass

    def record_job_start(self, job_id: str, file_ext: str = "") -> None:
        if not self._enabled:
            return
        self._emit({
            "event": "job_start",
            "job_id_hash": _hash_id(job_id),
            "file_ext": file_ext,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    def record_job_complete(
        self,
        job_id: str,
        duration_seconds: float,
        fields_extracted: int,
        success: bool = True,
    ) -> None:
        if not self._enabled:
            return
        self._emit({
            "event": "job_complete",
            "job_id_hash": _hash_id(job_id),
            "duration_seconds": round(duration_seconds, 3),
            "fields_extracted": fields_extracted,
            "success": success,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    def record_extraction(
        self,
        job_id: str,
        model: str,
        latency_seconds: float,
        document_chars: int,
    ) -> None:
        if not self._enabled:
            return
        self._emit({
            "event": "extraction",
            "job_id_hash": _hash_id(job_id),
            "model": model,
            "latency_seconds": round(latency_seconds, 3),
            "document_chars": document_chars,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    # ── Internal ───────────────────────────────────────────────────────

    def _emit(self, event: dict) -> None:
        if self._mode == "local":
            self._write_local(event)
        elif self._mode in ("managed", "self-hosted", "self_hosted"):
            self._write_remote(event)

    def _write_local(self, event: dict) -> None:
        try:
            path = Path(self.config.local_path) / "events.jsonl"
            with self._lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, default=str) + "\n")
        except Exception as e:
            if self._debug:
                print(f"⚠️ Telemetry local write failed: {e}")

    def _write_remote(self, event: dict) -> None:
        # Stub — implement HTTP POST to self.config.endpoint
        pass
