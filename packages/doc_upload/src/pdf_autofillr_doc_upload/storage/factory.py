# pdf_autofillr_doc_upload/storage/factory.py
"""StorageFactory — creates the correct backend from env config."""

from __future__ import annotations

import os

from pdf_autofillr_doc_upload.storage.base import StorageBackend


class StorageFactory:
    @staticmethod
    def create(storage_type: str | None = None, **kwargs) -> StorageBackend:
        storage_type = (
            storage_type or os.getenv("DOC_UPLOAD_STORAGE", "local") or "local"
        ).lower()

        if storage_type == "local":
            from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

            env_roots = os.getenv("DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS", "")
            return LocalStorage(
                data_path=kwargs.get(
                    "data_path", os.getenv("DOC_UPLOAD_DATA_PATH", "./data/doc_upload")
                ),
                config_path=kwargs.get(
                    "config_path", os.getenv("DOC_UPLOAD_CONFIG_PATH", "./configs")
                ),
                document_roots=kwargs.get(
                    "document_roots",
                    [r for r in env_roots.split(",") if r.strip()] or None,
                ),
            )

        if storage_type == "s3":
            from pdf_autofillr_doc_upload.storage.s3_storage import S3Storage

            return S3Storage(
                output_bucket=kwargs.get(
                    "output_bucket", os.environ["AWS_OUTPUT_BUCKET"]
                ),
                config_bucket=kwargs.get(
                    "config_bucket", os.environ["AWS_CONFIG_BUCKET"]
                ),
                region=kwargs.get("region", os.getenv("AWS_REGION", "us-east-1")),
            )

        if storage_type == "gcp":
            from pdf_autofillr_doc_upload.storage.gcp_storage import GCSStorage

            return GCSStorage(
                output_bucket=kwargs.get(
                    "output_bucket", os.environ["GCP_OUTPUT_BUCKET"]
                ),
                config_bucket=kwargs.get(
                    "config_bucket", os.environ["GCP_CONFIG_BUCKET"]
                ),
                project=kwargs.get("project", os.getenv("GCP_PROJECT_ID")),
            )

        if storage_type == "azure":
            from pdf_autofillr_doc_upload.storage.azure_storage import AzureStorage

            return AzureStorage(
                output_container=kwargs.get(
                    "output_container", os.environ["AZURE_OUTPUT_CONTAINER"]
                ),
                config_container=kwargs.get(
                    "config_container", os.environ["AZURE_CONFIG_CONTAINER"]
                ),
                connection_string=kwargs.get(
                    "connection_string", os.environ["AZURE_STORAGE_CONNECTION_STRING"]
                ),
            )

        raise ValueError(
            f"Unknown storage type: {storage_type!r}. "
            "Use 'local', 's3', 'gcp', or 'azure'."
        )
