# pdf_autofillr_doc_upload/storage/s3_storage.py
"""
S3Storage — AWS S3 backend.

Env vars::
    AWS_OUTPUT_BUCKET   Bucket for job outputs
    AWS_CONFIG_BUCKET   Bucket containing schema/config files
    AWS_REGION          (default: us-east-1)
"""
from __future__ import annotations

import json
import tempfile
from typing import Optional

from pdf_autofillr_doc_upload.storage.base import StorageBackend


def _parse_s3_uri(uri: str):
    assert uri.startswith("s3://"), f"Expected s3:// URI, got: {uri}"
    parts = uri.replace("s3://", "").split("/", 1)
    return parts[0], parts[1]


class S3Storage(StorageBackend):
    """
    Stores all data in AWS S3.

    Args:
        output_bucket: Bucket for job data and outputs.
        config_bucket: Bucket for schema/config files.
        region:        AWS region.
    """

    def __init__(self, output_bucket: str, config_bucket: str, region: str = "us-east-1"):
        import boto3
        self.output_bucket = output_bucket
        self.config_bucket = config_bucket
        self.s3 = boto3.client("s3", region_name=region)

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_json(self, bucket: str, key: str) -> Optional[dict]:
        try:
            obj = self.s3.get_object(Bucket=bucket, Key=key)
            return json.loads(obj["Body"].read())
        except self.s3.exceptions.NoSuchKey:
            return None
        except Exception as e:
            print(f"❌ S3 read error s3://{bucket}/{key}: {e}")
            return None

    def _put_json(self, bucket: str, key: str, data: dict) -> bool:
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data, indent=2, default=str),
                ContentType="application/json",
            )
            return True
        except Exception as e:
            print(f"❌ S3 write error s3://{bucket}/{key}: {e}")
            return False

    def _job_key(self, job_id: str, filename: str) -> str:
        return f"jobs/{job_id}/{filename}"

    # ── Job state ──────────────────────────────────────────────────────

    def get_job_state(self, job_id: str) -> Optional[dict]:
        return self._get_json(self.output_bucket, self._job_key(job_id, "job_state.json"))

    def save_job_state(self, job_id: str, state: dict) -> bool:
        return self._put_json(self.output_bucket, self._job_key(job_id, "job_state.json"), state)

    # ── Output ─────────────────────────────────────────────────────────

    def get_output(self, job_id: str) -> Optional[dict]:
        return self._get_json(self.output_bucket, self._job_key(job_id, "output.json"))

    def save_output(self, job_id: str, data: dict) -> bool:
        return self._put_json(self.output_bucket, self._job_key(job_id, "output.json"), data)

    def get_output_flat(self, job_id: str) -> Optional[dict]:
        return self._get_json(self.output_bucket, self._job_key(job_id, "output_flat.json"))

    def save_output_flat(self, job_id: str, data: dict) -> bool:
        return self._put_json(self.output_bucket, self._job_key(job_id, "output_flat.json"), data)

    # ── Logs ───────────────────────────────────────────────────────────

    def save_execution_log(self, job_id: str, data: dict) -> bool:
        return self._put_json(self.output_bucket, self._job_key(job_id, "execution_log.json"), data)

    def get_execution_log(self, job_id: str) -> Optional[dict]:
        return self._get_json(self.output_bucket, self._job_key(job_id, "execution_log.json"))

    # ── Config / document ──────────────────────────────────────────────

    def load_schema(self, schema_path: str) -> dict:
        """
        schema_path can be:
          - s3://bucket/path/to/form_keys.json   -> used as-is
          - a bare filename "form_keys.json"      -> loaded from config_bucket
        """
        if schema_path.startswith("s3://"):
            bucket, key = _parse_s3_uri(schema_path)
            data = self._get_json(bucket, key)
        else:
            data = self._get_json(self.config_bucket, schema_path)
        if data is None:
            raise FileNotFoundError(f"Schema not found: {schema_path}")
        return data

    def download_document(self, source_path: str, local_dest: str) -> str:
        """Download from S3 URI or local path to local_dest."""
        if source_path.startswith("s3://"):
            bucket, key = _parse_s3_uri(source_path)
            self.s3.download_file(bucket, key, local_dest)
        else:
            import shutil
            shutil.copy2(source_path, local_dest)
        return local_dest

    def upload_file(self, local_path: str, dest_path: str) -> bool:
        """Upload local file to S3 URI."""
        try:
            bucket, key = _parse_s3_uri(dest_path)
            self.s3.upload_file(local_path, bucket, key)
            return True
        except Exception as e:
            print(f"❌ S3 upload error: {e}")
            return False
