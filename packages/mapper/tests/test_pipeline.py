"""
Tests for PDFPipeline — the core orchestrator.

Tests the new mapper_config= parameter and verifies the existing
pipeline stages still work correctly after the refactor.
"""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mapper_cfg():
    from pdf_autofillr_mapper.config.mapper_config import MapperConfig
    return MapperConfig(
        llm_model="gpt-4o",
        confidence_threshold=0.8,
        chunking_strategy="page",
    )


class TestPDFPipelineInit:
    def test_empty_init(self):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        assert p.config == {}

    def test_config_dict_init(self):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline(config={"llm_model": "gpt-4"})
        assert p.config["llm_model"] == "gpt-4"

    def test_mapper_config_merges_into_config(self, mapper_cfg):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline(mapper_config=mapper_cfg)
        assert p.config["llm_model"] == "gpt-4o"
        assert p.config["confidence_threshold"] == 0.8
        assert p.config["chunking_strategy"] == "page"
        assert p.config["_mapper_config"] is mapper_cfg

    def test_explicit_config_takes_priority_over_mapper_config(self, mapper_cfg):
        """Explicit config dict values should NOT be overridden by mapper_config defaults."""
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline(
            config={"llm_model": "gpt-3.5-turbo"},
            mapper_config=mapper_cfg,
        )
        # setdefault means explicit config wins
        assert p.config["llm_model"] == "gpt-3.5-turbo"


