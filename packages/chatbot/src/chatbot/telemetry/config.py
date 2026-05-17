# chatbot/telemetry/config.py
"""TelemetryConfig dataclass."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TelemetryConfig:
    enabled: bool = False
    mode: str = "local"              # local | self_hosted | managed
    endpoint: str = ""
    sdk_api_key: str = ""
    include_field_keys: bool = True
    include_latency: bool = True
    include_state_transitions: bool = True
    batch_size: int = 10
    flush_interval_seconds: int = 30
