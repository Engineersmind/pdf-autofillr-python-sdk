# pdf_autofillr_doc_upload/storage/gcp_storage.py
"""
GCSStorage — Google Cloud Storage backend.

Env vars::
    GCP_OUTPUT_BUCKET
    GCP_CONFIG_BUCKET
    GCP_PROJECT_ID   (optional)
"""
from __future__ import annotations

import json
import tempfile
from typing import Optional

from pdf_autofillr_doc_upload.storage.base import StorageBackend


def _parse_gcs_uri(uri: str):
    assert uri.startswith("gs://"), f"Expected gs:// URI, got: {uri}"
    parts = uri.replace("gs://", "").split("/", 1)
    return parts[0], parts[1]


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self, output_bucket: str, config_bucket: str, project: Optional[str] = None):
        from google.cloud import storage as gcs
        self.output_bucket = output_bucket
        self.config_bucket = config_bucket
        self.client = gcs.Client(project=project)

    def _get_json(self, bucket: str, key: str) -> Optional[dict]:
        try:
            blob = self.client.bucket(bucket).blob(key)
            return json.loads(blob.download_as_text())
        except Exception as e:
            if "404" in str(e) or "No such object" in str(e):
                return None
            print(f"❌ GCS read error gs://{bucket}/{key}: {e}")
            return None

    def _put_json(self, bucket: str, key: str, data: dict) -> bool:
        try:
            blob = self.client.bucket(bucket).blob(key)
            blob.upload_from_string(
                json.dumps(data, indent=2, default=str),
                content_type="application/json",
            )
            return True
        except Exception as e:
            print(f"❌ GCS write error gs://{bucket}/{key}: {e}")
            return False

    def _job_key(self, job_id: str, filename: str) -> str:
        return f"jobs/{job_id}/{filename}"

    def get_job_state(self, job_id):
        return self._get_json(self.output_bucket, self._job_key(job_id, "job_state.json"))

    def save_job_state(self, job_id, state):
        return self._put_json(self.output_bucket, self._job_key(job_id, "job_state.json"), state)

    def get_output(self, job_id):
        return self._get_json(self.output_bucket, self._job_key(job_id, "output.json"))

    def save_output(self, job_id, data):
        return self._put_json(self.output_bucket, self._job_key(job_id, "output.json"), data)

    def get_output_flat(self, job_id):
        return self._get_json(self.output_bucket, self._job_key(job_id, "output_flat.json"))

    def save_output_flat(self, job_id, data):
        return self._put_json(self.output_bucket, self._job_key(job_id, "output_flat.json"), data)

    def save_execution_log(self, job_id, data):
        return self._put_json(self.output_bucket, self._job_key(job_id, "execution_log.json"), data)

    def get_execution_log(self, job_id):
        return self._get_json(self.output_bucket, self._job_key(job_id, "execution_log.json"))

    def load_schema(self, schema_path: str) -> dict:
        if schema_path.startswith("gs://"):
            bucket, key = _parse_gcs_uri(schema_path)
            data = self._get_json(bucket, key)
        else:
            data = self._get_json(self.config_bucket, schema_path)
        if data is None:
            raise FileNotFoundError(f"Schema not found: {schema_path}")
        return data

    def download_document(self, source_path: str, local_dest: str) -> str:
        if source_path.startswith("gs://"):
            bucket, key = _parse_gcs_uri(source_path)
            blob = self.client.bucket(bucket).blob(key)
            blob.download_to_filename(local_dest)
        else:
            import shutil
            shutil.copy2(source_path, local_dest)
        return local_dest

    def upload_file(self, local_path: str, dest_path: str) -> bool:
        try:
            bucket, key = _parse_gcs_uri(dest_path)
            blob = self.client.bucket(bucket).blob(key)
            blob.upload_from_filename(local_path)
            return True
        except Exception as e:
            print(f"❌ GCS upload error: {e}")
            return False
