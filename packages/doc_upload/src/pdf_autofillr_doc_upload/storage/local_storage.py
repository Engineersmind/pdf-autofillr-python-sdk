# pdf_autofillr_doc_upload/storage/local_storage.py
"""
LocalStorage — filesystem backend.

Layout::

    {data_path}/
    └── jobs/
        └── {job_id}/
            ├── job_state.json
            ├── output.json
            ├── output_flat.json
            └── execution_log.json
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

from pdf_autofillr_doc_upload.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """
    Stores all data as JSON files on the local filesystem.

    Args:
        data_path:   Root directory for job data.
        config_path: Directory containing schema JSON files (read-only).
    """

    def __init__(self, data_path: str = "./data/doc_upload", config_path: str = "./configs"):
        self.data_path = Path(data_path)
        self.config_path = Path(config_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

    # ── Paths ──────────────────────────────────────────────────────────

    def _job_dir(self, job_id: str) -> Path:
        p = self.data_path / "jobs" / job_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── JSON helpers ───────────────────────────────────────────────────

    def _read(self, path: Path) -> Optional[Any]:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, path: Path, data: Any) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            print(f"❌ LocalStorage write error {path}: {e}")
            return False

    # ── Job state ──────────────────────────────────────────────────────

    def get_job_state(self, job_id: str) -> Optional[dict]:
        return self._read(self._job_dir(job_id) / "job_state.json")

    def save_job_state(self, job_id: str, state: dict) -> bool:
        return self._write(self._job_dir(job_id) / "job_state.json", state)

    # ── Output ─────────────────────────────────────────────────────────

    def get_output(self, job_id: str) -> Optional[dict]:
        return self._read(self._job_dir(job_id) / "output.json")

    def save_output(self, job_id: str, data: dict) -> bool:
        return self._write(self._job_dir(job_id) / "output.json", data)

    def get_output_flat(self, job_id: str) -> Optional[dict]:
        return self._read(self._job_dir(job_id) / "output_flat.json")

    def save_output_flat(self, job_id: str, data: dict) -> bool:
        return self._write(self._job_dir(job_id) / "output_flat.json", data)

    # ── Logs ───────────────────────────────────────────────────────────

    def save_execution_log(self, job_id: str, data: dict) -> bool:
        return self._write(self._job_dir(job_id) / "execution_log.json", data)

    def get_execution_log(self, job_id: str) -> Optional[dict]:
        return self._read(self._job_dir(job_id) / "execution_log.json")

    # ── Config / document loading ──────────────────────────────────────

    def load_schema(self, schema_path: str) -> dict:
        """
        Load schema JSON.
        schema_path can be:
          - a bare filename:           "form_keys.json"  -> looked up in config_path
          - an absolute/relative path: "/abs/form_keys.json"
        """
        p = Path(schema_path)
        if not p.is_absolute() and not p.exists():
            p = self.config_path / schema_path
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def download_document(self, source_path: str, local_dest: str) -> str:
        """Local backend: source_path IS a local path — just copy it."""
        src = Path(source_path)
        dst = Path(local_dest)
        if src.resolve() != dst.resolve():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
        return str(dst)

    def upload_file(self, local_path: str, dest_path: str) -> bool:
        """Local backend: copy to dest_path on the filesystem."""
        try:
            dst = Path(dest_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, str(dst))
            return True
        except Exception as e:
            print(f"❌ LocalStorage upload error: {e}")
            return False
