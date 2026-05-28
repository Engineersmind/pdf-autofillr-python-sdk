"""
Google Cloud Storage backend.

Install: pip install ragpdf-sdk[gcs]

Usage:
    storage = GCSStorage(bucket="my-ragpdf-bucket", prefix="ragpdf/")

Credentials: set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON,
or use Application Default Credentials (gcloud auth application-default login).
"""

import json
import logging

from ragpdf.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class GCSStorage(StorageBackend):
    def __init__(self, bucket: str = "", prefix: str = ""):
        try:
            from google.cloud import storage as gcs
        except ImportError as e:
            raise ImportError(
                "GCSStorage requires google-cloud-storage. Install with: pip install ragpdf-sdk[gcs]"
            ) from e

        from ragpdf.config.settings import RAGPDF_GCS_BUCKET, RAGPDF_GCS_PREFIX

        self._bucket_name = bucket or RAGPDF_GCS_BUCKET
        self._prefix = prefix or RAGPDF_GCS_PREFIX
        self._prefix = self._prefix.rstrip("/") + "/" if self._prefix else ""

        if not self._bucket_name:
            raise ValueError("GCSStorage requires RAGPDF_GCS_BUCKET")

        self._client = gcs.Client()
        self._bucket = self._client.bucket(self._bucket_name)
        logger.info(
            f"GCSStorage initialized: bucket={self._bucket_name}, prefix={self._prefix}"
        )

    def _blob_name(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def save_json(self, key: str, data: dict) -> None:
        blob = self._bucket.blob(self._blob_name(key))
        blob.upload_from_string(
            json.dumps(data, indent=2), content_type="application/json"
        )
        logger.debug(f"GCS saved: gs://{self._bucket_name}/{self._blob_name(key)}")

    def load_json(self, key: str) -> dict | None:
        try:
            blob = self._bucket.blob(self._blob_name(key))
            return json.loads(blob.download_as_text())
        except Exception:
            return None

    def append_to_jsonl(self, key: str, data: dict) -> None:
        existing = ""
        try:
            blob = self._bucket.blob(self._blob_name(key))
            existing = blob.download_as_text()
        except Exception:
            pass  # intentional
        blob = self._bucket.blob(self._blob_name(key))
        blob.upload_from_string(
            existing + json.dumps(data) + "\n", content_type="application/jsonl"
        )

    def load_jsonl(self, key: str) -> list:
        try:
            blob = self._bucket.blob(self._blob_name(key))
            content = blob.download_as_text()
            return [
                json.loads(line)
                for line in content.strip().splitlines()
                if line.strip()
            ]
        except Exception:
            return []

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        try:
            src = self._bucket.blob(self._blob_name(source_key))
            dst = self._bucket.blob(self._blob_name(dest_key))
            self._bucket.copy_blob(src, self._bucket, dst.name)
            return True
        except Exception:
            return False

    def load_json_from_path(self, full_path: str) -> dict | None:
        if full_path.startswith("gs://"):
            parts = full_path[5:].split("/", 1)
            bucket = self._client.bucket(parts[0])
            blob = bucket.blob(parts[1])
            return json.loads(blob.download_as_text())
        return self.load_json(full_path)
