# pdf_autofillr_doc_upload/storage/azure_storage.py
"""
AzureStorage — Azure Blob Storage backend.

Env vars::
    AZURE_OUTPUT_CONTAINER
    AZURE_CONFIG_CONTAINER
    AZURE_STORAGE_CONNECTION_STRING
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from pdf_autofillr_doc_upload.storage.base import StorageBackend


class AzureStorage(StorageBackend):
    """Azure Blob Storage backend."""

    def __init__(
        self,
        output_container: str,
        config_container: str,
        connection_string: str,
    ):
        from azure.storage.blob import BlobServiceClient

        self.output_container = output_container
        self.config_container = config_container
        self.service = BlobServiceClient.from_connection_string(connection_string)

    def _get_json(self, container: str, blob_name: str) -> dict | None:
        try:
            client = self.service.get_blob_client(container=container, blob=blob_name)
            data = client.download_blob().readall()
            return json.loads(data)
        except Exception as e:
            if "BlobNotFound" in str(e) or "404" in str(e):
                return None
            print(f"❌ Azure read error {container}/{blob_name}: {e}")
            return None

    def _put_json(self, container: str, blob_name: str, data: dict) -> bool:
        try:
            client = self.service.get_blob_client(container=container, blob=blob_name)
            client.upload_blob(
                json.dumps(data, indent=2, default=str),
                overwrite=True,
                content_settings=None,
            )
            return True
        except Exception as e:
            print(f"❌ Azure write error {container}/{blob_name}: {e}")
            return False

    def _job_key(self, job_id: str, filename: str) -> str:
        return f"jobs/{job_id}/{filename}"

    def get_job_state(self, job_id):
        return self._get_json(
            self.output_container, self._job_key(job_id, "job_state.json")
        )

    def save_job_state(self, job_id, state):
        return self._put_json(
            self.output_container, self._job_key(job_id, "job_state.json"), state
        )

    def get_output(self, job_id):
        return self._get_json(
            self.output_container, self._job_key(job_id, "output.json")
        )

    def save_output(self, job_id, data):
        return self._put_json(
            self.output_container, self._job_key(job_id, "output.json"), data
        )

    def get_output_flat(self, job_id):
        return self._get_json(
            self.output_container, self._job_key(job_id, "output_flat.json")
        )

    def save_output_flat(self, job_id, data):
        return self._put_json(
            self.output_container, self._job_key(job_id, "output_flat.json"), data
        )

    def save_execution_log(self, job_id, data):
        return self._put_json(
            self.output_container, self._job_key(job_id, "execution_log.json"), data
        )

    def get_execution_log(self, job_id):
        return self._get_json(
            self.output_container, self._job_key(job_id, "execution_log.json")
        )

    def load_schema(self, schema_path: str) -> dict:
        data = self._get_json(self.config_container, schema_path)
        if data is None:
            raise FileNotFoundError(f"Schema not found in Azure: {schema_path}")
        return data

    def download_document(self, source_path: str, local_dest: str) -> str:
        _parsed = urlparse(source_path)
        if (
            (_parsed.hostname or "").endswith(".blob.core.windows.net")
            and _parsed.scheme == "https"
        ) or source_path.startswith("azure://"):
            # Parse azure:// URI or HTTPS blob URL
            blob_name = source_path.split("/")[-1]
            client = self.service.get_blob_client(
                container=self.output_container, blob=blob_name
            )
            with open(local_dest, "wb") as f:
                f.write(client.download_blob().readall())
        else:
            import shutil

            shutil.copy2(source_path, local_dest)
        return local_dest

    def upload_file(self, local_path: str, dest_path: str) -> bool:
        try:
            blob_name = dest_path.lstrip("/")
            client = self.service.get_blob_client(
                container=self.output_container, blob=blob_name
            )
            with open(local_path, "rb") as f:
                client.upload_blob(f, overwrite=True)
            return True
        except Exception as e:
            print(f"❌ Azure upload error: {e}")
            return False
