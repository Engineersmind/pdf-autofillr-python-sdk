# pdf_autofillr_doc_upload/storage/base.py
"""
StorageBackend — abstract class all storage implementations extend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """
    Abstract interface for all storage backends.

    Implement this to plug in any storage system — S3, GCS, Azure Blob,
    a custom database, etc.
    """

    # ── Job / session state ────────────────────────────────────────────

    @abstractmethod
    def get_job_state(self, job_id: str) -> dict | None:
        pass

    @abstractmethod
    def save_job_state(self, job_id: str, state: dict) -> bool:
        pass

    # ── Output data ────────────────────────────────────────────────────

    @abstractmethod
    def get_output(self, job_id: str) -> dict | None:
        pass

    @abstractmethod
    def save_output(self, job_id: str, data: dict) -> bool:
        pass

    @abstractmethod
    def get_output_flat(self, job_id: str) -> dict | None:
        pass

    @abstractmethod
    def save_output_flat(self, job_id: str, data: dict) -> bool:
        pass

    # ── Logs ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_execution_log(self, job_id: str, data: dict) -> bool:
        pass

    @abstractmethod
    def get_execution_log(self, job_id: str) -> dict | None:
        pass

    # ── Config loaders ─────────────────────────────────────────────────

    @abstractmethod
    def load_schema(self, schema_path: str) -> dict:
        pass

    @abstractmethod
    def download_document(self, source_path: str, local_dest: str) -> str:
        """
        Fetch document from wherever it lives (local path, S3 URI, GCS URI, etc.)
        and write it to local_dest. Returns local_dest.
        """
        pass

    @abstractmethod
    def upload_file(self, local_path: str, dest_path: str) -> bool:
        """
        Upload a local file to the storage backend at dest_path.
        dest_path is a URI or relative path depending on backend.
        """
        pass
