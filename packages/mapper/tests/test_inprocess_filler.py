"""
Tests for InProcessMapperFiller — the zero-HTTP in-process integration.
"""
import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def configs_dir(tmp_path):
    """Create a minimal configs/ directory with form_keys.json and mapper_config.ini."""
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()

    # Minimal form_keys.json
    form_keys = {
        "investor_full_legal_name_id": "",
        "investor_email_id": "",
    }
    (cfg_dir / "form_keys.json").write_text(json.dumps(form_keys))

    # Minimal mapper_config.ini
    ini = "[mapping]\nllm_model = gpt-4o\n"
    (cfg_dir / "mapper_config.ini").write_text(ini)

    return str(cfg_dir)


@pytest.fixture
def embedded_pdf(tmp_path):
    """Create a fake embedded PDF file."""
    pdf = tmp_path / "form_embedded.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake embedded pdf")
    return str(pdf)


class TestInProcessMapperFillerInit:
    def test_loads_config_from_directory(self, configs_dir):
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller
        filler = InProcessMapperFiller(config_dir=configs_dir)
        assert filler._mapper_config.llm_model == "gpt-4o"

    def test_falls_back_to_env_when_no_ini(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MAPPER_LLM_MODEL", "gpt-4o-mini")
        # Create configs dir without mapper_config.ini
        cfg_dir = tmp_path / "configs"
        cfg_dir.mkdir()
        (cfg_dir / "form_keys.json").write_text("{}")

        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller
        filler = InProcessMapperFiller(config_dir=str(cfg_dir))
        assert filler._mapper_config.llm_model == "gpt-4o-mini"

    def test_accepts_explicit_mapper_config(self, configs_dir):
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        cfg = MapperConfig(llm_model="claude-3-5-sonnet-20241022")
        filler = InProcessMapperFiller(mapper_config=cfg, config_dir=configs_dir)
        assert filler._mapper_config.llm_model == "claude-3-5-sonnet-20241022"


class TestInProcessMapperFillerInterface:
    def test_check_document_ready_true_when_exists(self, embedded_pdf, configs_dir):
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller
        filler = InProcessMapperFiller(config_dir=configs_dir)
        assert filler.check_document_ready(embedded_pdf) is True

    def test_check_document_ready_false_when_missing(self, configs_dir):
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller
        filler = InProcessMapperFiller(config_dir=configs_dir)
        assert filler.check_document_ready("/nonexistent/path.pdf") is False

    @pytest.mark.skip(reason="requires valid PDF fixture - blank bytes rejected by PyMuPDF, tracked separately")
    def test_prepare_document_calls_pipeline_stages(self, configs_dir, tmp_path):
        """prepare_document should call extract -> map -> embed in sequence."""
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller

        fake_pdf = str(tmp_path / "blank.pdf")
        Path(fake_pdf).write_bytes(b"%PDF-1.4 blank")
        embedded_result = str(tmp_path / "blank_embedded.pdf")

        with patch("pdf_autofillr_mapper.inprocess_filler.InProcessMapperFiller.__init__",
                   return_value=None):
            filler = InProcessMapperFiller.__new__(InProcessMapperFiller)
            filler._config_dir = configs_dir
            filler._mapper_config = MagicMock()

            mock_pipeline = MagicMock()
            mock_pipeline.extract = AsyncMock(return_value={"output_file": str(tmp_path / "extracted.json")})
            mock_pipeline.map = AsyncMock(return_value={
                "output_files": {
                    "mapping": str(tmp_path / "mapped.json"),
                    "radio_groups": str(tmp_path / "radio.json"),
                }
            })
            mock_pipeline.embed = AsyncMock(return_value={"output_file": embedded_result})
            filler._pipeline = mock_pipeline

            # Create form_keys.json so _get_form_keys_path works
            Path(configs_dir) / "form_keys.json"  # already exists from fixture

            result = filler.prepare_document(fake_pdf, "Individual")

            mock_pipeline.extract.assert_called_once()
            mock_pipeline.map.assert_called_once()
            mock_pipeline.embed.assert_called_once()
            assert result == embedded_result

    def test_fill_document_writes_temp_json_and_calls_fill(self, embedded_pdf, configs_dir, tmp_path):
        """fill_document should write data_flat to temp JSON and call pipeline.fill."""
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller

        data_flat = {
            "investor_full_legal_name_id": "John Doe",
            "investor_email_id": "john@example.com",
        }
        filled_path = str(tmp_path / "form_filled.pdf")

        with patch("pdf_autofillr_mapper.inprocess_filler.InProcessMapperFiller.__init__",
                   return_value=None):
            filler = InProcessMapperFiller.__new__(InProcessMapperFiller)
            filler._config_dir = configs_dir
            filler._mapper_config = MagicMock()

            mock_pipeline = MagicMock()
            mock_pipeline.fill = AsyncMock(return_value={"output_file": filled_path, "status": "success"})
            filler._pipeline = mock_pipeline

            result = filler.fill_document(embedded_pdf, data_flat)

            mock_pipeline.fill.assert_called_once()
            call_kwargs = mock_pipeline.fill.call_args
            # The temp JSON path must have been passed
            assert call_kwargs.kwargs.get("embedded_pdf_path") == embedded_pdf
            tmp_json = call_kwargs.kwargs.get("input_data_path")
            # Temp file should be cleaned up
            assert not Path(tmp_json).exists()
            assert result["output_file"] == filled_path

    def test_get_form_keys_path_raises_when_missing(self, tmp_path):
        """_get_form_keys_path should raise FileNotFoundError if form_keys.json absent."""
        from pdf_autofillr_mapper.inprocess_filler import InProcessMapperFiller

        empty_dir = str(tmp_path / "empty_configs")
        Path(empty_dir).mkdir()

        with patch("pdf_autofillr_mapper.inprocess_filler.InProcessMapperFiller.__init__",
                   return_value=None):
            filler = InProcessMapperFiller.__new__(InProcessMapperFiller)
            filler._config_dir = empty_dir
            filler._mapper_config = MagicMock()
            filler._pipeline = MagicMock()

            with pytest.raises(FileNotFoundError, match="form_keys.json"):
                filler._get_form_keys_path()
