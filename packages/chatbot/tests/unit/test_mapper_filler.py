"""
Unit tests for MapperPDFFiller.

Covers:
  - Auto-mode detection (in-process vs HTTP)
  - HTTP mode: URL prefix, investor_type encoding, doc_id extraction,
    check_document_ready, fill_document
  - In-process mode: delegates to InProcessMapperFiller
  - ImportError when mapper package missing
"""
import os
import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def http_filler(tmp_path):
    """MapperPDFFiller in HTTP mode with a mocked _HttpMapperFiller impl."""
    from chatbot.pdf.mapper_filler import MapperPDFFiller
    f = MapperPDFFiller(
        mapper_api_url="http://localhost:8000",
        mapper_api_key="test-key",
        config_dir=str(tmp_path),
    )
    # Force HTTP mode by pre-initialising the impl with a mock
    mock_impl = MagicMock()
    f._impl = mock_impl
    return f, mock_impl


@pytest.fixture
def inprocess_filler(tmp_path):
    """MapperPDFFiller in in-process mode with a mocked InProcessMapperFiller."""
    from chatbot.pdf.mapper_filler import MapperPDFFiller
    # No MAPPER_API_URL -> in-process mode
    f = MapperPDFFiller(mapper_api_url="", config_dir=str(tmp_path))
    mock_impl = MagicMock()
    f._impl = mock_impl
    return f, mock_impl


# ─────────────────────────────────────────────────────────────────────────────
# Mode detection
# ─────────────────────────────────────────────────────────────────────────────

class TestModeDetection:
    def test_http_mode_when_url_set(self, tmp_path):
        from chatbot.pdf.mapper_filler import MapperPDFFiller, _HttpMapperFiller
        f = MapperPDFFiller(mapper_api_url="http://myserver:9000", config_dir=str(tmp_path))
        impl = f._get_impl()
        assert isinstance(impl, _HttpMapperFiller)

    def test_http_mode_url_has_prefix(self, tmp_path):
        from chatbot.pdf.mapper_filler import MapperPDFFiller, _HttpMapperFiller
        f = MapperPDFFiller(mapper_api_url="http://myserver:9000", config_dir=str(tmp_path))
        impl = f._get_impl()
        assert impl._api_url == "http://myserver:9000/mapper"

    def test_http_mode_custom_prefix_empty(self, tmp_path):
        from chatbot.pdf.mapper_filler import MapperPDFFiller, _HttpMapperFiller
        f = MapperPDFFiller(
            mapper_api_url="http://myserver:9000",
            url_prefix="",
            config_dir=str(tmp_path),
        )
        impl = f._get_impl()
        assert impl._api_url == "http://myserver:9000"

    def test_http_mode_custom_prefix(self, tmp_path):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        f = MapperPDFFiller(
            mapper_api_url="http://myserver:9000",
            url_prefix="/api/v1",
            config_dir=str(tmp_path),
        )
        impl = f._get_impl()
        assert impl._api_url == "http://myserver:9000/api/v1"

    def test_inprocess_mode_when_no_url(self, tmp_path):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        # Patch InProcessMapperFiller so we don't need actual mapper installed
        with patch("chatbot.pdf.mapper_filler.InProcessMapperFiller") as MockIP:
            MockIP.return_value = MagicMock()
            f = MapperPDFFiller(mapper_api_url="", config_dir=str(tmp_path))
            impl = f._get_impl()
        MockIP.assert_called_once_with(config_dir=str(tmp_path))

    def test_inprocess_mode_uses_config_dir(self, tmp_path, monkeypatch):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        monkeypatch.setenv("chatbot_CONFIG_PATH", str(tmp_path))
        with patch("chatbot.pdf.mapper_filler.InProcessMapperFiller") as MockIP:
            MockIP.return_value = MagicMock()
            f = MapperPDFFiller(mapper_api_url="")
            f._get_impl()
        MockIP.assert_called_once_with(config_dir=str(tmp_path))

    def test_inprocess_raises_import_error_when_mapper_missing(self, tmp_path):
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        f = MapperPDFFiller(mapper_api_url="", config_dir=str(tmp_path))
        with patch.dict("sys.modules", {"pdf_autofillr_mapper": None,
                                         "pdf_autofillr_mapper.inprocess_filler": None}):
            with pytest.raises(ImportError, match="pdf-autofillr-mapper"):
                f._get_impl()

    def test_url_prefix_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MAPPER_URL_PREFIX", "/custom")
        from chatbot.pdf.mapper_filler import MapperPDFFiller
        f = MapperPDFFiller(mapper_api_url="http://host:8000", config_dir=str(tmp_path))
        impl = f._get_impl()
        assert impl._api_url == "http://host:8000/custom"


