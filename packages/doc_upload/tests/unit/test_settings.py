# tests/unit/test_settings.py
"""Unit tests for DocUploadSettings."""

from __future__ import annotations

# All env vars that could leak from .env and break defaults assertions
_ALL_DOC_UPLOAD_VARS = [
    "DOC_UPLOAD_LLM_MODEL",
    "DOC_UPLOAD_LLM_API_KEY",
    "DOC_UPLOAD_STORAGE",
    "DOC_UPLOAD_DATA_PATH",
    "DOC_UPLOAD_CONFIG_PATH",
    "DOC_UPLOAD_PDF_FILLER",
    "DOC_UPLOAD_PDF_PATH",
    "DOC_UPLOAD_TELEMETRY",
    "DOC_UPLOAD_LOG_LEVEL",
    "DOC_UPLOAD_DEBUG_LOGGING",
    "DOC_UPLOAD_LLM_TEMPERATURE",
    "DOC_UPLOAD_LLM_MAX_TOKENS",
    "DOC_UPLOAD_LLM_TIMEOUT",
    "DOC_UPLOAD_LLM_MAX_RETRIES",
    "DOC_UPLOAD_PDF_POLL_INTERVAL",
    "DOC_UPLOAD_PDF_POLL_TIMEOUT",
    "DOC_UPLOAD_PDF_MAX_RETRIES",
    "MAPPER_API_URL",
    "MAPPER_API_KEY",
]


class TestDocUploadSettings:
    def test_defaults(self, monkeypatch):
        from pdf_autofillr_doc_upload.config.settings import DocUploadSettings

        # Clear ALL doc_upload env vars so .env doesn't leak into defaults test
        for var in _ALL_DOC_UPLOAD_VARS:
            monkeypatch.delenv(var, raising=False)
        s = DocUploadSettings()
        assert s.llm_model == "openai/gpt-4.1-mini"
        assert s.storage == "local"
        assert s.pdf_filler == "none"
        assert s.telemetry == "off"
        assert s.pdf_path == ""
        assert s.mapper_api_url == ""
        assert s.pdf_poll_interval == 10
        assert s.pdf_poll_timeout == 150
        assert s.pdf_max_retries == 3

    def test_env_override(self, monkeypatch):
        from pdf_autofillr_doc_upload.config.settings import DocUploadSettings

        monkeypatch.setenv(
            "DOC_UPLOAD_LLM_MODEL", "anthropic/claude-3-5-haiku-20241022"
        )
        monkeypatch.setenv("DOC_UPLOAD_STORAGE", "s3")
        monkeypatch.setenv("DOC_UPLOAD_PDF_FILLER", "mapper")
        monkeypatch.setenv("DOC_UPLOAD_PDF_PATH", "/tmp/blank.pdf")
        s = DocUploadSettings()
        assert s.llm_model == "anthropic/claude-3-5-haiku-20241022"
        assert s.storage == "s3"
        assert s.pdf_filler == "mapper"
        assert s.pdf_path == "/tmp/blank.pdf"

    def test_from_env(self, monkeypatch):
        from pdf_autofillr_doc_upload.config.settings import DocUploadSettings

        monkeypatch.setenv("DOC_UPLOAD_DEBUG_LOGGING", "true")
        s = DocUploadSettings.from_env()
        assert s.debug_logging is True
