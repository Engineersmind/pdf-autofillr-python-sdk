# chatbot/pdf/interface.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional
"""
PDFFillerInterface — abstract class for PDF filling integrations.
"""

class PDFFillerInterface(ABC):
    """
    Implement this to connect any PDF filling service.

    Example::

        class MyPDFService(PDFFillerInterface):
            def prepare_document(self, pdf_path, investor_type):
                r = requests.post('https://api.my-pdf.com/prepare', json={...})
                return r.json()['doc_id']

            def check_document_ready(self, doc_id):
                r = requests.get(f'https://api.my-pdf.com/status/{doc_id}')
                return r.json()['status'] == 'ready'

            def fill_document(self, doc_id, data_flat, output_path=None):
                r = requests.post(f'https://api.my-pdf.com/fill/{doc_id}', json={...})
                return r.json()['download_url']
    """

    @abstractmethod
    def prepare_document(self, pdf_path: str, investor_type: str) -> str:
        """
        Prepare the PDF for filling (field mapping, embed, etc.).
        Called when investor type is selected.

        Returns:
            doc_id — any string identifier for this prepared document.
        """

    @abstractmethod
    def check_document_ready(self, doc_id: str) -> bool:
        """
        Return True when the document is ready to be filled.
        The workflow manager handles polling — just return bool.
        """

    @abstractmethod
    def fill_document(self, doc_id: str, data_flat: dict,
                      output_path: Optional[str] = None) -> Any:
        """
        Fill the prepared document with collected investor data.
        Called after conversation completes.

        Args:
            doc_id:      Identifier returned by prepare_document().
            data_flat:   The final_output_flat dict from the session.
            output_path: Optional destination for the filled PDF.
                         workflow.py passes
                         {data_path}/{user_id}/sessions/{session_id}/filled.pdf
                         so all session outputs are in one place.
                         When None the filler decides where to write.
        """

    def get_result(self, doc_id: str) -> Any:
        """Optional: retrieve result after async fill completes."""
        return None