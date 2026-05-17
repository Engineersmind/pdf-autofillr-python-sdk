"""
StorageConfig — path resolution for the pdf-fillr-production bucket structure.

Bucket: pdf-fillr-production

Path patterns (all methods build these):

  Input PDF (uploaded by caller):
    shared/input-pdfs/{env_folder}/{uid}/sessions/{sid}/pdfs/{pid}/{filename}

  Static config (read-only, seeded at deploy):
    config/{filename}

  Session handoff (written by chatbot/doc_upload):
    {env_folder}/{user_type}/{uid}/sessions/{sid}/final_output_flat.json

  Mapper outputs:
    {env_folder}/{user_type}/{uid}/sessions/{sid}/mapper/{pid}/{filename}

  RAG inputs (mapper writes, RAG API 1 reads):
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/input/{filename}

  RAG predictions:
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/predictions/{filename}

  Shared — filled PDF store:
    shared/filled_pdf_store/{env_folder}/{uid}/{sid}/{pid}/filled.pdf

  Shared — unpredicted fields:
    shared/unpredicted_fields/{env_folder}/{uid}/{sid}/{pid}/{filename}

  Shared — hash registry (mapper cache):
    shared/pdf-cache/pdf-registry/hash_registry.json

env_folder mapping:
    "Local_user"  → "local"
    "DEV_user"    → "dev"
    "prod_user"   → "prod"

user_type:
    developer_id present → "sdk-user"
    developer_id absent  → "regular"
"""

import os
import logging
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ── env label → folder segment ────────────────────────────────────────────────
_ENV_FOLDER_MAP = {
    "local_user": "local",
    "dev_user":   "dev",
    "prod_user":  "prod",
}


def _env_to_folder(env: str) -> str:
    """Map env label (e.g. 'DEV_user') to path folder (e.g. 'dev')."""
    return _ENV_FOLDER_MAP.get(env.lower(), env.lower())


def _derive_user_type(developer_id: Optional[str]) -> str:
    return "sdk-user" if developer_id else "regular"


