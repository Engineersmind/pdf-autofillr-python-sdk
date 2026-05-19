# src/ragpdf/storage/base.py
from abc import ABC, abstractmethod
from typing import Any, Optional


class StorageBackend(ABC):
    """
    Abstract storage backend. Implement this to add any storage system
    (PostgreSQL, MongoDB, GCS, Azure Blob, etc.)
    """

    @abstractmethod
    def save_json(self, key: str, data: dict) -> None:
        """Save a dict as JSON at the given key."""

    @abstractmethod
    def load_json(self, key: str) -> Optional[dict]:
        """Load JSON from key. Returns None if not found."""

    @abstractmethod
    def append_to_jsonl(self, key: str, data: dict) -> None:
        """Append a line to a JSONL file at the given key."""

    @abstractmethod
    def load_jsonl(self, key: str) -> list:
        """Load a JSONL file. Returns list of dicts."""

    @abstractmethod
    def copy_file(self, source_key: str, dest_key: str) -> bool:
        """Copy a file from source_key to dest_key."""

    def load_json_from_path(self, full_path: str) -> Optional[dict]:
        """
        Load JSON from a full path (e.g. s3://bucket/key or /abs/path).
        Default implementation — override if your backend needs it.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement load_json_from_path"
        )
