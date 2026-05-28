# pdf_autofillr_doc_upload/logging/logger.py
"""
ExecutionLogger — comprehensive logger for all API calls and processing steps.

Ports Lambda logger_utils.py into a standalone class that works in any
deployment (local, AWS Lambda, GCP, Azure) without boto3 dependency at
the class level — S3 persistence is called explicitly only when needed.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any


class ExecutionLogger:
    """
    Tracks every API request, response, processing step, and error
    for a single extraction job.

    Usage::

        logger = ExecutionLogger(job_id="abc123")
        logger.log("📄 Reading document...")
        logger.log_api_request("make_embed_file", url, headers, payload)
        logger.log_api_response("make_embed_file", 200, data, 1.23)
        logger.log_error("Something failed", exception=e)
        summary = logger.get_summary()
    """

    def __init__(self, job_id: str | None = None):
        self.job_id = job_id or "unknown"
        self._data: dict = {
            "job_id": self.job_id,
            "started_at": datetime.now(timezone.utc).isoformat() + "Z",
            "api_calls": [],
            "process_logs": [],
            "errors": [],
        }

    # ── Process steps ──────────────────────────────────────────────────

    def log(self, message: str) -> None:
        """Log a processing step or status message."""
        ts = datetime.now(timezone.utc).isoformat() + "Z"
        print(message)
        self._data["process_logs"].append({"timestamp": ts, "message": message})

    # ── API calls ──────────────────────────────────────────────────────

    def log_api_request(
        self,
        operation: str,
        url: str,
        headers: dict,
        payload: dict,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat() + "Z"
        print(f"\n{'-'*60}\n📤 API REQUEST: {operation}\n{'-'*60}")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        self._data["api_calls"].append(
            {
                "type": "request",
                "timestamp": ts,
                "operation": operation,
                "url": url,
                "headers": headers,
                "payload": payload,
            }
        )

    def log_api_response(
        self,
        operation: str,
        status_code: int,
        response_data: Any,
        duration_seconds: float,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat() + "Z"
        print(f"📥 API RESPONSE: {operation}  [{status_code}]  {duration_seconds}s")
        self._data["api_calls"].append(
            {
                "type": "response",
                "timestamp": ts,
                "operation": operation,
                "status_code": status_code,
                "response_data": response_data,
                "duration_seconds": duration_seconds,
            }
        )

    # ── Errors ─────────────────────────────────────────────────────────

    def log_error(
        self,
        message: str,
        details: dict | None = None,
        exception: Exception | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat() + "Z"
        entry: dict = {"timestamp": ts, "message": message}
        if details:
            entry["details"] = details
        if exception:
            entry["exception_type"] = type(exception).__name__
            entry["exception_message"] = str(exception)
            entry["traceback"] = traceback.format_exc()

        print(f"\n{'!'*60}\n❌ ERROR: {message}\n{'!'*60}")
        if details:
            print(json.dumps(details, indent=2, default=str))
        self._data["errors"].append(entry)

    # ── Input / output snapshots ───────────────────────────────────────

    def log_input_request(self, body: dict) -> None:
        print(f"\n{'='*60}\n📥 INCOMING REQUEST\n{'='*60}")
        print(json.dumps(body, indent=2, default=str))
        self._data["input_request"] = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "body": body,
        }

    def log_output_response(self, body: dict) -> None:
        print(f"\n{'='*60}\n📤 OUTGOING RESPONSE\n{'='*60}")
        print(json.dumps(body, indent=2, default=str))
        self._data["output_response"] = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "body": body,
        }

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        data = dict(self._data)
        data["summary"] = {
            "total_api_calls": len(
                [c for c in self._data["api_calls"] if c["type"] == "request"]
            ),
            "total_process_logs": len(self._data["process_logs"]),
            "total_errors": len(self._data["errors"]),
            "success": len(self._data["errors"]) == 0,
        }
        return data

    def print_summary(self) -> None:
        s = self.get_summary()["summary"]
        print(f"\n{'='*60}\n📊 EXECUTION SUMMARY\n{'='*60}")
        print(f"API Calls  : {s['total_api_calls']}")
        print(f"Steps      : {s['total_process_logs']}")
        print(f"Errors     : {s['total_errors']}")
        print(f"Success    : {'✅ YES' if s['success'] else '❌ NO'}")
        print("=" * 60)

    def finalize(self) -> dict:
        """Add end timestamp and total duration, return full summary."""
        summary = self.get_summary()
        summary["ended_at"] = datetime.now(timezone.utc).isoformat() + "Z"
        try:
            start = datetime.fromisoformat(summary["started_at"].replace("Z", ""))
            end = datetime.fromisoformat(summary["ended_at"].replace("Z", ""))
            summary["total_duration_seconds"] = round((end - start).total_seconds(), 3)
        except Exception:
            pass  # intentional
        return summary