class StorageConfig:
    """
    Provides path resolution for all pipeline files.

    Constructed once per request with the env and developer_id from the
    incoming API payload.  All path methods take (uid, sid, pid, filename).

    Env vars:
        MAPPER_STORAGE          local | aws | azure | gcp  (default: local)
        MAPPER_PROCESSING_PATH  temp dir for in-flight work (default: /tmp/processing)

        # Local only
        MAPPER_DATA_PATH        root for local data         (default: /app/data)

        # AWS S3
        MAPPER_S3_BUCKET        bucket name (default: pdf-fillr-production)

        # Azure Blob
        MAPPER_AZURE_CONTAINER  container name

        # GCP Cloud Storage
        MAPPER_GCS_BUCKET       bucket name
    """

    def __init__(self, env: str = None, developer_id: str = None):
        """
        Args:
            env:          Env label from the API request — "Local_user", "DEV_user",
                          or "prod_user".  Falls back to MAPPER_ENV env var.
            developer_id: Developer ID from the API request (if set → sdk-user path).
                          Falls back to MAPPER_DEVELOPER_ID env var.
        """
        raw_env = env or os.environ.get("MAPPER_ENV", "Local_user")
        self.env_label   = raw_env
        self.env_folder  = _env_to_folder(raw_env)

        dev_id = developer_id or os.environ.get("MAPPER_DEVELOPER_ID", "")
        self.developer_id = dev_id or None
        self.user_type    = _derive_user_type(self.developer_id)

        raw_storage = (
            os.environ.get("MAPPER_STORAGE")
            or os.environ.get("CLOUD_PROVIDER", "local")
        ).lower()
        # Normalise: "s3" → "aws"
        self.storage_type = "aws" if raw_storage == "s3" else raw_storage

        self._processing_base = os.environ.get("MAPPER_PROCESSING_PATH", "/tmp/processing")
        self._backend = None

        # ── Storage root ─────────────────────────────────────────────────────
        if self.storage_type == "aws":
            bucket = (
                os.environ.get("MAPPER_S3_BUCKET")
                or os.environ.get("AWS_S3_BUCKET", "pdf-fillr-production")
            )
            self._root = f"s3://{bucket}"

        elif self.storage_type == "azure":
            container = (
                os.environ.get("MAPPER_AZURE_CONTAINER")
                or os.environ.get("AZURE_STORAGE_CONTAINER", "pdf-fillr-production")
            )
            self._root = f"azure://{container}"

        elif self.storage_type == "gcp":
            bucket = (
                os.environ.get("MAPPER_GCS_BUCKET")
                or os.environ.get("GCP_STORAGE_BUCKET", "pdf-fillr-production")
            )
            self._root = f"gs://{bucket}"

        else:  # local
            self._root = os.environ.get("MAPPER_DATA_PATH", "/app/data")

        logger.debug(
            f"StorageConfig: storage={self.storage_type} root={self._root} "
            f"env={self.env_folder} user_type={self.user_type}"
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _join(self, *parts) -> str:
        path = "/".join(str(p).strip("/") for p in parts if p)
        if self._root.startswith(("s3://", "azure://", "gs://")):
            return f"{self._root}/{path}"
        full = os.path.join(self._root, *[str(p) for p in parts])
        os.makedirs(os.path.dirname(full) if "." in os.path.basename(full) else full,
                    exist_ok=True)
        return full

    def _session_base(self, uid, sid) -> str:
        return f"{self.env_folder}/{self.user_type}/{uid}/sessions/{sid}"

    # ── Path builders ─────────────────────────────────────────────────────────

    def input_pdf_path(self, uid, sid, pid, filename: str) -> str:
        """shared/input-pdfs/{env}/{uid}/sessions/{sid}/pdfs/{pid}/{filename}"""
        return self._join(
            "shared", "input-pdfs", self.env_folder,
            uid, "sessions", sid, "pdfs", pid, filename
        )

    def config_path(self, filename: str) -> str:
        """config/{filename} — static files, never written at runtime."""
        return self._join("config", filename)

    def session_root_path(self, uid, sid, filename: str) -> str:
        """{env}/{user_type}/{uid}/sessions/{sid}/{filename}"""
        return self._join(self._session_base(uid, sid), filename)

    def mapper_path(self, uid, sid, pid, filename: str) -> str:
        """{env}/{user_type}/{uid}/sessions/{sid}/mapper/{pid}/{filename}"""
        return self._join(self._session_base(uid, sid), "mapper", pid, filename)

    def rag_input_path(self, uid, sid, pid, filename: str) -> str:
        """{env}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/input/{filename}"""
        return self._join(self._session_base(uid, sid), "rag", pid, "input", filename)

    def rag_predictions_path(self, uid, sid, pid, filename: str) -> str:
        """{env}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/predictions/{filename}"""
        return self._join(self._session_base(uid, sid), "rag", pid, "predictions", filename)

    def filled_pdf_store_path(self, uid, sid, pid) -> str:
        """shared/filled_pdf_store/{env}/{uid}/{sid}/{pid}/filled.pdf"""
        return self._join(
            "shared", "filled_pdf_store", self.env_folder,
            uid, sid, pid, "filled.pdf"
        )

    def unpredicted_fields_path(self, uid, sid, pid, filename: str) -> str:
        """shared/unpredicted_fields/{env}/{uid}/{sid}/{pid}/{filename}"""
        return self._join(
            "shared", "unpredicted_fields", self.env_folder,
            uid, sid, pid, filename
        )

    def cache_path(self, filename: str) -> str:
        """shared/pdf-cache/pdf-registry/{filename}"""
        return self._join("shared", "pdf-cache", "pdf-registry", filename)

    def local_cache_path(self, filename: str) -> str:
        """Always a local filesystem path — used for reading/writing the hash registry."""
        from pdf_autofillr_mapper.core.config import settings
        cfg_path = getattr(settings, "cache_registry_path", "")
        if cfg_path and not cfg_path.startswith(("s3://", "azure://", "gs://")):
            local_base = os.path.dirname(cfg_path)
        else:
            local_base = os.path.join(
                os.environ.get("MAPPER_DATA_PATH", "/app/data"),
                "shared", "pdf-cache", "pdf-registry"
            )
        os.makedirs(local_base, exist_ok=True)
        return os.path.join(local_base, filename)

    def new_processing_dir(self) -> str:
        """Create and return a fresh isolated temp directory for one request."""
        path = os.path.join(self._processing_base, str(uuid4()))
        os.makedirs(path, exist_ok=True)
        return path

    def processing_path(self, job_dir: str, filename: str) -> str:
        return os.path.join(job_dir, filename)

    # ── Backend ───────────────────────────────────────────────────────────────

    @property
    def backend(self):
        if self._backend is None:
            from pdf_autofillr_mapper.storage.backends.factory import get_storage_backend
            self._backend = get_storage_backend(self.storage_type)
        return self._backend


# ── Factory ───────────────────────────────────────────────────────────────────

def get_storage_config(env: str = None, developer_id: str = None) -> StorageConfig:
    """Create a StorageConfig for a single request."""
    return StorageConfig(env=env, developer_id=developer_id)


def reset_storage_config() -> None:
    """No-op kept for backwards compatibility with tests."""
    try:
        from pdf_autofillr_mapper.storage.backends.factory import clear_cache
        clear_cache()
    except ImportError:
        pass