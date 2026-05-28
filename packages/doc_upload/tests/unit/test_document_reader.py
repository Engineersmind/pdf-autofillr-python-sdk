# tests/unit/test_document_reader.py
"""Unit tests for DocumentReader — no LLM, no network, no disk I/O except temp files."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

# Guard: skip all tests if heavy deps not installed
pytest.importorskip("fitz", reason="PyMuPDF not installed")


def _write_tmp(content: str, suffix: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    f.write(content)
    f.flush()
    f.close()
    return f.name


class TestDocumentReaderTxt:
    def test_read_txt(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        path = _write_tmp("Hello World\nLine 2", ".txt")
        try:
            text = DocumentReader().read(path)
            assert "Hello World" in text
            assert "Line 2" in text
        finally:
            os.unlink(path)

    def test_read_md(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        path = _write_tmp("# Heading\n\nSome **bold** text.", ".md")
        try:
            text = DocumentReader().read(path)
            assert "Heading" in text
        finally:
            os.unlink(path)


class TestDocumentReaderJson:
    def test_read_json(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        data = {"name": "John", "age": 30}
        path = _write_tmp(json.dumps(data), ".json")
        try:
            text = DocumentReader().read(path)
            assert "John" in text
        finally:
            os.unlink(path)


class TestDocumentReaderCsv:
    def test_read_csv(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        path = _write_tmp("name,age\nJohn,30\nJane,25", ".csv")
        try:
            text = DocumentReader().read(path)
            assert "John" in text
            assert "Jane" in text
        finally:
            os.unlink(path)


class TestDocumentReaderHtml:
    def test_read_html(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        html = "<html><body><h1>Title</h1><p>Paragraph text.</p></body></html>"
        path = _write_tmp(html, ".html")
        try:
            text = DocumentReader().read(path)
            assert "Title" in text
            assert "Paragraph text" in text
        finally:
            os.unlink(path)

    def test_strips_script_tags(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        html = (
            "<html><body><script>alert('x')</script><p>Real content</p></body></html>"
        )
        path = _write_tmp(html, ".html")
        try:
            text = DocumentReader().read(path)
            assert "alert" not in text
            assert "Real content" in text
        finally:
            os.unlink(path)


class TestDocumentReaderErrors:
    def test_file_not_found(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        with pytest.raises(FileNotFoundError):
            DocumentReader().read("/nonexistent/path/file.pdf")

    def test_unsupported_format(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        path = _write_tmp("data", ".xyz")
        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                DocumentReader().read(path)
        finally:
            os.unlink(path)

    def test_supported_extensions_list(self):
        from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader

        exts = DocumentReader.supported_extensions()
        assert ".pdf" in exts
        assert ".docx" in exts
        assert ".csv" in exts
        assert ".md" in exts
