# pdf_autofillr_doc_upload/telemetry/config.py
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TelemetryConfig:
    enabled: bool = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_TELEMETRY", "off").lower() not in ("off", "false", "0")
    )
    mode: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_TELEMETRY", "off").lower()
    )
    # local mode — write JSONL to a file
    local_path: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_TELEMETRY_PATH", "./doc_upload_telemetry")
    )
    # managed / self-hosted mode
    endpoint: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_TELEMETRY_ENDPOINT", "")
    )
    sdk_api_key: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_TELEMETRY_API_KEY", "")
    )
    batch_size: int = 10
    flush_interval_seconds: float = 5.0
