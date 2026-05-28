"""
Universal storage helper functions.

Provides source-agnostic download/upload operations for AWS, Azure, GCP, and local storage.
"""

import logging
import os
from typing import Optional

from pdf_autofillr_mapper.configs.factory import get_storage_config

logger = logging.getLogger(__name__)


def download_from_source(source_path: str, local_path: str) -> str:
    """
    Download file from any source (S3, Azure, GCS, or local) to local path.

    Automatically detects source type from path prefix:
    - s3:// -> AWS S3
    - azure:// or https://*.blob.core.windows.net -> Azure Blob
    - gs:// -> Google Cloud Storage
    - Local paths -> Copy to destination

    Args:
        source_path: Source file path (with scheme for cloud storage)
        local_path: Destination local file path

    Returns:
        Local file path where file was saved

    Example:
        >>> download_from_source("s3://my-bucket/file.pdf", "/tmp/file.pdf")
        '/tmp/file.pdf'

        >>> download_from_source("gs://my-bucket/file.pdf", "/tmp/file.pdf")
        '/tmp/file.pdf'

        >>> download_from_source("/source/file.pdf", "/tmp/file.pdf")
        '/tmp/file.pdf'
    """
    storage = get_storage_config(source_path)
    logger.info(
        f"Downloading from {storage.source_type}: {source_path} -> {local_path}"
    )

    # Create local directory if needed
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    return storage.download_file(source_path, local_path)


def upload_to_source(local_path: str, destination_path: str) -> str:
    """
    Upload file from local path to any destination (S3, Azure, GCS, or local).

    Automatically detects destination type from path prefix.

    Args:
        local_path: Local file path to upload
        destination_path: Destination path (with scheme for cloud storage)

    Returns:
        Destination path where file was uploaded

    Example:
        >>> upload_to_source("/tmp/file.pdf", "s3://my-bucket/output.pdf")
        's3://my-bucket/output.pdf'

        >>> upload_to_source("/tmp/file.pdf", "gs://my-bucket/output.pdf")
        'gs://my-bucket/output.pdf'

        >>> upload_to_source("/tmp/file.pdf", "/destination/output.pdf")
        '/destination/output.pdf'
    """
    storage = get_storage_config(destination_path)
    logger.info(
        f"Uploading to {storage.source_type}: {local_path} -> {destination_path}"
    )

    return storage.upload_file(local_path, destination_path)


def file_exists(file_path: str) -> bool:
    """
    Check if file exists at any source (S3, Azure, GCS, or local).

    Args:
        file_path: File path to check

    Returns:
        True if file exists, False otherwise

    Example:
        >>> file_exists("s3://my-bucket/file.pdf")
        True

        >>> file_exists("/local/path/file.pdf")
        False
    """
    storage = get_storage_config(file_path)
    return storage.file_exists(file_path)


def generate_output_path(
    input_path: str, suffix: str, extension: Optional[str] = None
) -> str:
    """
    Generate output file path based on input path, suffix, and optional extension.

    Works with any storage type.

    Args:
        input_path: Input file path
        suffix: Suffix to add (e.g., "_extracted", "_mapped")
        extension: Optional new extension (e.g., ".json", ".pdf")

    Returns:
        Generated output path

    Example:
        >>> generate_output_path("s3://bucket/file.pdf", "_extracted", ".json")
        's3://bucket/file_extracted.json'

        >>> generate_output_path("/local/file.pdf", "_filled")
        '/local/file_filled.pdf'
    """
    storage = get_storage_config(input_path)
    return storage.generate_output_path(input_path, suffix, extension)


def get_storage_type(file_path: str) -> str:
    """
    Get storage type for a file path.

    Args:
        file_path: File path to analyze

    Returns:
        Storage type: "aws", "azure", "gcp", or "local"

    Example:
        >>> get_storage_type("s3://my-bucket/file.pdf")
        'aws'

        >>> get_storage_type("/local/file.pdf")
        'local'
    """
    storage = get_storage_config(file_path)
    return storage.source_type


def create_storage_config(file_path: str) -> dict:
    """
    Create storage configuration dict for a file path.

    This is used by processing modules (extractor, mapper, etc.)

    Args:
        file_path: File path

    Returns:
        Storage configuration dict

    Example:
        >>> create_storage_config("s3://bucket/file.json")
        {'type': 's3', 'bucket': 'bucket', 'key': 'file.json', ...}

        >>> create_storage_config("/local/file.json")
        {'type': 'local', 'path': '/local/file.json', ...}
    """
    storage = get_storage_config(file_path)
    return storage.get_storage_config(file_path)
