# tests/unit/test_extractor.py
"""Unit tests for Extractor — LLM is mocked, no network calls."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock

SAMPLE_SCHEMA = {
    "investor_full_legal_name_id": "",
    "investor_email_id": "",
    "address_registered": {
        "address_registered_line1_id": "",
        "address_registered_city_id": "",
        "address_registered_country_id": "",
    },
}

SAMPLE_LLM_OUTPUT = {
    "filled_form_keys": {
        "investor_full_legal_name_id": "John Doe",
        "investor_email_id": "john@example.com",
        "address_registered": {
            "address_registered_line1_id": "123 Main St",
            "address_registered_city_id": "London",
            "address_registered_country_id": "United Kingdom",
        },
    }
}


def _write_tmp_txt(content: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.flush()
    f.close()
    return f.name


class TestExtractorWithMockedLLM:
    def test_extract_returns_schema_shaped_dict(self):
        from pdf_autofillr_doc_upload.extraction.extractor import Extractor
        from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.complete.return_value = json.dumps(SAMPLE_LLM_OUTPUT)

        extractor = Extractor(llm_client=mock_llm)
        path = _write_tmp_txt("Investor: John Doe, email john@example.com")
        try:
            result = extractor.extract(document_path=path, schema=SAMPLE_SCHEMA)
        finally:
            os.unlink(path)

        assert result["investor_full_legal_name_id"] == "John Doe"
        assert result["investor_email_id"] == "john@example.com"
        assert isinstance(result["address_registered"], dict)
        assert result["address_registered"]["address_registered_city_id"] == "London"

    def test_missing_fields_get_empty_string(self):
        from pdf_autofillr_doc_upload.extraction.extractor import Extractor
        from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

        mock_llm = MagicMock(spec=LLMClient)
        # LLM only returns name, not email
        mock_llm.complete.return_value = json.dumps(
            {
                "filled_form_keys": {
                    "investor_full_legal_name_id": "Jane",
                    "investor_email_id": "",
                    "address_registered": {
                        "address_registered_line1_id": "",
                        "address_registered_city_id": "",
                        "address_registered_country_id": "",
                    },
                }
            }
        )

        extractor = Extractor(llm_client=mock_llm)
        path = _write_tmp_txt("Name: Jane")
        try:
            result = extractor.extract(document_path=path, schema=SAMPLE_SCHEMA)
        finally:
            os.unlink(path)

        assert result["investor_email_id"] == ""

    def test_strips_markdown_fences_from_llm_output(self):
        from pdf_autofillr_doc_upload.extraction.extractor import Extractor
        from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

        mock_llm = MagicMock(spec=LLMClient)
        # Simulate LLM wrapping output in markdown fences
        mock_llm.complete.return_value = (
            "```json\n" + json.dumps(SAMPLE_LLM_OUTPUT) + "\n```"
        )

        extractor = Extractor(llm_client=mock_llm)
        path = _write_tmp_txt("doc content")
        try:
            result = extractor.extract(document_path=path, schema=SAMPLE_SCHEMA)
        finally:
            os.unlink(path)

        assert result["investor_full_legal_name_id"] == "John Doe"


class TestFlattenDict:
    def test_flat_passthrough(self):
        from pdf_autofillr_doc_upload.extraction.extractor import flatten_dict

        d = {"a": 1, "b": "two"}
        assert flatten_dict(d) == {"a": 1, "b": "two"}

    def test_nested_one_level(self):
        from pdf_autofillr_doc_upload.extraction.extractor import flatten_dict

        d = {"address": {"city": "London", "zip": "NW1"}}
        flat = flatten_dict(d)
        assert flat["address.city"] == "London"
        assert flat["address.zip"] == "NW1"

    def test_nested_two_levels(self):
        from pdf_autofillr_doc_upload.extraction.extractor import flatten_dict

        d = {"wiring": {"address": {"city": "NYC"}}}
        flat = flatten_dict(d)
        assert flat["wiring.address.city"] == "NYC"
