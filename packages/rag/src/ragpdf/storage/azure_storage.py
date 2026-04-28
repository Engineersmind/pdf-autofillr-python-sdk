"""
Azure Blob Storage backend.

Install: pip install ragpdf-sdk[azure]

Usage:
    storage = AzureStorage(account="myaccount", container="ragpdf")
    # OR with connection string:
    storage = AzureStorage(conn_str="DefaultEndpointsProtocol=https;...")

Credentials (pick one):
  - RAGPDF_AZURE_CONN_STR  -> connection string (easiest for local dev)
  - RAGPDF_AZURE_ACCOUNT   -> account name + DefaultAzureCredential (managed identity / CLI login)
"""
import json
import logging
from typing import Optional
from ragpdf.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class AzureStorage(StorageBackend):
    def __init__(self, account: str = "", container: str = "", conn_str: str = "", prefix: str = ""):
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            raise ImportError("AzureStorage requires azure-storage-blob. Install with: pip install ragpdf-sdk[azure]")

        from ragpdf.config.settings import RAGPDF_AZURE_ACCOUNT, RAGPDF_AZURE_CONTAINER, RAGPDF_AZURE_CONN_STR
        self._container = container or RAGPDF_AZURE_CONTAINER
        self._prefix    = prefix.rstrip("/") + "/" if prefix else ""

        conn = conn_str or RAGPDF_AZURE_CONN_STR
        acct = account  or RAGPDF_AZURE_ACCOUNT

        if conn:
            self._client = BlobServiceClient.from_connection_string(conn)
        elif acct:
            from azure.identity import DefaultAzureCredential
            url = f"https://{acct}.blob.core.windows.net"
            self._client = BlobServiceClient(account_url=url, credential=DefaultAzureCredential())
        else:
            raise ValueError("AzureStorage requires RAGPDF_AZURE_CONN_STR or RAGPDF_AZURE_ACCOUNT")

        self._container_client = self._client.get_container_client(self._container)
        try:
            self._container_client.create_container()
        except Exception:
            pass  # already exists
        logger.info(f"AzureStorage initialized: container={self._container}, prefix={self._prefix}")

    def _blob_name(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def save_json(self, key: str, data: dict) -> None:
        blob = self._container_client.get_blob_client(self._blob_name(key))
        blob.upload_blob(json.dumps(data, indent=2).encode("utf-8"), overwrite=True, content_settings=None)
        logger.debug(f"Azure saved: {self._blob_name(key)}")

    def load_json(self, key: str) -> Optional[dict]:
        try:
            blob = self._container_client.get_blob_client(self._blob_name(key))
            data = blob.download_blob().readall()
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def append_to_jsonl(self, key: str, data: dict) -> None:
        existing = ""
        try:
            blob = self._container_client.get_blob_client(self._blob_name(key))
            existing = blob.download_blob().readall().decode("utf-8")
        except Exception:
            pass
        blob = self._container_client.get_blob_client(self._blob_name(key))
        blob.upload_blob((existing + json.dumps(data) + "\n").encode("utf-8"), overwrite=True)

    def load_jsonl(self, key: str) -> list:
        try:
            blob = self._container_client.get_blob_client(self._blob_name(key))
            content = blob.download_blob().readall().decode("utf-8")
            return [json.loads(line) for line in content.strip().splitlines() if line.strip()]
        except Exception:
            return []

    def copy_file(self, source_key: str, dest_key: str) -> bool:
        try:
            src  = self._container_client.get_blob_client(self._blob_name(source_key))
            dst  = self._container_client.get_blob_client(self._blob_name(dest_key))
            dst.start_copy_from_url(src.url)
            return True
        except Exception:
            return False

    def load_json_from_path(self, full_path: str) -> Optional[dict]:
        if full_path.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(full_path)
            blob_name = parsed.path.lstrip("/")
            container_name = blob_name.split("/")[0]
            blob_name = "/".join(blob_name.split("/")[1:])
            cc = self._client.get_container_client(container_name)
            blob = cc.get_blob_client(blob_name)
            data = blob.download_blob().readall()
            return json.loads(data.decode("utf-8"))
        return self.load_json(full_path)
