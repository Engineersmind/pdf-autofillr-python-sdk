# src/ragpdf/storage/local_storage.py
import json
import logging
import os
from typing import Optional

from ragpdf.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorage(StorageBackend):
    """
    Filesystem-backed storage. Ideal for development and single-server deployments.

    Usage:
        storage = LocalStorage(data_path="./data/rag")
    """

    def __init__(self, data_path: str = "./data/rag"):
        self.data_path = data_path
        os.makedirs(data_path, exist_ok=True)

    def _full_path(self, key: str) -> str:
        path = os.path.join(self.data_path, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def save_json(self, key: str, data: dict) -> None:
        path = self._full_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved JSON: {path}")

    def load_json(self, key: str) -> Optional[dict]:
        path = os.path.join(self.data_path, key)
        if not os.path.exists(path):
            logger.debug(f"Not found: {path}")
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def append_to_jsonl(self, key: str, data: dict) -> None:
        path = self._full_path(key)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def load_jsonl(self, key: str) -> list:
        path = os.path.join(self.data_path, key)
        if not os.path.exists(path):
            return []
        results = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return results

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        import shutil
        src = os.path.join(self.data_path, source_key)
        dst = self._full_path(dest_key)
        if not os.path.exists(src):
            logger.warning(f"Source not found: {src}")
            return False
        shutil.copy2(src, dst)
        return True

    def load_json_from_path(self, full_path: str) -> Optional[dict]:
        """Load from absolute filesystem path."""
        if not os.path.exists(full_path):
            return None
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
