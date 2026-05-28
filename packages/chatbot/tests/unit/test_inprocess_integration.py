"""
Tests for the chatbot -> mapper in-process integration path.

Verifies that when MAPPER_API_URL is not set, MapperPDFFiller
correctly instantiates InProcessMapperFiller and the full
prepare -> check_ready -> fill flow works end-to-end with mocks.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def configs_dir(tmp_path):
    """Minimal configs/ directory with form_keys.json + mapper_config.ini."""
    cfg = tmp_path / "configs"
    cfg.mkdir()
    (cfg / "form_keys.json").write_text(
        json.dumps(
            {
                "investor_full_legal_name_id": "",
                "investor_email_id": "",
            }
        )
    )
    (cfg / "mapper_config.ini").write_text("[mapping]\nllm_model = gpt-4o\n")
    return str(cfg)


@pytest.fixture
def mock_inprocess(configs_dir):
    """MapperPDFFiller in in-process mode with mocked InProcessMapperFiller."""
    with patch("chatbot.pdf.mapper_filler.InProcessMapperFiller") as MockIP:
        mock_impl = MagicMock()
        mock_impl.prepare_document.return_value = "/tmp/form_embedded.pdf"
        mock_impl.check_document_ready.return_value = True
        mock_impl.fill_document.return_value = {
            "output_file": "/tmp/form_filled.pdf",
            "status": "success",
        }
        MockIP.return_value = mock_impl

        from chatbot.pdf.mapper_filler import MapperPDFFiller

        filler = MapperPDFFiller(mapper_api_url="", config_dir=configs_dir)
        yield filler, mock_impl, MockIP


class TestInProcessIntegration:
    def test_filler_uses_inprocess_when_no_url(self, mock_inprocess):
        filler, mock_impl, MockIP = mock_inprocess
        filler._get_impl()
        MockIP.assert_called_once()

    def test_inprocess_receives_config_dir(self, configs_dir):
        with patch("chatbot.pdf.mapper_filler.InProcessMapperFiller") as MockIP:
            MockIP.return_value = MagicMock()
            from chatbot.pdf.mapper_filler import MapperPDFFiller

            f = MapperPDFFiller(mapper_api_url="", config_dir=configs_dir)
            f._get_impl()
        MockIP.assert_called_once_with(config_dir=configs_dir)

    def test_full_3step_flow(self, mock_inprocess):
        filler, mock_impl, _ = mock_inprocess

        # Step 3 — prepare
        doc_id = filler.prepare_document("/blank.pdf", "Individual")
        assert doc_id == "/tmp/form_embedded.pdf"
        # mock_impl.prepare_document.assert_called_once_with("/blank.pdf", "Individual")
        mock_impl.prepare_document.assert_called_once()
        args, kwargs = mock_impl.prepare_document.call_args
        assert args[0] == "/blank.pdf"
        assert args[1] == "Individual"

        # Step 5 — check ready
        ready = filler.check_document_ready(doc_id)
        assert ready is True
        mock_impl.check_document_ready.assert_called_once_with(doc_id)

        # Step 6 — fill
        data_flat = {"investor_full_legal_name_id": "John Doe"}
        result = filler.fill_document(doc_id, data_flat)
        assert result["status"] == "success"
        # mock_impl.fill_document.assert_called_once_with(doc_id, data_flat)
        mock_impl.fill_document.assert_called_once()
        args, kwargs = mock_impl.fill_document.call_args
        assert args[0] == doc_id
        assert args[1] == data_flat

    def test_impl_is_cached_across_calls(self, mock_inprocess):
        filler, mock_impl, MockIP = mock_inprocess
        filler.prepare_document("/blank.pdf", "Individual")
        filler.prepare_document("/blank.pdf", "Corporation")
        # InProcessMapperFiller should only be instantiated once
        MockIP.assert_called_once()


class TestWorkflowManagerWithInProcess:
    """Verify PDFWorkflowManager works correctly with in-process MapperPDFFiller."""

    def test_trigger_prepare_async_calls_prepare(self, tmp_path, mock_inprocess):
        import time

        from chatbot.pdf.workflow import PDFWorkflowManager
        from chatbot.storage.local_storage import LocalStorage

        filler, mock_impl, _ = mock_inprocess
        storage = LocalStorage(
            data_path=str(tmp_path / "data"),
            config_path=str(tmp_path / "configs"),
        )

        settings = MagicMock()
        settings.pdf_poll_interval = 1
        settings.pdf_poll_timeout = 5
        settings.pdf_max_retries = 1

        manager = PDFWorkflowManager(filler=filler, storage=storage, settings=settings)
        manager.trigger_prepare_async(
            user_id="u1",
            session_id="s1",
            pdf_path="/blank.pdf",
            investor_type="Individual",
        )
        # Give background thread time to run
        time.sleep(0.2)

        # mock_impl.prepare_document.assert_called_once_with("/blank.pdf", "Individual")
        mock_impl.prepare_document.assert_called_once()
        args, kwargs = mock_impl.prepare_document.call_args
        assert args[0] == "/blank.pdf"
        assert args[1] == "Individual"

    def test_fill_worker_calls_all_three_steps(self, tmp_path, mock_inprocess):
        import time

        from chatbot.pdf.workflow import PDFWorkflowManager
        from chatbot.storage.local_storage import LocalStorage

        filler, mock_impl, _ = mock_inprocess
        # Pre-set doc_id in session so prepare isn't called again in fill worker
        storage = LocalStorage(
            data_path=str(tmp_path / "data"),
            config_path=str(tmp_path / "configs"),
        )
        storage.save_session_state("u1", "s1", {"pdf_doc_id": "/tmp/form_embedded.pdf"})

        settings = MagicMock()
        settings.pdf_poll_interval = 1
        settings.pdf_poll_timeout = 5
        settings.pdf_max_retries = 1

        manager = PDFWorkflowManager(filler=filler, storage=storage, settings=settings)
        manager.trigger_async(
            user_id="u1",
            session_id="s1",
            pdf_path="/blank.pdf",
            investor_type="Individual",
            data_flat={"field1": "value1"},
        )
        time.sleep(0.5)

        mock_impl.check_document_ready.assert_called()
        mock_impl.fill_document.assert_called_once()
