# pdf_autofillr_doc_upload/pdf/api_handler.py
"""
PDFAPIHandler — HTTP client for the PDF-filling Lambda service.

Direct port of Lambda api_handler.py.

Supports three operations:
  make_embed_file    — create embedded PDF template
  check_embed_file   — poll until embed file is ready
  fill_pdf           — fill the PDF with extracted data
"""

from __future__ import annotations

import time

import requests

from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger


class PDFAPIHandler:
    """
    Thin HTTP client for all three PDF-filling API operations.

    Args:
        lambda_url: URL of the PDF-filling Lambda (or any HTTP endpoint).
        api_key:    API key sent as X-API-Key header.
        logger:     ExecutionLogger instance for request/response tracking.
    """

    def __init__(self, lambda_url: str, api_key: str, logger: ExecutionLogger):
        self.lambda_url = lambda_url
        self.api_key = api_key
        self.logger = logger

    # ── Generic request helper ─────────────────────────────────────────

    def _make_request(
        self,
        operation: str,
        payload: dict,
        timeout: float = 200,
    ) -> tuple[bool, dict | None]:
        start = time.time()
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        self.logger.log_api_request(
            operation=operation,
            url=self.lambda_url,
            headers={"X-API-Key": "***REDACTED***", "Content-Type": "application/json"},
            payload=payload,
        )

        try:
            response = requests.post(
                self.lambda_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            duration = time.time() - start

            try:
                data = response.json()
            except Exception:
                data = {"raw_text": response.text[:500]}

            self.logger.log_api_response(
                operation=operation,
                status_code=response.status_code,
                response_data=data,
                duration_seconds=round(duration, 3),
            )

            if response.status_code == 200:
                return True, data
            else:
                self.logger.log_error(
                    f"API request failed: {operation}",
                    details={"status_code": response.status_code, "response": data},
                )
                return False, data

        except requests.Timeout:
            duration = time.time() - start
            self.logger.log_error(
                f"API request timeout: {operation}",
                details={
                    "timeout_seconds": timeout,
                    "duration_seconds": round(duration, 3),
                },
            )
            return False, None

        except Exception as e:
            duration = time.time() - start
            self.logger.log_error(
                f"API request error: {operation}",
                details={"error": str(e), "duration_seconds": round(duration, 3)},
                exception=e,
            )
            return False, None

    # ── Step 1: make_embed_file ────────────────────────────────────────

    def make_embed_file(
        self,
        user_id,
        pdf_doc_id,
        session_id: str,
        investor_type: str,
        use_second_mapper: bool = True,
    ) -> bool:
        self.logger.log(
            f"📤 make_embed_file  user={user_id}  pdf={pdf_doc_id}  type={investor_type}"
        )

        try:
            user_id = int(user_id)
            pdf_doc_id = int(pdf_doc_id)
        except (ValueError, TypeError) as e:
            self.logger.log_error(f"Invalid user_id or pdf_doc_id: {e}")
            return False

        payload = {
            "operation": "make_embed_file",
            "user_id": user_id,
            "pdf_doc_id": pdf_doc_id,
            "session_id": session_id,
            "investor_type": investor_type,
            "use_second_mapper": use_second_mapper,
        }

        success, _ = self._make_request("make_embed_file", payload)
        self.logger.log(
            "✅ make_embed_file OK" if success else "❌ make_embed_file failed"
        )
        return success

    # ── Step 2: check_embed_file (polling) ────────────────────────────

    def check_embed_file(
        self,
        user_id,
        pdf_doc_id,
        investor_type: str,
        max_attempts: int = 48,
        wait_interval: int = 10,
    ) -> tuple[bool, str | None]:
        self.logger.log(
            f"🔄 check_embed_file  max={max_attempts}×{wait_interval}s = {max_attempts*wait_interval}s"
        )

        try:
            user_id = int(user_id)
            pdf_doc_id = int(pdf_doc_id)
        except (ValueError, TypeError) as e:
            self.logger.log_error(f"Invalid user_id or pdf_doc_id: {e}")
            return False, None

        payload = {
            "operation": "check_embed_file",
            "user_id": user_id,
            "pdf_doc_id": pdf_doc_id,
            "investor_type": investor_type,
        }

        for attempt in range(1, max_attempts + 1):
            self.logger.log(f"⏳ Poll {attempt}/{max_attempts}")
            success, data = self._make_request("check_embed_file", payload, timeout=10)

            if success and data:
                result = data.get("result", {})
                if result.get("embedded_pdf_created", False):
                    embed_path = result.get("embedded_pdf_path")
                    self.logger.log(f"✅ Embed file ready: {embed_path}")
                    return True, embed_path

            self.logger.log(f"⏳ Not ready, waiting {wait_interval}s…")
            time.sleep(wait_interval)

        self.logger.log_error(
            f"Embed file not ready after {max_attempts * wait_interval}s",
            details={"max_attempts": max_attempts, "wait_interval": wait_interval},
        )
        return False, None

    # ── Step 3: fill_pdf ──────────────────────────────────────────────

    def fill_pdf(
        self,
        user_id,
        pdf_doc_id,
        session_id: str,
        use_profile_info: bool = True,
    ) -> bool:
        self.logger.log(
            f"📝 fill_pdf  user={user_id}  pdf={pdf_doc_id}  session={session_id}"
        )

        try:
            user_id = int(user_id)
            pdf_doc_id = int(pdf_doc_id)
        except (ValueError, TypeError) as e:
            self.logger.log_error(f"Invalid user_id or pdf_doc_id: {e}")
            return False

        payload = {
            "operation": "fill_pdf",
            "user_id": user_id,
            "pdf_doc_id": pdf_doc_id,
            "session_id": session_id,
            "use_profile_info": use_profile_info,
        }

        success, _ = self._make_request("fill_pdf", payload, timeout=200)
        self.logger.log("✅ fill_pdf OK" if success else "❌ fill_pdf failed")
        return success
