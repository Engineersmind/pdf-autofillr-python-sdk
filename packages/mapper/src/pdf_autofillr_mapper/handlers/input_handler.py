"""

Input File Handler - Downloads/copies input files from source storage.

This handler detects the source type (local/aws/azure/gcp) and automatically
downloads files to the processing directory before operations start.

Usage in operations:
    from pdf_autofillr_mapper.handlers.input_handler import InputFileHandler

    handler = InputFileHandler(config)

    # Download a file:
    local_path = handler.get_input('input_pdf')
    # Returns: /tmp/processing/file.pdf (already downloaded)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class InputFileHandler:
    """
    Handles downloading/copying input files from source storage based on source type.

    For local storage: copies from input directory
    For AWS: downloads from S3
    For Azure: downloads from Blob Storage
    For GCP: downloads from Cloud Storage
    """

    def __init__(self, config):
        """
        Initialize input handler.

        Args:
            config: Storage config (LocalStorageConfig, AWSStorageConfig, etc.)
        """
        self.config = config
        self.source_type = config.source_type
        logger.info(f"InputFileHandler initialized for source_type: {self.source_type}")

    def get_input(
        self,
        file_type: str,
        source_path: Optional[str] = None,
        local_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get input file - downloads if needed, returns local path.

        Args:
            file_type: Type of file (e.g., 'input_pdf', 'input_json', 'extracted_json')
            source_path: Optional explicit source path (overrides auto-detection)
            local_path: Optional local destination path (overrides config path)

        Returns:
            Local path where file is available for operations

        Example:
            # Get input PDF (already downloaded by entrypoint usually)
            pdf_path = handler.get_input('input_pdf')
            # Returns: /tmp/processing/553_990_input.pdf

            # Download specific S3 file
            extracted_path = handler.download_input(
                's3://bucket/path/file.json',
                '/tmp/processing/extracted.json'
            )
        """
        if not local_path:
            local_path = self._get_local_path(file_type)

        if not local_path:
            logger.warning(f"No local path configured for {file_type}")
            return None

        if os.path.exists(local_path):
            logger.debug(f"File already available locally: {local_path}")
            return local_path

        if not source_path:
            source_path = self._get_source_path(file_type)

        if not source_path:
            logger.warning(f"No source path configured for {file_type}")
            return None

        return self.download_input(source_path, local_path)

    def download_input(self, source_path: str, local_path: str) -> Optional[str]:
        """
        Download input file from source storage.
        Automatically detects storage type from path prefix.

        Args:
            source_path: Path in source storage (s3://, azure://, gs://, or /local/path)
            local_path: Destination path in /tmp/processing/

        Returns:
            Local path where file was downloaded
        """
        if not source_path:
            logger.warning("No source path provided")
            return None

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        if source_path.startswith("s3://"):
            logger.debug(f"Detected S3 path: {source_path}")
            return self._download_aws(source_path, local_path)
        elif source_path.startswith("gs://"):
            logger.debug(f"Detected GCS path: {source_path}")
            return self._download_gcp(source_path, local_path)
        elif source_path.startswith("azure://") or (
            "blob.core.windows.net" in source_path
            and source_path.startswith("https://")
        ):
            logger.debug(f"Detected Azure path: {source_path}")
            return self._download_azure(source_path, local_path)
        else:
            logger.debug(
                f"Using configured source type ({self.source_type}) for: {source_path}"
            )
            if self.source_type == "local":
                return self._download_local(source_path, local_path)
            elif self.source_type == "aws":
                return self._download_aws(source_path, local_path)
            elif self.source_type == "azure":
                return self._download_azure(source_path, local_path)
            elif self.source_type == "gcp":
                return self._download_gcp(source_path, local_path)
            else:
                logger.error(f"Unknown source type: {self.source_type}")
                return None

    def _get_local_path(self, file_type: str) -> Optional[str]:
        """
        Get local path from config based on file type.

        Maps file_type to config.local_* attributes:
            - input_pdf -> config.local_input_pdf
            - input_json -> config.local_input_json
            - extracted_json -> config.local_extracted_json
            - etc.
        """
        attr_name = f"local_{file_type}"
        local_path = getattr(self.config, attr_name, None)

        if not local_path:
            logger.debug(f"No local path found in config.{attr_name}")

        return local_path

    def _get_source_path(self, file_type: str) -> Optional[str]:
        """
        Get source path from config based on file type and source type.

        Maps file_type to source-specific attributes:
            AWS: input_pdf -> config.s3_input_pdf
            Azure: input_pdf -> config.blob_input_pdf
            GCP: input_pdf -> config.gcs_input_pdf
            Local: input_pdf -> config.source_input_pdf (if set)
        """
        if self.source_type == "aws":
            attr_name = f"s3_{file_type}"
        elif self.source_type == "azure":
            attr_name = f"blob_{file_type}"
        elif self.source_type == "gcp":
            attr_name = f"gcs_{file_type}"
        elif self.source_type == "local":
            attr_name = f"source_{file_type}"
        else:
            return None

        source_path = getattr(self.config, attr_name, None)

        if not source_path:
            logger.debug(f"No source path found in config.{attr_name}")

        return source_path

    def _download_local(self, source_path: str, local_path: str) -> Optional[str]:
        """
        Download from local file system (copy file).

        Example:
            ../../data/input/file.pdf -> /tmp/processing/file.pdf
        """
        try:
            self.config.download_file(source_path, local_path)
            logger.info(f"✅ Copied from local: {source_path} -> {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to copy local file: {e}", exc_info=True)
            return None

    def _download_aws(self, source_path: str, local_path: str) -> Optional[str]:
        """
        Download from AWS S3.

        Example:
            s3://bucket/path/file.pdf -> /tmp/processing/file.pdf
        """
        try:
            from pdf_autofillr_mapper.configs.aws import AWSStorageConfig

            if hasattr(self.config, "s3_client") and self.config.source_type == "aws":
                self.config.download_file(source_path, local_path)
            else:
                aws_config = AWSStorageConfig()
                aws_config.download_file(source_path, local_path)

            logger.info(f"✅ Downloaded from S3: {source_path} -> {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to download from S3: {e}", exc_info=True)
            return None

    def _download_azure(self, source_path: str, local_path: str) -> Optional[str]:
        """
        Download from Azure Blob Storage.

        Example:
            azure://container/path/file.pdf -> /tmp/processing/file.pdf
        """
        try:
            from pdf_autofillr_mapper.configs.azure import AzureStorageConfig

            if (
                hasattr(self.config, "blob_client")
                and self.config.source_type == "azure"
            ):
                self.config.download_file(source_path, local_path)
            else:
                azure_config = AzureStorageConfig()
                azure_config.download_file(source_path, local_path)

            logger.info(f"✅ Downloaded from Azure: {source_path} -> {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to download from Azure: {e}", exc_info=True)
            return None

    def _download_gcp(self, source_path: str, local_path: str) -> Optional[str]:
        """
        Download from GCP Cloud Storage.

        Example:
            gs://bucket/path/file.pdf -> /tmp/processing/file.pdf
        """
        try:
            from pdf_autofillr_mapper.configs.gcp import GCPStorageConfig

            if hasattr(self.config, "gcs_client") and self.config.source_type == "gcp":
                self.config.download_file(source_path, local_path)
            else:
                gcp_config = GCPStorageConfig()
                gcp_config.download_file(source_path, local_path)

            logger.info(f"✅ Downloaded from GCS: {source_path} -> {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}", exc_info=True)
            return None

    def download_multiple_inputs(self, file_mappings: dict) -> dict:
        """
        Download multiple input files at once.

        Args:
            file_mappings: Dict mapping file_type to source_path
                {
                    'input_pdf': 's3://bucket/path/file.pdf',
                    'input_json': 's3://bucket/path/input.json'
                }

        Returns:
            Dict mapping file_type to local_path
        """
        results = {}

        for file_type, source_path in file_mappings.items():
            local_path = self._get_local_path(file_type)
            if local_path:
                downloaded = self.download_input(source_path, local_path)
                if downloaded:
                    results[file_type] = downloaded

        return results


def create_input_handler(config):
    """
    Factory function to create InputFileHandler from config.

    Args:
        config: Storage config (LocalStorageConfig, AWSStorageConfig, etc.)

    Returns:
        InputFileHandler instance
    """
    return InputFileHandler(config)
