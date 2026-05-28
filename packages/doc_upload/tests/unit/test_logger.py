# tests/unit/test_logger.py
"""Unit tests for ExecutionLogger."""

from __future__ import annotations


class TestExecutionLogger:
    def test_log_adds_to_process_logs(self):
        from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger

        logger = ExecutionLogger(job_id="test")
        logger.log("Step 1 done")
        logger.log("Step 2 done")
        summary = logger.get_summary()
        assert summary["summary"]["total_process_logs"] == 2
        assert any("Step 1" in e["message"] for e in summary["process_logs"])

    def test_log_error_adds_to_errors(self):
        from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger

        logger = ExecutionLogger(job_id="test")
        logger.log_error("Something went wrong", details={"code": 500})
        summary = logger.get_summary()
        assert summary["summary"]["total_errors"] == 1
        assert summary["summary"]["success"] is False

    def test_success_true_when_no_errors(self):
        from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger

        logger = ExecutionLogger(job_id="test")
        logger.log("all good")
        assert logger.get_summary()["summary"]["success"] is True

    def test_api_call_logged(self):
        from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger

        logger = ExecutionLogger(job_id="test")
        logger.log_api_request(
            "make_embed_file", "https://example.com", {}, {"op": "embed"}
        )
        logger.log_api_response("make_embed_file", 200, {"result": "ok"}, 1.23)
        summary = logger.get_summary()
        assert summary["summary"]["total_api_calls"] == 1

    def test_finalize_adds_timestamps(self):
        from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger

        logger = ExecutionLogger(job_id="test")
        result = logger.finalize()
        assert "ended_at" in result
        assert "total_duration_seconds" in result
        assert result["total_duration_seconds"] >= 0

    def test_job_id_stored(self):
        from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger

        logger = ExecutionLogger(job_id="abc123")
        assert logger.get_summary()["job_id"] == "abc123"
