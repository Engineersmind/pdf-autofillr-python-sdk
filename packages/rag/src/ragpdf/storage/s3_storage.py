# src/ragpdf/storage/s3_storage.py
import json
import logging

from ragpdf.storage.base import StorageBackend
from ragpdf.utils.helpers import safe_for_log

logger = logging.getLogger(__name__)


class S3Storage(StorageBackend):
    """
    AWS S3-backed storage. Uses your own bucket — the SDK never touches
    any external service; it calls boto3 with your credentials.

    Usage:
        storage = S3Storage(bucket="my-ragpdf-bucket", region="us-east-1")

    AWS credentials are resolved via the standard boto3 chain:
    env vars -> ~/.aws/credentials -> IAM role.
    """

    def __init__(self, bucket: str, region: str = "us-east-1", prefix: str = ""):
        try:
            import boto3
            from botocore.exceptions import ClientError

            self._ClientError = ClientError
        except ImportError as e:
            raise ImportError(
                "S3Storage requires boto3. Install with: pip install ragpdf-sdk[s3]"
            ) from e
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self._s3 = boto3.client("s3", region_name=region)

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def save_json(self, key: str, data: dict) -> None:
        self._s3.put_object(
            Bucket=self.bucket,
            Key=self._key(key),
            Body=json.dumps(data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        logger.debug(f"S3 saved: s3://{self.bucket}/{safe_for_log(self._key(key))}")

    def load_json(self, key: str) -> dict | None:
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(key))
            return json.loads(obj["Body"].read().decode("utf-8"))
        except self._ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise

    def append_to_jsonl(self, key: str, data: dict) -> None:
        existing = ""
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(key))
            existing = obj["Body"].read().decode("utf-8")
        except self._ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                raise
        self._s3.put_object(
            Bucket=self.bucket,
            Key=self._key(key),
            Body=(existing + json.dumps(data) + "\n").encode("utf-8"),
            ContentType="application/jsonl",
        )

    def load_jsonl(self, key: str) -> list:
        try:
            obj = self._s3.get_object(Bucket=self.bucket, Key=self._key(key))
            content = obj["Body"].read().decode("utf-8")
            return [
                json.loads(line)
                for line in content.strip().splitlines()
                if line.strip()
            ]
        except self._ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        try:
            self._s3.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": self._key(source_key)},
                Key=self._key(dest_key),
            )
            return True
        except Exception as e:
            logger.error(f"S3 copy failed: {e}")
            return False

    def load_json_from_path(self, full_path: str) -> dict | None:
        """Load from a full s3://bucket/key path."""
        if not full_path.startswith("s3://"):
            raise ValueError(f"Expected s3:// path, got: {full_path}")
        parts = full_path[5:].split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        try:
            obj = self._s3.get_object(Bucket=bucket, Key=key)
            return json.loads(obj["Body"].read().decode("utf-8"))
        except self._ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise
