# chatbot/storage/gcp_storage.py
"""
GCSStorage — Google Cloud Storage backend.
Identical JSON key layout to LocalStorage and S3Storage.

Key pattern:
    {user_id}/sessions/{session_id}/{filename}
    {user_id}/{filename}

Requires: pip install "pdf-autofillr-chatbot[gcp]"
Env vars: GOOGLE_APPLICATION_CREDENTIALS, GCP_OUTPUT_BUCKET,
          GCP_CONFIG_BUCKET, GCP_PROJECT_ID (optional)
"""

from __future__ import annotations

import json
from typing import Any

from chatbot.storage.base import StorageBackend

try:
    from google.cloud import storage as gcs
    from google.cloud.exceptions import NotFound

    _GCS_AVAILABLE = True
except ImportError:
    _GCS_AVAILABLE = False


class GCSStorage(StorageBackend):

    def __init__(
        self, output_bucket: str, config_bucket: str, project: str | None = None
    ):
        if not _GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage is required for GCSStorage.\n"
                "Install: pip install 'pdf-autofillr-chatbot[gcp]'"
            )
        self.output_bucket = output_bucket
        self.config_bucket = config_bucket
        self._client = gcs.Client(project=project)
        self._out = self._client.bucket(output_bucket)
        self._cfg = self._client.bucket(config_bucket)

    # ── Helpers ───────────────────────────────────────────────────────

    def _get(self, bucket, key: str) -> Any | None:
        try:
            blob = bucket.blob(key)
            data = blob.download_as_text(encoding="utf-8")
            return json.loads(data)
        except NotFound:
            return None
        except Exception as e:
            print(f"❌ GCSStorage get error {key}: {e}")
            return None

    def _put(self, bucket, key: str, data: Any) -> bool:
        try:
            blob = bucket.blob(key)
            blob.upload_from_string(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                content_type="application/json",
            )
            return True
        except Exception as e:
            print(f"❌ GCSStorage put error {key}: {e}")
            return False

    def _sk(self, user_id: str, session_id: str, filename: str) -> str:
        return f"{user_id}/sessions/{session_id}/{filename}"

    def _uk(self, user_id: str, filename: str) -> str:
        return f"{user_id}/{filename}"

    # ── Session state ─────────────────────────────────────────────────

    def get_session_state(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "session_state.json"))

    def save_session_state(self, user_id, session_id, state):
        return self._put(
            self._out, self._sk(user_id, session_id, "session_state.json"), state
        )

    # ── User integrated info ──────────────────────────────────────────

    def get_user_integrated_info(self, user_id):
        data = self._get(
            self._out, self._uk(user_id, "user_integrated_information.json")
        )
        return data.get("data", data) if isinstance(data, dict) else data

    def save_user_integrated_info(self, user_id, data):
        return self._put(
            self._out,
            self._uk(user_id, "user_integrated_information.json"),
            {"data": data},
        )

    # ── Final output ──────────────────────────────────────────────────

    def get_final_output(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "final_output.json"))

    def save_final_output(self, user_id, session_id, data):
        return self._put(
            self._out, self._sk(user_id, session_id, "final_output.json"), data
        )

    def get_final_output_flat(self, user_id, session_id):
        return self._get(
            self._out, self._sk(user_id, session_id, "final_output_flat.json")
        )

    def save_final_output_flat(self, user_id, session_id, data):
        return self._put(
            self._out, self._sk(user_id, session_id, "final_output_flat.json"), data
        )

    # ── Session history ───────────────────────────────────────────────

    def get_session_history(self, user_id):
        return self._get(self._out, self._uk(user_id, "session_history.json"))

    def save_session_history(self, user_id, history):
        return self._put(self._out, self._uk(user_id, "session_history.json"), history)

    # ── Logs ──────────────────────────────────────────────────────────

    def save_conversation_log(self, user_id, session_id, data):
        return self._put(
            self._out, self._sk(user_id, session_id, "conversation_log.json"), data
        )

    def save_debug_conversation(self, user_id, session_id, data):
        return self._put(
            self._out, self._sk(user_id, session_id, "debug_conversation.json"), data
        )

    def get_debug_conversation(self, user_id, session_id):
        return self._get(
            self._out, self._sk(user_id, session_id, "debug_conversation.json")
        )

    def get_pdf_filling_logs(self, user_id, session_id):
        return self._get(
            self._out, self._sk(user_id, session_id, "calling_filling_logs.json")
        )

    def save_pdf_filling_logs(self, user_id, session_id, data):
        return self._put(
            self._out, self._sk(user_id, session_id, "calling_filling_logs.json"), data
        )

    # ── Fill report ───────────────────────────────────────────────────

    def get_fill_report(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "fill_report.json"))

    def save_fill_report(self, user_id, session_id, data):
        return self._put(
            self._out, self._sk(user_id, session_id, "fill_report.json"), data
        )

    # ── Utility ───────────────────────────────────────────────────────

    def list_user_sessions(self, user_id: str) -> list[str]:
        """Uses pages() to correctly collect prefixes across all GCS pages."""
        prefix = f"{user_id}/sessions/"
        sessions = []
        iterator = self._client.list_blobs(
            self.output_bucket, prefix=prefix, delimiter="/"
        )
        for page in iterator.pages:
            for p in page.prefixes:
                session_id = p.replace(prefix, "").rstrip("/")
                if session_id:
                    sessions.append(session_id)
        return sessions

    def delete_session(self, user_id: str, session_id: str) -> bool:
        prefix = f"{user_id}/sessions/{session_id}/"
        try:
            blobs = list(self._client.list_blobs(self.output_bucket, prefix=prefix))
            for blob in blobs:
                blob.delete()
            return True
        except Exception as e:
            print(f"❌ GCSStorage delete error: {e}")
            return False

    # ── Config loaders ────────────────────────────────────────────────

    def load_config(self, filename: str) -> dict:
        data = self._get(self._cfg, filename)
        if data is None:
            raise FileNotFoundError(
                f"Config not found in GCS: {self.config_bucket}/{filename}"
            )
        return data

    def load_investor_type_config(self, filename: str) -> dict:
        data = self._get(self._cfg, f"global_investor_type_keys/{filename}")
        if data is None:
            return self.load_config("form_keys.json")
        return data
