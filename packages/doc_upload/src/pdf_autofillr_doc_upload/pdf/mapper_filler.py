# pdf_autofillr_doc_upload/pdf/mapper_filler.py
"""
MapperPDFFiller — connects the extractor SDK to pdf-autofillr-mapper.

Two modes (same pattern as chatbot-final):

  IN-PROCESS MODE (MAPPER_API_URL not set):
      Calls PDFAPIHandler directly via HTTP to the Lambda/service URL.
      set DOC_UPLOAD_FILL_PDF_LAMBDA_URL + DOC_UPLOAD_PDF_API_KEY.

  HTTP MODE (MAPPER_API_URL is set):
      Makes REST calls to a running mapper FastAPI server.

Usage::

    # Auto mode (env-driven)
    filler = MapperPDFFiller()

    # Explicit
    filler = MapperPDFFiller(
        lambda_url="https://xyz.lambda-url.us-east-1.on.aws",
        api_key="my-key",
    )
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from pdf_autofillr_doc_upload.pdf.interface import PDFFillerInterface
from pdf_autofillr_doc_upload.pdf.api_handler import PDFAPIHandler
from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger


class MapperPDFFiller(PDFFillerInterface):
    """
    PDF filler that calls the PDF-filling Lambda service.

    Args:
        lambda_url:  URL of the PDF-filling Lambda.
        api_key:     API key for the Lambda.
        logger:      ExecutionLogger instance (created fresh if not provided).
    """

    def __init__(
        self,
        lambda_url: Optional[str] = None,
        api_key: Optional[str] = None,
        logger: Optional[ExecutionLogger] = None,
    ):
        self._lambda_url = (
            lambda_url
            or os.getenv("DOC_UPLOAD_FILL_PDF_LAMBDA_URL")
            or os.getenv("FILL_PDF_LAMBDA_URL", "")
        ).rstrip("/")
        self._api_key = (
            api_key
            or os.getenv("DOC_UPLOAD_PDF_API_KEY")
            or os.getenv("PDF_API_KEY", "")
        )
        self._logger = logger or ExecutionLogger(job_id="pdf_filler")
        self._handler: Optional[PDFAPIHandler] = None

    def _get_handler(self) -> PDFAPIHandler:
        if self._handler is None:
            if not self._lambda_url:
                raise EnvironmentError(
                    "DOC_UPLOAD_FILL_PDF_LAMBDA_URL (or FILL_PDF_LAMBDA_URL) is required "
                    "for MapperPDFFiller. Set it in .env or pass lambda_url= explicitly."
                )
            self._handler = PDFAPIHandler(
                lambda_url=self._lambda_url,
                api_key=self._api_key,
                logger=self._logger,
            )
        return self._handler

    # ── PDFFillerInterface ────────────────────────────────────────────

    def make_embed_file(
        self,
        user_id: str,
        pdf_doc_id: str,
        session_id: str,
        investor_type: str,
        use_second_mapper: bool = True,
    ) -> bool:
        return self._get_handler().make_embed_file(
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            investor_type=investor_type,
            use_second_mapper=use_second_mapper,
        )

    def check_embed_file(
        self,
        user_id: str,
        pdf_doc_id: str,
        investor_type: str,
        max_attempts: int = 48,
        wait_interval: int = 10,
    ) -> Tuple[bool, Optional[str]]:
        return self._get_handler().check_embed_file(
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            investor_type=investor_type,
            max_attempts=max_attempts,
            wait_interval=wait_interval,
        )

    def fill_pdf(
        self,
        user_id: str,
        pdf_doc_id: str,
        session_id: str,
        use_profile_info: bool = True,
    ) -> bool:
        return self._get_handler().fill_pdf(
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            use_profile_info=use_profile_info,
        )