# ─────────────────────────────────────────────────────────────────────────────
# Interface delegation
# ─────────────────────────────────────────────────────────────────────────────

class TestInterfaceDelegation:
    def test_prepare_document_delegates(self, http_filler):
        f, mock_impl = http_filler
        mock_impl.prepare_document.return_value = "/out/embedded.pdf"
        result = f.prepare_document("/in/form.pdf", "Individual")
        mock_impl.prepare_document.assert_called_once_with("/in/form.pdf", "Individual")
        assert result == "/out/embedded.pdf"

    def test_check_document_ready_delegates(self, http_filler):
        f, mock_impl = http_filler
        mock_impl.check_document_ready.return_value = True
        assert f.check_document_ready("/out/embedded.pdf") is True
        mock_impl.check_document_ready.assert_called_once_with("/out/embedded.pdf")

    def test_fill_document_delegates(self, http_filler):
        f, mock_impl = http_filler
        data = {"field1": "value1"}
        mock_impl.fill_document.return_value = {"status": "success"}
        result = f.fill_document("/out/embedded.pdf", data)
        mock_impl.fill_document.assert_called_once_with("/out/embedded.pdf", data)
        assert result["status"] == "success"

    def test_inprocess_delegates(self, inprocess_filler):
        f, mock_impl = inprocess_filler
        mock_impl.prepare_document.return_value = "/tmp/embedded.pdf"
        result = f.prepare_document("/tmp/blank.pdf", "Trust")
        mock_impl.prepare_document.assert_called_once_with("/tmp/blank.pdf", "Trust")
        assert result == "/tmp/embedded.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP implementation (_HttpMapperFiller)
# ─────────────────────────────────────────────────────────────────────────────

class TestHttpMapperFiller:

    @pytest.fixture
    def http_impl(self):
        from chatbot.pdf.mapper_filler import _HttpMapperFiller
        return _HttpMapperFiller(
            api_url="http://localhost:8000/mapper",
            api_key="test-key",
            timeout=30.0,
        )

    def test_prepare_extracts_outputs_embedded_pdf(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"outputs": {"embedded_pdf": "/out/emb.pdf"}}}
            result = http_impl.prepare_document("/in/form.pdf", "Individual")
        assert result == "/out/emb.pdf"

    def test_prepare_extracts_flat_embedded_pdf(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"embedded_pdf": "/out/flat.pdf"}}
            result = http_impl.prepare_document("/in/form.pdf", "Individual")
        assert result == "/out/flat.pdf"

    def test_prepare_extracts_embedded_pdf_path(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"embedded_pdf_path": "/out/legacy.pdf"}}
            result = http_impl.prepare_document("/in/form.pdf", "Individual")
        assert result == "/out/legacy.pdf"

    def test_prepare_falls_back_to_input_when_no_key(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"unexpected_key": "value"}}
            result = http_impl.prepare_document("/in/form.pdf", "Individual")
        assert result == "/in/form.pdf"

    def test_prepare_encodes_investor_type_in_session_label(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"embedded_pdf": "/out/e.pdf"}}
            http_impl.prepare_document("/in/form.pdf", "Corporation")
        call_payload = mock_post.call_args[0][1]
        assert "corporation" in call_payload["session_id"].lower()

    def test_check_ready_exists_true(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"exists": True}}
            assert http_impl.check_document_ready("/out/e.pdf") is True

    def test_check_ready_exists_false(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"exists": False}}
            assert http_impl.check_document_ready("/out/e.pdf") is False

    def test_check_ready_status_success(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"status": "success"}}
            assert http_impl.check_document_ready("/out/e.pdf") is True

    def test_check_ready_status_not_found(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"status": "not_found"}}
            assert http_impl.check_document_ready("/out/e.pdf") is False

    def test_check_ready_legacy_has_metadata(self, http_impl):
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"data": {"has_metadata": True}}
            assert http_impl.check_document_ready("/out/e.pdf") is True

    def test_fill_document_posts_to_fill(self, http_impl):
        data = {"investor_full_name_id": "John Doe"}
        with patch("chatbot.pdf.mapper_filler._HttpMapperFiller._post") as mock_post:
            mock_post.return_value = {"status": "success", "filled_pdf": "/out/filled.pdf"}
            result = http_impl.fill_document("/out/embedded.pdf", data)
        call_args = mock_post.call_args
        assert call_args[0][0] == "fill"
        assert call_args[0][1]["embedded_pdf_path"] == "/out/embedded.pdf"
        assert call_args[0][1]["data"] == data
        assert result["status"] == "success"

    def test_post_attaches_api_key_header(self, http_impl):
        import httpx
        with patch("httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {}
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response
            http_impl._post("test", {})
        headers = mock_post.call_args[1]["headers"]
        assert headers.get("X-API-Key") == "test-key"
