# chatbot/storage/s3_storage.py
"""
S3Storage — AWS S3 backend.
Identical JSON key layout to LocalStorage.

Key pattern:
    {user_id}/sessions/{session_id}/{filename}
    {user_id}/{filename}

Requires: pip install "pdf-autofillr-chatbot[s3]"
Env vars: AWS_OUTPUT_BUCKET, AWS_CONFIG_BUCKET, AWS_REGION,
          AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (or AWS_PROFILE or IAM role)
"""

from __future__ import annotations

import json
from typing import Any

from chatbot.storage.base import StorageBackend

try:
    import boto3
    from botocore.exceptions import ClientError

    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


class S3Storage(StorageBackend):

    def __init__(
        self, output_bucket: str, config_bucket: str, region: str = "us-east-1"
    ):
        if not _BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3Storage.\n"
                "Install: pip install 'pdf-autofillr-chatbot[s3]'"
            )
        self.output_bucket = output_bucket
        self.config_bucket = config_bucket
        self.s3 = boto3.client("s3", region_name=region)

    # ── Helpers ────────────────────────────────────────────────────────

    def _get(self, bucket: str, key: str) -> Any | None:
        try:
            resp = self.s3.get_object(Bucket=bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def _put(self, bucket: str, key: str, data: Any) -> bool:
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data, ensure_ascii=False, indent=2, default=str),
                ContentType="application/json",
            )
            return True
        except ClientError as e:
            print(f"❌ S3Storage put error {key}: {e}")
            return False

    def _sk(self, user_id: str, session_id: str, filename: str) -> str:
        return f"{user_id}/sessions/{session_id}/{filename}"

    def _uk(self, user_id: str, filename: str) -> str:
        return f"{user_id}/{filename}"

    # ── Session state ──────────────────────────────────────────────────

    def get_session_state(self, user_id, session_id):
        return self._get(
            self.output_bucket, self._sk(user_id, session_id, "session_state.json")
        )

    def save_session_state(self, user_id, session_id, state):
        return self._put(
            self.output_bucket,
            self._sk(user_id, session_id, "session_state.json"),
            state,
        )

    # ── User integrated info ───────────────────────────────────────────

    def get_user_integrated_info(self, user_id):
        data = self._get(
            self.output_bucket, self._uk(user_id, "user_integrated_information.json")
        )
        return data.get("data", data) if isinstance(data, dict) else data

    def save_user_integrated_info(self, user_id, data):
        return self._put(
            self.output_bucket,
            self._uk(user_id, "user_integrated_information.json"),
            {"data": data},
        )

    # ── Final output ───────────────────────────────────────────────────

    def get_final_output(self, user_id, session_id):
        return self._get(
            self.output_bucket, self._sk(user_id, session_id, "final_output.json")
        )

    def save_final_output(self, user_id, session_id, data):
        return self._put(
            self.output_bucket, self._sk(user_id, session_id, "final_output.json"), data
        )

    def get_final_output_flat(self, user_id, session_id):
        return self._get(
            self.output_bucket, self._sk(user_id, session_id, "final_output_flat.json")
        )

    def save_final_output_flat(self, user_id, session_id, data):
        return self._put(
            self.output_bucket,
            self._sk(user_id, session_id, "final_output_flat.json"),
            data,
        )

    # ── Session history ────────────────────────────────────────────────

    def get_session_history(self, user_id):
        return self._get(self.output_bucket, self._uk(user_id, "session_history.json"))

    def save_session_history(self, user_id, history):
        return self._put(
            self.output_bucket, self._uk(user_id, "session_history.json"), history
        )

    # ── Logs ───────────────────────────────────────────────────────────

    def save_conversation_log(self, user_id, session_id, data):
        return self._put(
            self.output_bucket,
            self._sk(user_id, session_id, "conversation_log.json"),
            data,
        )

    def save_debug_conversation(self, user_id, session_id, data):
        return self._put(
            self.output_bucket,
            self._sk(user_id, session_id, "debug_conversation.json"),
            data,
        )

    def get_debug_conversation(self, user_id, session_id):
        return self._get(
            self.output_bucket, self._sk(user_id, session_id, "debug_conversation.json")
        )

    def get_pdf_filling_logs(self, user_id, session_id):
        return self._get(
            self.output_bucket,
            self._sk(user_id, session_id, "calling_filling_logs.json"),
        )

    def save_pdf_filling_logs(self, user_id, session_id, data):
        return self._put(
            self.output_bucket,
            self._sk(user_id, session_id, "calling_filling_logs.json"),
            data,
        )

    # ── Fill report ────────────────────────────────────────────────────

    def get_fill_report(self, user_id, session_id):
        return self._get(
            self.output_bucket, self._sk(user_id, session_id, "fill_report.json")
        )

    def save_fill_report(self, user_id, session_id, data):
        return self._put(
            self.output_bucket, self._sk(user_id, session_id, "fill_report.json"), data
        )

    # ── Utility ────────────────────────────────────────────────────────

    def list_user_sessions(self, user_id: str) -> list[str]:
        """Paginated — handles buckets with >1000 objects."""
        prefix = f"{user_id}/sessions/"
        sessions = []
        paginator = self.s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(
                Bucket=self.output_bucket, Prefix=prefix, Delimiter="/"
            ):
                for cp in page.get("CommonPrefixes", []):
                    sessions.append(cp["Prefix"].replace(prefix, "").rstrip("/"))
        except ClientError:
            return []
        return sessions

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Paginated delete — handles sessions with >1000 objects."""
        prefix = f"{user_id}/sessions/{session_id}/"
        paginator = self.s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=self.output_bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    self.s3.delete_objects(
                        Bucket=self.output_bucket,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                    )
            return True
        except ClientError as e:
            print(f"❌ S3Storage delete error: {e}")
            return False

    # ── Config loaders ─────────────────────────────────────────────────

    def load_config(self, filename: str) -> dict:
        data = self._get(self.config_bucket, filename)
        if data is None:
            raise FileNotFoundError(
                f"Config not found in S3: {self.config_bucket}/{filename}"
            )
        return data

    def load_investor_type_config(self, filename: str) -> dict:
        data = self._get(self.config_bucket, f"global_investor_type_keys/{filename}")
        if data is None:
            return self.load_config("form_keys.json")
        return data
