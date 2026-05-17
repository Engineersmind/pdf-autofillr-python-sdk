# chatbot/storage/azure_storage.py
"""
AzureStorage — Azure Blob Storage backend.

Identical file layout to LocalStorage and S3Storage.

Requires:  pip install "pdf-autofillr-chatbot[azure]"
           azure-storage-blob>=12.19.0

Env vars (set in .env):
    AZURE_STORAGE_CONNECTION_STRING  full connection string
    AZURE_OUTPUT_CONTAINER           container for session data (read/write)
    AZURE_CONFIG_CONTAINER           container for form config JSONs (read-only)
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from chatbot.storage.base import StorageBackend

try:
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ResourceNotFoundError
    _AZURE_AVAILABLE = True
except ImportError:
    _AZURE_AVAILABLE = False


class AzureStorage(StorageBackend):
    """
    Uses two Azure Blob containers:

    - ``output_container``: session data (read/write)
    - ``config_container``: form config files (read-only)

    Auth via AZURE_STORAGE_CONNECTION_STRING.
    """

    def __init__(
        self,
        output_container: str,
        config_container: str,
        connection_string: str,
    ):
        if not _AZURE_AVAILABLE:
            raise ImportError(
                "azure-storage-blob is required for AzureStorage.\n"
                "Install it with: pip install 'pdf-autofillr-chatbot[azure]'"
            )
        self.output_container = output_container
        self.config_container = config_container
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._out = self._service.get_container_client(output_container)
        self._cfg = self._service.get_container_client(config_container)

    # ── Helpers ───────────────────────────────────────────────────────

    def _get(self, container_client, key: str) -> Optional[Any]:
        try:
            blob = container_client.get_blob_client(key)
            data = blob.download_blob().readall().decode("utf-8")
            return json.loads(data)
        except ResourceNotFoundError:
            return None
        except Exception as e:
            print(f"❌ AzureStorage get error {key}: {e}")
            return None

    def _put(self, container_client, key: str, data: Any) -> bool:
        try:
            blob = container_client.get_blob_client(key)
            blob.upload_blob(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                overwrite=True,
                content_settings=None,
            )
            return True
        except Exception as e:
            print(f"❌ AzureStorage put error {key}: {e}")
            return False

    def _sk(self, user_id: str, session_id: str, filename: str) -> str:
        return f"{user_id}/sessions/{session_id}/{filename}"

    def _uk(self, user_id: str, filename: str) -> str:
        return f"{user_id}/{filename}"

    # ── Session state ─────────────────────────────────────────────────

    def get_session_state(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "session_state.json"))

    def save_session_state(self, user_id, session_id, state):
        return self._put(self._out, self._sk(user_id, session_id, "session_state.json"), state)

    # ── User integrated info ──────────────────────────────────────────

    def get_user_integrated_info(self, user_id):
        data = self._get(self._out, self._uk(user_id, "user_integrated_information.json"))
        return data.get("data", data) if isinstance(data, dict) else data

    def save_user_integrated_info(self, user_id, data):
        return self._put(self._out, self._uk(user_id, "user_integrated_information.json"), {"data": data})

    # ── Final output ──────────────────────────────────────────────────

    def get_final_output(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "final_output.json"))

    def save_final_output(self, user_id, session_id, data):
        return self._put(self._out, self._sk(user_id, session_id, "final_output.json"), data)

    def get_final_output_flat(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "final_output_flat.json"))

    def save_final_output_flat(self, user_id, session_id, data):
        return self._put(self._out, self._sk(user_id, session_id, "final_output_flat.json"), data)

    # ── Session history ───────────────────────────────────────────────

    def get_session_history(self, user_id):
        return self._get(self._out, self._uk(user_id, "session_history.json"))

    def save_session_history(self, user_id, history):
        return self._put(self._out, self._uk(user_id, "session_history.json"), history)

    # ── Logs ──────────────────────────────────────────────────────────

    def save_conversation_log(self, user_id, session_id, data):
        return self._put(self._out, self._sk(user_id, session_id, "conversation_log.json"), data)

    def save_debug_conversation(self, user_id, session_id, data):
        return self._put(self._out, self._sk(user_id, session_id, "debug_conversation.json"), data)

    def get_debug_conversation(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "debug_conversation.json"))

    def get_pdf_filling_logs(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "calling_filling_logs.json"))

    def save_pdf_filling_logs(self, user_id, session_id, data):
        return self._put(self._out, self._sk(user_id, session_id, "calling_filling_logs.json"), data)

    # ── Fill report ───────────────────────────────────────────────────

    def get_fill_report(self, user_id, session_id):
        return self._get(self._out, self._sk(user_id, session_id, "fill_report.json"))

    def save_fill_report(self, user_id, session_id, data):
        return self._put(self._out, self._sk(user_id, session_id, "fill_report.json"), data)

    # ── Utility ───────────────────────────────────────────────────────

    def list_user_sessions(self, user_id: str) -> List[str]:
        prefix = f"{user_id}/sessions/"
        blobs = self._out.list_blobs(name_starts_with=prefix)
        seen = set()
        for blob in blobs:
            parts = blob.name[len(prefix):].split("/")
            if parts:
                seen.add(parts[0])
        return list(seen)

    def delete_session(self, user_id: str, session_id: str) -> bool:
        prefix = f"{user_id}/sessions/{session_id}/"
        blobs = list(self._out.list_blobs(name_starts_with=prefix))
        for blob in blobs:
            self._out.get_blob_client(blob.name).delete_blob()
        return True

    # ── Config loaders ────────────────────────────────────────────────

    def load_config(self, filename: str) -> dict:
        data = self._get(self._cfg, filename)
        if data is None:
            raise FileNotFoundError(f"Config not found in Azure: {self.config_container}/{filename}")
        return data

    def load_investor_type_config(self, filename: str) -> dict:
        data = self._get(self._cfg, f"global_investor_type_keys/{filename}")
        if data is None:
            return self.load_config("form_keys.json")
        return data