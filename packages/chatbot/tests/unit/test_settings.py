"""
Unit tests for Settings — covers mapper mode validation changes.

Key change: MAPPER_API_URL is now optional.
In-process mode is the default when it's not set.
"""

import pytest


class TestSettingsMapperMode:
    def test_mapper_mode_no_url_no_error(self, monkeypatch):
        """mapper mode without MAPPER_API_URL should not raise (in-process is default)."""
        monkeypatch.setenv("chatbot_PDF_FILLER", "mapper")
        monkeypatch.setenv("chatbot_PDF_PATH", "/path/to/blank.pdf")
        monkeypatch.delenv("MAPPER_API_URL", raising=False)
        from chatbot.config.settings import Settings

        # Should not raise
        s = Settings(validate=True)
        assert s.pdf_filler_mode == "mapper"

    def test_mapper_mode_with_url_no_key_warns(self, monkeypatch, recwarn):
        """When MAPPER_API_URL is set but MAPPER_API_KEY is not, a warning is emitted."""
        monkeypatch.setenv("chatbot_PDF_FILLER", "mapper")
        monkeypatch.setenv("chatbot_PDF_PATH", "/path/to/blank.pdf")
        monkeypatch.setenv("MAPPER_API_URL", "http://localhost:8000")
        monkeypatch.delenv("MAPPER_API_KEY", raising=False)
        from chatbot.config.settings import Settings

        Settings(validate=True)
        # Should warn about missing API key
        assert any("MAPPER_API_KEY" in str(w.message) for w in recwarn.list)

    def test_mapper_mode_with_url_and_key_no_warning(self, monkeypatch, recwarn):
        """When MAPPER_API_URL and MAPPER_API_KEY are both set, no warning."""
        monkeypatch.setenv("chatbot_PDF_FILLER", "mapper")
        monkeypatch.setenv("chatbot_PDF_PATH", "/path/to/blank.pdf")
        monkeypatch.setenv("MAPPER_API_URL", "http://localhost:8000")
        monkeypatch.setenv("MAPPER_API_KEY", "my-key")
        from chatbot.config.settings import Settings

        Settings(validate=True)
        mapper_warns = [w for w in recwarn.list if "MAPPER_API_KEY" in str(w.message)]
        assert len(mapper_warns) == 0

    def test_mapper_config_dir_defaults_to_config_path(self, monkeypatch):
        """mapper_config_dir should equal chatbot_CONFIG_PATH."""
        monkeypatch.setenv("chatbot_CONFIG_PATH", "/custom/configs")
        monkeypatch.setenv("chatbot_PDF_FILLER", "none")
        from chatbot.config.settings import Settings

        s = Settings(validate=False)
        assert s.mapper_config_dir == "/custom/configs"

    def test_mapper_config_dir_default(self, monkeypatch):
        monkeypatch.delenv("chatbot_CONFIG_PATH", raising=False)
        monkeypatch.setenv("chatbot_PDF_FILLER", "none")
        from chatbot.config.settings import Settings

        s = Settings(validate=False)
        assert s.mapper_config_dir == "./configs"

    def test_none_mode_no_validation_errors(self, monkeypatch):
        monkeypatch.setenv("chatbot_PDF_FILLER", "none")
        from chatbot.config.settings import Settings

        s = Settings(validate=True)
        assert s.pdf_filler_mode == "none"

    def test_missing_pdf_path_raises(self, monkeypatch):
        monkeypatch.setenv("chatbot_PDF_FILLER", "mapper")
        monkeypatch.delenv("chatbot_PDF_PATH", raising=False)
        from chatbot.config.settings import Settings

        with pytest.raises(EnvironmentError, match="chatbot_PDF_PATH"):
            Settings(validate=True)
