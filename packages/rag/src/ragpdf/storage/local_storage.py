# src/ragpdf/storage/local_storage.py
import json
import logging
import os
from pathlib import Path

from ragpdf.storage.base import StorageBackend
from ragpdf.utils.helpers import safe_for_log

logger = logging.getLogger(__name__)


class PathAccessError(PermissionError):
    """Raised when a storage key would resolve outside data_path."""


class LocalStorage(StorageBackend):
    """
    Filesystem-backed storage. Ideal for development and single-server deployments.

    Usage:
        storage = LocalStorage(data_path="./data/rag")
    """

    def __init__(self, data_path: str = "./data/rag"):
        self.data_path = data_path
        os.makedirs(data_path, exist_ok=True)

    def _validated_path(self, key: str) -> str:
        """
        Resolve `key` against data_path (following symlinks) and verify the
        result stays inside data_path before it's used for any file
        operation. Keys here are built elsewhere from user_id/session_id/
        pdf_id (e.g. "predictions/{user_id}/{session_id}/{pdf_id}/..."),
        which reach this class directly from HTTP request bodies via the
        prediction/feedback pipelines — a crafted user_id like
        "../../../etc" previously reached open()/os.path.join() with zero
        validation at all (CWE-22).

        Must use Path.resolve(), not os.path.normpath/abspath — a symlink
        inside data_path pointing outside it would pass a normpath-only
        check but read from the symlink target.
        """
        base = Path(self.data_path).resolve()
        resolved = (base / key).resolve()
        if not (resolved == base or str(resolved).startswith(str(base) + os.sep)):
            raise PathAccessError(f"Invalid key: {key!r} escapes data_path")
        return str(resolved)

    def _full_path(self, key: str) -> str:
        path = self._validated_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def save_json(self, key: str, data: dict) -> None:
        path = self._full_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved JSON: {safe_for_log(path)}")

    def load_json(self, key: str) -> dict | None:
        path = self._validated_path(key)
        if not os.path.exists(path):
            logger.debug(f"Not found: {safe_for_log(path)}")
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def append_to_jsonl(self, key: str, data: dict) -> None:
        path = self._full_path(key)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

    def load_jsonl(self, key: str) -> list:
        path = self._validated_path(key)
        if not os.path.exists(path):
            return []
        results = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # intentional
        return results

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        import shutil

        src = self._validated_path(source_key)
        dst = self._full_path(dest_key)
        if not os.path.exists(src):
            logger.warning(f"Source not found: {safe_for_log(src)}")
            return False
        shutil.copy2(src, dst)
        return True

    def load_json_from_path(self, full_path: str) -> dict | None:
        """Load from absolute filesystem path."""
        if not os.path.exists(full_path):
            return None
        with open(full_path, encoding="utf-8") as f:
            return json.load(f)