class TestPDFPipelineExtract:
    async def test_raises_on_missing_pdf(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            await p.extract(pdf_path=str(tmp_path / "nonexistent.pdf"))

    async def test_extract_returns_dict_with_output_file(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline

        fake_pdf = tmp_path / "form.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        mock_extracted = {"pages": [], "fields": [{"name": "f1"}]}

        with patch("pdf_autofillr_mapper.orchestrator.DetailedFitzExtractor") as MockExt:
            instance = MockExt.return_value
            instance.extract.return_value = mock_extracted

            p = PDFPipeline()
            result = await p.extract(pdf_path=str(fake_pdf))

        assert result["status"] == "success"
        assert result["output_file"].endswith("_extracted.json")
        assert "execution_time_seconds" in result
        assert result["extracted_data"] == mock_extracted


class TestPDFPipelineMap:
    async def test_raises_on_missing_extracted_json(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        schema = tmp_path / "schema.json"
        schema.write_text("{}")
        with pytest.raises(FileNotFoundError, match="Extracted JSON not found"):
            await p.map(
                extracted_json_path=str(tmp_path / "missing.json"),
                input_schema_path=str(schema),
            )

    async def test_raises_on_missing_schema(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        extracted = tmp_path / "extracted.json"
        extracted.write_text("{}")
        with pytest.raises(FileNotFoundError, match="Input schema not found"):
            await p.map(
                extracted_json_path=str(extracted),
                input_schema_path=str(tmp_path / "missing.json"),
            )

    async def test_map_returns_output_files(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline

        extracted = tmp_path / "form_extracted.json"
        extracted.write_text(json.dumps({"pages": []}))
        schema = tmp_path / "schema.json"
        schema.write_text(json.dumps({"field1": ""}))

        mock_mapped = {"mapping": {"field1": "fid_1"}, "radio_groups": {}}

        with patch("pdf_autofillr_mapper.orchestrator.SemanticMapper") as MockMapper:
            instance = MockMapper.return_value
            instance.map = AsyncMock(return_value=mock_mapped)

            p = PDFPipeline()
            result = await p.map(
                extracted_json_path=str(extracted),
                input_schema_path=str(schema),
            )

        assert result["status"] == "success"
        assert "mapping" in result["output_files"]
        assert "radio_groups" in result["output_files"]
        assert Path(result["output_files"]["mapping"]).exists()
        assert Path(result["output_files"]["radio_groups"]).exists()


class TestPDFPipelineEmbed:
    async def test_raises_when_input_missing(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        with pytest.raises(FileNotFoundError):
            await p.embed(
                original_pdf_path=str(tmp_path / "missing.pdf"),
                extracted_json_path=str(tmp_path / "e.json"),
                mapping_json_path=str(tmp_path / "m.json"),
                radio_json_path=str(tmp_path / "r.json"),
            )

    async def test_embed_calls_java_stage(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline

        pdf = tmp_path / "form.pdf"
        pdf.write_bytes(b"%PDF fake")
        extracted = tmp_path / "extracted.json"
        extracted.write_text("{}")
        mapping = tmp_path / "mapping.json"
        mapping.write_text("{}")
        radio = tmp_path / "radio.json"
        radio.write_text("{}")
        embedded = tmp_path / "form_embedded.pdf"
        embedded.write_bytes(b"%PDF embedded")

        with patch("pdf_autofillr_mapper.orchestrator.run_embed_java_stage",
                   new=AsyncMock(return_value=str(embedded))):
            p = PDFPipeline()
            result = await p.embed(
                original_pdf_path=str(pdf),
                extracted_json_path=str(extracted),
                mapping_json_path=str(mapping),
                radio_json_path=str(radio),
            )

        assert result["status"] == "success"
        assert result["output_file"] == str(embedded)


class TestPDFPipelineFill:
    async def test_raises_when_embedded_pdf_missing(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        data = tmp_path / "data.json"
        data.write_text("{}")
        with pytest.raises(FileNotFoundError, match="Embedded PDF not found"):
            await p.fill(
                embedded_pdf_path=str(tmp_path / "missing.pdf"),
                input_data_path=str(data),
            )

    async def test_fill_calls_java_filler(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline

        embedded = tmp_path / "form_embedded.pdf"
        embedded.write_bytes(b"%PDF embedded")
        data = tmp_path / "data.json"
        data.write_text(json.dumps({"field1": "value1"}))
        filled = tmp_path / "form_filled.pdf"
        filled.write_bytes(b"%PDF filled")

        with patch("pdf_autofillr_mapper.orchestrator.fill_with_java",
                   new=AsyncMock(return_value=str(filled))):
            p = PDFPipeline()
            result = await p.fill(
                embedded_pdf_path=str(embedded),
                input_data_path=str(data),
            )

        assert result["status"] == "success"
        assert result["output_file"] == str(filled)


class TestPDFPipelineRunAll:
    async def test_run_all_raises_on_missing_pdf(self, tmp_path):
        from pdf_autofillr_mapper.orchestrator import PDFPipeline
        p = PDFPipeline()
        data = tmp_path / "data.json"
        data.write_text("{}")
        with pytest.raises(FileNotFoundError, match="Input PDF not found"):
            await p.run_all(
                input_pdf_path=str(tmp_path / "missing.pdf"),
                input_data_path=str(data),
            )

    async def test_run_all_returns_all_outputs(self, tmp_path):
        """run_all should call all 4 stages and return a complete result dict."""
        from pdf_autofillr_mapper.orchestrator import PDFPipeline

        pdf = tmp_path / "form.pdf"
        pdf.write_bytes(b"%PDF fake")
        data = tmp_path / "data.json"
        data.write_text(json.dumps({"field1": ""}))

        extracted = str(tmp_path / "form_extracted.json")
        mapped    = str(tmp_path / "form_mapped.json")
        radio     = str(tmp_path / "form_radio.json")
        embedded  = str(tmp_path / "form_embedded.pdf")
        filled    = str(tmp_path / "form_filled.pdf")

        # Create files so move operations don't fail
        for f in [extracted, mapped, radio, embedded, filled]:
            Path(f).write_bytes(b"fake")

        p = PDFPipeline()
        p.extract = AsyncMock(return_value={
            "output_file": extracted, "execution_time_seconds": 1.0, "status": "success"
        })
        p.map = AsyncMock(return_value={
            "output_files": {"mapping": mapped, "radio_groups": radio},
            "execution_time_seconds": 2.0, "status": "success"
        })
        p.embed = AsyncMock(return_value={
            "output_file": embedded, "execution_time_seconds": 0.5, "status": "success"
        })
        p.fill = AsyncMock(return_value={
            "output_file": filled, "execution_time_seconds": 0.3, "status": "success"
        })

        result = await p.run_all(
            input_pdf_path=str(pdf),
            input_data_path=str(data),
        )

        assert result["status"] == "success"
        assert result["final_output"] == filled
        assert "all_outputs" in result
        assert result["all_outputs"]["extracted_json"] == extracted
        assert result["all_outputs"]["filled_pdf"] == filled
        assert "timing" in result
        assert result["timing"]["total_pipeline_seconds"] > 0

        p.extract.assert_called_once()
        p.map.assert_called_once()
        p.embed.assert_called_once()
        p.fill.assert_called_once()
