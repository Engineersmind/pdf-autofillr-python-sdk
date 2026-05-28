# pdf_autofillr_doc_upload/pdf/interface.py
"""PDFFillerInterface — abstract base for all PDF filling backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PDFFillerInterface(ABC):
    """
    Abstract interface for PDF filling backends.

    Implement this to connect any PDF filler:
      - MapperPDFFiller  — uses pdf-autofillr-mapper (in-process or HTTP)
      - ManagedFiller    — (stub) cloud-managed filler
      - Custom           — bring your own
    """

    @abstractmethod
    def make_embed_file(
        self,
        user_id: str,
        pdf_doc_id: str,
        session_id: str,
        investor_type: str,
        use_second_mapper: bool = True,
    ) -> bool:
        """
        Step 1 — prepare the PDF template (make_embed_file).

        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def check_embed_file(
        self,
        user_id: str,
        pdf_doc_id: str,
        investor_type: str,
        max_attempts: int = 48,
        wait_interval: int = 10,
    ) -> tuple:
        """
        Step 2 — poll until the embed file is ready.

        Returns (ready: bool, embed_path: str | None).
        """
        pass

    @abstractmethod
    def fill_pdf(
        self,
        user_id: str,
        pdf_doc_id: str,
        session_id: str,
        use_profile_info: bool = True,
    ) -> bool:
        """
        Step 3 — fill the PDF with extracted data.

        Returns True if successful, False otherwise.
        """
        pass
