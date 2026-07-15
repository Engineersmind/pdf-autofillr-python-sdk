# pdf_autofillr_doc_upload/config/settings.py
"""
DocUploadSettings — all configuration from environment variables.

Variable reference
------------------
DOC_UPLOAD_LLM_MODEL        LiteLLM model string  (default: openai/gpt-4.1-mini)
DOC_UPLOAD_LLM_API_KEY      Universal API key override
OPENAI_API_KEY              Passed through to LiteLLM for openai/* models
ANTHROPIC_API_KEY           Passed through to LiteLLM for anthropic/* models

DOC_UPLOAD_STORAGE          local | s3 | gcp | azure     (default: local)
DOC_UPLOAD_DATA_PATH        Root for job data             (default: ./data/doc_upload)
DOC_UPLOAD_CONFIG_PATH      configs/ directory            (default: ./configs)
DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS
                            Comma-separated extra directories that
                            document_path may point into (local storage
                            only). Paths outside DOC_UPLOAD_DATA_PATH,
                            DOC_UPLOAD_CONFIG_PATH, and these roots are
                            rejected — this closes local-file-disclosure
                            via a crafted document_path/schema_path.

AWS_OUTPUT_BUCKET           Required when DOC_UPLOAD_STORAGE=s3
AWS_CONFIG_BUCKET           Required when DOC_UPLOAD_STORAGE=s3
AWS_REGION                  (default: us-east-1)

GCP_OUTPUT_BUCKET           Required when DOC_UPLOAD_STORAGE=gcp
GCP_CONFIG_BUCKET           Required when DOC_UPLOAD_STORAGE=gcp
GCP_PROJECT_ID              Optional GCP project

AZURE_OUTPUT_CONTAINER      Required when DOC_UPLOAD_STORAGE=azure
AZURE_CONFIG_CONTAINER      Required when DOC_UPLOAD_STORAGE=azure
AZURE_STORAGE_CONNECTION_STRING

DOC_UPLOAD_PDF_FILLER       none | mapper | managed       (default: none)
DOC_UPLOAD_PDF_PATH         Path/URI to the blank PDF to fill
                              Local:  C:/path/to/blank_form.pdf
                              S3:     s3://bucket/path/blank_form.pdf
                              GCS:    gs://bucket/path/blank_form.pdf
MAPPER_API_URL              HTTP mapper server URL (leave empty for in-process)
MAPPER_API_KEY              API key for HTTP mapper server
DOC_UPLOAD_PDF_POLL_INTERVAL  Seconds between ready-checks  (default: 10)
DOC_UPLOAD_PDF_POLL_TIMEOUT   Max seconds to wait for embed  (default: 150)
DOC_UPLOAD_PDF_MAX_RETRIES    Fill retry attempts            (default: 3)

DOC_UPLOAD_TELEMETRY        off | local | managed           (default: off)
DOC_UPLOAD_TELEMETRY_PATH   Local telemetry JSONL dir       (default: ./doc_upload_telemetry)

DOC_UPLOAD_LOG_LEVEL        DEBUG | INFO | WARNING | ERROR  (default: INFO)
DOC_UPLOAD_DEBUG_LOGGING    true | false                    (default: false)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class DocUploadSettings:
    # ── LLM ───────────────────────────────────────────────────────────
    llm_model: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_LLM_MODEL", "openai/gpt-4.1-mini")
    )
    llm_api_key: str | None = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("DOC_UPLOAD_LLM_TEMPERATURE", "0"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("DOC_UPLOAD_LLM_MAX_TOKENS", "4096"))
    )
    llm_timeout: float = field(
        default_factory=lambda: float(os.getenv("DOC_UPLOAD_LLM_TIMEOUT", "120"))
    )
    llm_max_retries: int = field(
        default_factory=lambda: int(os.getenv("DOC_UPLOAD_LLM_MAX_RETRIES", "3"))
    )

    # ── Storage ───────────────────────────────────────────────────────
    storage: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_STORAGE", "local").lower()
    )
    data_path: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_DATA_PATH", "./data/doc_upload")
    )
    config_path: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_CONFIG_PATH", "./configs")
    )
    allowed_document_roots: list[str] = field(
        default_factory=lambda: [
            r
            for r in os.getenv("DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS", "").split(",")
            if r.strip()
        ]
    )

    # ── PDF Filler ────────────────────────────────────────────────────
    pdf_filler: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_PDF_FILLER", "none").lower()
    )
    # Path or URI to the blank PDF to fill.
    # Local examples:  C:/path/to/blank_form.pdf   ./data/input/blank_form.pdf
    # Cloud examples:  s3://bucket/blank_form.pdf  gs://bucket/blank_form.pdf
    pdf_path: str = field(default_factory=lambda: os.getenv("DOC_UPLOAD_PDF_PATH", ""))
    mapper_api_url: str = field(default_factory=lambda: os.getenv("MAPPER_API_URL", ""))
    mapper_api_key: str = field(default_factory=lambda: os.getenv("MAPPER_API_KEY", ""))
    pdf_poll_interval: int = field(
        default_factory=lambda: int(os.getenv("DOC_UPLOAD_PDF_POLL_INTERVAL", "10"))
    )
    pdf_poll_timeout: int = field(
        default_factory=lambda: int(os.getenv("DOC_UPLOAD_PDF_POLL_TIMEOUT", "150"))
    )
    pdf_max_retries: int = field(
        default_factory=lambda: int(os.getenv("DOC_UPLOAD_PDF_MAX_RETRIES", "3"))
    )

    # ── Telemetry ─────────────────────────────────────────────────────
    telemetry: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_TELEMETRY", "off").lower()
    )
    telemetry_path: str = field(
        default_factory=lambda: os.getenv(
            "DOC_UPLOAD_TELEMETRY_PATH", "./doc_upload_telemetry"
        )
    )

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_LOG_LEVEL", "INFO")
    )
    debug_logging: bool = field(
        default_factory=lambda: os.getenv("DOC_UPLOAD_DEBUG_LOGGING", "false").lower()
        == "true"
    )

    @classmethod
    def from_env(cls) -> DocUploadSettings:
        """Load all settings from environment variables."""
        return cls()
