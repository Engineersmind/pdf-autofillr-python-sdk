from ragpdf.storage.base import StorageBackend


class StorageFactory:
    """Create a storage backend from environment variables."""

    @staticmethod
    def create() -> StorageBackend:
        from ragpdf.config.settings import (
            RAGPDF_STORAGE, RAGPDF_DATA_PATH,
            RAGPDF_S3_BUCKET, RAGPDF_S3_REGION, RAGPDF_S3_PREFIX,
            RAGPDF_AZURE_ACCOUNT, RAGPDF_AZURE_CONTAINER, RAGPDF_AZURE_CONN_STR,
            RAGPDF_GCS_BUCKET, RAGPDF_GCS_PREFIX,
        )
        if RAGPDF_STORAGE == "s3":
            from ragpdf.storage.s3_storage import S3Storage
            return S3Storage(bucket=RAGPDF_S3_BUCKET, region=RAGPDF_S3_REGION, prefix=RAGPDF_S3_PREFIX)

        if RAGPDF_STORAGE == "azure":
            from ragpdf.storage.azure_storage import AzureStorage
            return AzureStorage(account=RAGPDF_AZURE_ACCOUNT, container=RAGPDF_AZURE_CONTAINER, conn_str=RAGPDF_AZURE_CONN_STR)

        if RAGPDF_STORAGE == "gcs":
            from ragpdf.storage.gcs_storage import GCSStorage
            return GCSStorage(bucket=RAGPDF_GCS_BUCKET, prefix=RAGPDF_GCS_PREFIX)

        from ragpdf.storage.local_storage import LocalStorage
        return LocalStorage(data_path=RAGPDF_DATA_PATH)
