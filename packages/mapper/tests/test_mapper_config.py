"""
Tests for MapperConfig — the new lazy configuration class.
"""
import os
import pytest
import tempfile
from pathlib import Path


class TestMapperConfigFromDirectory:
    def test_loads_defaults_when_no_ini(self, tmp_path):
        """Should return defaults without crashing if mapper_config.ini missing."""
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig.from_directory(str(tmp_path))
        assert cfg.llm_model == "gpt-4o"
        assert cfg.confidence_threshold == 0.7
        assert cfg.source_type == "local"

    def test_loads_values_from_ini(self, tmp_path):
        """Should read values correctly from a real mapper_config.ini."""
        ini_content = """
[general]
source_type = aws
pdf_cache_enabled = false

[mapping]
llm_model = claude-3-5-sonnet-20241022
confidence_threshold = 0.85
chunking_strategy = window
use_second_mapper = true

[aws]
output_base_path = s3://my-bucket/output
cache_registry_path = s3://my-bucket/cache.json
temp_local_dir = /tmp
"""
        (tmp_path / "mapper_config.ini").write_text(ini_content)
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig.from_directory(str(tmp_path))

        assert cfg.llm_model == "claude-3-5-sonnet-20241022"
        assert cfg.confidence_threshold == 0.85
        assert cfg.chunking_strategy == "window"
        assert cfg.source_type == "aws"
        assert cfg.use_second_mapper is True
        assert cfg.pdf_cache_enabled is False
        assert cfg.output_base_path == "s3://my-bucket/output"

    def test_partial_ini_falls_back_to_defaults(self, tmp_path):
        """Partial INI should fill missing keys with defaults."""
        ini_content = """
[mapping]
llm_model = gpt-4
"""
        (tmp_path / "mapper_config.ini").write_text(ini_content)
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig.from_directory(str(tmp_path))
        assert cfg.llm_model == "gpt-4"
        assert cfg.confidence_threshold == 0.7  # default


class TestMapperConfigFromEnv:
    def test_reads_env_vars(self, monkeypatch):
        """Should read all values from environment variables."""
        monkeypatch.setenv("MAPPER_LLM_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("MAPPER_CONFIDENCE_THRESHOLD", "0.9")
        monkeypatch.setenv("MAPPER_SOURCE_TYPE", "aws")
        monkeypatch.setenv("MAPPER_CACHE_ENABLED", "false")

        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig.from_env()
        assert cfg.llm_model == "gpt-4o-mini"
        assert cfg.confidence_threshold == 0.9
        assert cfg.source_type == "aws"
        assert cfg.pdf_cache_enabled is False

    def test_defaults_when_no_env(self):
        """Should return defaults when no env vars set."""
        # Clear any relevant env vars
        for k in ["MAPPER_LLM_MODEL", "MAPPER_SOURCE_TYPE"]:
            os.environ.pop(k, None)
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig.from_env()
        assert cfg.llm_model == "gpt-4o"
        assert cfg.source_type == "local"


class TestMapperConfigDirect:
    def test_direct_construction(self):
        """Should accept kwargs directly."""
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig(
            llm_model="ollama/llama3",
            confidence_threshold=0.6,
            source_type="local",
        )
        assert cfg.llm_model == "ollama/llama3"
        assert cfg.confidence_threshold == 0.6

    def test_import_does_not_crash_without_ini(self):
        """Importing pdf_autofillr_mapper must never crash even without config.ini."""
        import pdf_autofillr_mapper  # noqa: F401 — should not raise
        assert pdf_autofillr_mapper.__version__ == "1.0.8"
