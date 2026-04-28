"""
Tests for copy_sample_configs() — verifies chatbot configs are bundled
correctly and that mapper configs are also copied when mapper is available.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCopySampleConfigs:
    def test_creates_configs_dir(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        assert (tmp_path / "configs").is_dir()

    def test_copies_form_keys(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        assert (tmp_path / "configs" / "form_keys.json").exists()

    def test_copies_mandatory(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        assert (tmp_path / "configs" / "mandatory.json").exists()

    def test_copies_meta_form_keys(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        assert (tmp_path / "configs" / "meta_form_keys.json").exists()

    def test_copies_field_questions(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        assert (tmp_path / "configs" / "field_questions.json").exists()

    def test_copies_investor_type_keys(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        itype_dir = tmp_path / "configs" / "global_investor_type_keys"
        assert itype_dir.is_dir()
        assert (itype_dir / "form_keys_individual.json").exists()

    def test_idempotent(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        copy_sample_configs(str(tmp_path))  # second call should not raise
        assert (tmp_path / "configs" / "form_keys.json").exists()

    def test_form_keys_is_valid_json(self, tmp_path):
        from chatbot import copy_sample_configs
        copy_sample_configs(str(tmp_path))
        with open(tmp_path / "configs" / "form_keys.json") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_calls_mapper_copy_sample_configs(self, tmp_path):
        """When pdf-autofillr-mapper is installed, its copy_sample_configs is called."""
        mock_mapper = MagicMock()
        mock_mapper.copy_sample_configs = MagicMock()
        with patch.dict("sys.modules", {"pdf_autofillr_mapper": mock_mapper}):
            from chatbot import copy_sample_configs
            copy_sample_configs(str(tmp_path))
        mock_mapper.copy_sample_configs.assert_called_once_with(str(tmp_path))

    def test_silently_skips_mapper_copy_if_not_installed(self, tmp_path):
        """Should not raise if pdf-autofillr-mapper is not installed."""
        with patch.dict("sys.modules", {"pdf_autofillr_mapper": None}):
            from chatbot import copy_sample_configs
            # Should complete without error
            copy_sample_configs(str(tmp_path))
        assert (tmp_path / "configs" / "form_keys.json").exists()
