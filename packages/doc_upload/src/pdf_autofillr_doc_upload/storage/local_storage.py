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

Security
--------
This class is used both as a trusted programmatic library (call
``download_document``/``load_schema`` with any path your own code chooses —
that's the documented contract, and is unrestricted here on purpose) and,
via the FastAPI entrypoint, as a target for untrusted HTTP input. Those are
different trust levels, so the restriction belongs at the HTTP boundary, not
buried in the general-purpose storage backend: see
``entrypoints/fastapi_app.py``, which calls ``assert_path_allowed()`` on
every `document_path`/`schema_path` it receives *before* it ever reaches
this class. That's what actually closes the unauthenticated arbitrary local
file disclosure this class previously enabled — restricting the paths
`download_document`/`load_schema` accept here as well would also block
ordinary programmatic use (e.g. reading a document from anywhere on disk in
a script or notebook), which is exactly what this backend is for.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from pdf_autofillr_doc_upload.storage.base import StorageBackend


class PathAccessError(PermissionError):
    """Raised when a requested path falls outside the allowed roots."""


class LocalStorage(StorageBackend):
    """
    Stores all data as JSON files on the local filesystem.

    Args:
        data_path:      Root directory for job data.
        config_path:    Directory containing schema JSON files (read-only).
        document_roots: Extra directories considered "allowed" by
                         ``assert_path_allowed()`` (used by the HTTP
                         entrypoint to validate untrusted input), in
                         addition to data_path/config_path. Defaults to the
                         DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS env var
                         (comma-separated). Has no effect on
                         download_document/load_schema themselves, which
                         remain unrestricted for trusted/programmatic use.
    """

    def __init__(
        self,
        data_path: str = "./data/doc_upload",
        config_path: str = "./configs",
        document_roots: list[str] | None = None,
    ):
        self.data_path = Path(data_path).resolve()
        self.config_path = Path(config_path).resolve()
        self.data_path.mkdir(parents=True, exist_ok=True)

        if document_roots is None:
            env_roots = os.getenv("DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS", "")
            document_roots = [r for r in env_roots.split(",") if r.strip()]

        # Roots considered "safe" for *untrusted* input — see
        # assert_path_allowed() below and its use in the FastAPI entrypoint.
        self._allowed_roots = [self.data_path, self.config_path] + [
            Path(r).resolve() for r in document_roots
        ]

    # ── Path safety (used by the HTTP entrypoint on untrusted input) ────

    def assert_path_allowed(self, raw_path: str, *, purpose: str = "document") -> Path:
        """
        Resolve `raw_path` (symlinks included) and verify it lives inside
        one of the allowed roots (data_path, config_path, or
        DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS). Raises PathAccessError otherwise.

        Call this on any path that originated from an untrusted caller
        (e.g. an HTTP request body) before passing it to
        download_document()/load_schema() — those two methods do not
        enforce this themselves, since they're also the documented,
        unrestricted programmatic API for trusted callers.
        """
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            # Bare filenames / relative paths are resolved against config_path
            # for schemas and data_path for everything else, mirroring the
            # documented lookup behaviour — never against the process CWD.
            base = self.config_path if purpose == "schema" else self.data_path
            candidate = base / raw_path

        resolved = candidate.resolve()

        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue

        raise PathAccessError(
            f"Refusing to access '{raw_path}' ({purpose}): path resolves to "
            f"'{resolved}', which is outside the allowed directories "
            f"{[str(r) for r in self._allowed_roots]}."
        )

    # ── Paths ──────────────────────────────────────────────────────────

    def _job_dir(self, job_id: str) -> Path:
        # job_id ends up as a single path segment under data_path/jobs — make
        # sure it can't be used to escape that directory (e.g. "../../etc").
        safe_id = Path(job_id).name
        if not safe_id or safe_id != job_id:
            raise PathAccessError(f"Invalid job_id: {job_id!r}")
        p = self.data_path / "jobs" / safe_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ── JSON helpers ───────────────────────────────────────────────────

    def _read(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
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

    def get_job_state(self, job_id: str) -> dict | None:
        return self._read(self._job_dir(job_id) / "job_state.json")

    def save_job_state(self, job_id: str, state: dict) -> bool:
        return self._write(self._job_dir(job_id) / "job_state.json", state)

    # ── Output ─────────────────────────────────────────────────────────

    def get_output(self, job_id: str) -> dict | None:
        return self._read(self._job_dir(job_id) / "output.json")

    def save_output(self, job_id: str, data: dict) -> bool:
        return self._write(self._job_dir(job_id) / "output.json", data)

    def get_output_flat(self, job_id: str) -> dict | None:
        return self._read(self._job_dir(job_id) / "output_flat.json")

    def save_output_flat(self, job_id: str, data: dict) -> bool:
        return self._write(self._job_dir(job_id) / "output_flat.json", data)

    # ── Logs ───────────────────────────────────────────────────────────

    def save_execution_log(self, job_id: str, data: dict) -> bool:
        return self._write(self._job_dir(job_id) / "execution_log.json", data)

    def get_execution_log(self, job_id: str) -> dict | None:
        return self._read(self._job_dir(job_id) / "execution_log.json")

    # ── Config / document loading ──────────────────────────────────────

    def load_schema(self, schema_path: str) -> dict:
        """
        Load schema JSON.
        schema_path can be:
          - a bare filename:           "form_keys.json"  -> looked up in config_path
          - an absolute/relative path: "/abs/form_keys.json"

        Unrestricted by design — this is the trusted programmatic API. If
        `schema_path` comes from an untrusted source (e.g. an HTTP request),
        validate it with assert_path_allowed() first; the FastAPI entrypoint
        does this for you.
        """
        p = Path(schema_path)
        if not p.is_absolute() and not p.exists():
            p = self.config_path / schema_path
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def download_document(self, source_path: str, local_dest: str) -> str:
        """
        Local backend: source_path IS a local path — just copy it.

        Unrestricted by design — this is the trusted programmatic API. If
        `source_path` comes from an untrusted source (e.g. an HTTP request),
        validate it with assert_path_allowed() first; the FastAPI entrypoint
        does this for you.
        """
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
