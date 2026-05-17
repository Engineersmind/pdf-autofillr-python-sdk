# chatbot/telemetry/collector.py
"""
TelemetryCollector — no-op if disabled, fires async HTTP events if enabled.

Privacy guarantee:
  - Field VALUES are NEVER included in any event.
  - User/session IDs are one-way SHA-256 hashed before transmission.
  - Only metadata (counts, latencies, states, field keys) is sent.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from chatbot.telemetry.config import TelemetryConfig
from chatbot.telemetry.document_context import DocumentContext


def _hash_id(value: str) -> str:
    """One-way SHA-256 hash for user/session IDs."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


class TelemetryCollector:
    """
    Collects and ships telemetry events.

    Events are queued in-memory and flushed in a background thread
    using aiohttp (already in pyproject.toml dependencies).
    When telemetry is disabled, all calls are no-ops with zero overhead.
    """

    def __init__(
        self,
        config: Optional[TelemetryConfig] = None,
        document_context: Optional[DocumentContext] = None,
    ):
        self.config = config
        self.document_context = document_context
        self._enabled = bool(config and config.enabled)
        self._endpoint = config.endpoint if config else ""
        self._api_key = config.sdk_api_key if config else ""
        self._batch_size = config.batch_size if config and hasattr(config, "batch_size") else 10

        import os
        self._debug = os.getenv("chatbot_DEBUG_LOGGING", "").lower() == "true"

        # In-memory queue + background flush thread
        self._queue: deque = deque()
        self._lock = threading.Lock()

        if self._enabled and self._endpoint:
            flush_interval = (
                config.flush_interval_seconds
                if config and hasattr(config, "flush_interval_seconds")
                else 30
            )
            self._start_flush_thread(flush_interval)

    # ------------------------------------------------------------------
    # Public tracking methods
    # ------------------------------------------------------------------

    def track_extraction(
        self,
        user_id: str,
        session_id: str,
        fields_extracted: int,
        fields_attempted: int,
        latency: float,
        method: str,
        prompt_version: str = "v1",
        hallucination_detected: bool = False,
    ) -> None:
        if not self._enabled:
            return
        self._emit("extraction_result", user_id, session_id, {
            "fields_extracted": fields_extracted,
            "fields_attempted": fields_attempted,
            "latency_ms": int(latency * 1000),
            "method": method,
            "prompt_version": prompt_version,
            "hallucination_detected": hallucination_detected,
        })

    def track_state_transition(
        self,
        from_state: str,
        to_state: str,
        turn_number: int,
        latency: float,
        user_id: str = "",
        session_id: str = "",
    ) -> None:
        if not self._enabled:
            return
        self._emit("state_transition", user_id, session_id, {
            "from_state": from_state,
            "to_state": to_state,
            "turn_number": turn_number,
            "latency_ms": int(latency * 1000),
        })

    def track_session_complete(
        self,
        user_id: str,
        session_id: str,
        total_turns: int,
        duration_seconds: float,
        mandatory_pct: float,
        optional_pct: float,
    ) -> None:
        if not self._enabled:
            return
        self._emit("session_complete", user_id, session_id, {
            "total_turns": total_turns,
            "duration_seconds": round(duration_seconds, 1),
            "mandatory_completion_pct": round(mandatory_pct, 2),
            "optional_completion_pct": round(optional_pct, 2),
        })

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, user_id: str, session_id: str, payload: dict) -> None:
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id_hash": _hash_id(user_id) if user_id else None,
            "session_id_hash": _hash_id(session_id) if session_id else None,
            **payload,
        }
        if self.document_context:
            event.update(self.document_context.to_dict())

        if self._debug:
            print(f"[TELEMETRY] {event_type}: {payload}")

        if self._enabled and self._endpoint:
            with self._lock:
                self._queue.append(event)
                if len(self._queue) >= self._batch_size:
                    self._flush_nowait()

    def _flush_nowait(self) -> None:
        """Pull current queue and fire-and-forget in a new thread."""
        if not self._queue:
            return
        with self._lock:
            batch = list(self._queue)
            self._queue.clear()

        threading.Thread(
            target=self._send_batch,
            args=(batch,),
            daemon=True,
        ).start()

    def _send_batch(self, batch: list) -> None:
        """Synchronous wrapper — runs in a daemon thread."""
        try:
            asyncio.run(self._send_batch_async(batch))
        except Exception as e:
            if self._debug:
                print(f"[TELEMETRY] Send error: {e}")

    async def _send_batch_async(self, batch: list) -> None:
        """POST batch to configured endpoint using aiohttp."""
        try:
            import aiohttp
        except ImportError:
            if self._debug:
                print("[TELEMETRY] aiohttp not installed — events dropped")
            return

        headers = {
            "Content-Type": "application/json",
            "X-chatbot-SDK-Key": self._api_key,
        }
        payload = json.dumps({"events": batch}, default=str)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._endpoint,
                    data=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if self._debug:
                        print(f"[TELEMETRY] Sent {len(batch)} events -> HTTP {resp.status}")
        except Exception as e:
            if self._debug:
                print(f"[TELEMETRY] Failed to send batch: {e}")

    def _start_flush_thread(self, interval_seconds: int) -> None:
        """Background thread that flushes the queue on a timer."""
        def _loop():
            import time
            while True:
                time.sleep(interval_seconds)
                try:
                    self._flush_nowait()
                except Exception:
                    pass

        t = threading.Thread(target=_loop, daemon=True)
        t.start()