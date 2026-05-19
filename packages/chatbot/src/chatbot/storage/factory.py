# chatbot/storage/factory.py
"""StorageFactory — creates the correct backend from env config."""
from __future__ import annotations
import os
from chatbot.storage.base import StorageBackend


class StorageFactory:
    @staticmethod
    def create(storage_type: str = None, **kwargs) -> StorageBackend:
        storage_type = (storage_type or os.getenv("chatbot_STORAGE", "local")).lower()

        if storage_type == "local":
            from chatbot.storage.local_storage import LocalStorage
            return LocalStorage(
                data_path=kwargs.get("data_path", os.getenv("chatbot_DATA_PATH", "./data/chatbot")),
                config_path=kwargs.get("config_path", os.getenv("chatbot_CONFIG_PATH", "./configs")),
            )

        if storage_type == "s3":
            from chatbot.storage.s3_storage import S3Storage
            return S3Storage(
                output_bucket=kwargs.get("output_bucket", os.environ["AWS_OUTPUT_BUCKET"]),
                config_bucket=kwargs.get("config_bucket", os.environ["AWS_CONFIG_BUCKET"]),
                region=kwargs.get("region", os.getenv("AWS_REGION", "us-east-1")),
            )

        if storage_type == "gcp":
            from chatbot.storage.gcp_storage import GCSStorage
            return GCSStorage(
                output_bucket=kwargs.get("output_bucket", os.environ["GCP_OUTPUT_BUCKET"]),
                config_bucket=kwargs.get("config_bucket", os.environ["GCP_CONFIG_BUCKET"]),
                project=kwargs.get("project", os.getenv("GCP_PROJECT_ID")),
            )

        if storage_type == "azure":
            from chatbot.storage.azure_storage import AzureStorage
            return AzureStorage(
                output_container=kwargs.get("output_container", os.environ["AZURE_OUTPUT_CONTAINER"]),
                config_container=kwargs.get("config_container", os.environ["AZURE_CONFIG_CONTAINER"]),
                connection_string=kwargs.get(
                    "connection_string", os.environ["AZURE_STORAGE_CONNECTION_STRING"]
                ),
            )

        raise ValueError(
            f"Unknown storage type: {storage_type!r}. "
            "Use 'local', 's3', 'gcp', or 'azure'."
        )
