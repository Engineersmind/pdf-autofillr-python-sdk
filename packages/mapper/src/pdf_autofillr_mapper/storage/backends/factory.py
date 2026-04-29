"""
StorageBackendFactory - builds the right storage backend from config.ini source_type.

Each backend only needs to implement: download_file, upload_file, file_exists.
"""

import logging

logger = logging.getLogger(__name__)

_BACKEND_CLASSES = {
    'aws':   'pdf_autofillr_mapper.configs.aws.AWSStorageConfig',
    'azure': 'pdf_autofillr_mapper.configs.azure.AzureStorageConfig',
    'gcp':   'pdf_autofillr_mapper.configs.gcp.GCPStorageConfig',
    'local': 'pdf_autofillr_mapper.configs.local.LocalStorageConfig',
}

_instances: dict = {}

# Backends that are fully implemented
_IMPLEMENTED = {'aws', 'azure', 'gcp', 'local'}

# Required env vars per backend (at least one must be set for cloud backends)
_CREDENTIAL_CHECKS = {
    'aws':   ['AWS_ACCESS_KEY_ID', 'AWS_ROLE_ARN'],   # IAM role OR access key
    'azure': ['AZURE_STORAGE_CONNECTION_STRING', 'AZURE_STORAGE_ACCOUNT'],
    'gcp':   ['GOOGLE_APPLICATION_CREDENTIALS', 'GOOGLE_CLOUD_PROJECT'],
}


def get_storage_backend(source_type: str):
    """
    Get (cached) storage backend for a given source type.

    Fails fast at startup if:
    - source_type is unknown
    - backend is not yet implemented (azure, gcp)
    - required credentials are missing from environment

    Args:
        source_type: 'aws', 'azure', 'gcp', or 'local'

    Returns:
        Storage backend with download_file / upload_file / file_exists
    """
    if source_type not in _BACKEND_CLASSES:
        raise ValueError(
            f"Unknown storage type: {source_type!r}. "
            f"Valid options: {list(_BACKEND_CLASSES)}"
        )

    if source_type not in _IMPLEMENTED:
        raise NotImplementedError(
            f"Storage backend {source_type!r} is not yet implemented. "
            f"Implemented backends: {sorted(_IMPLEMENTED)}. "
            f"To add support, implement download_file/upload_file/file_exists "
            f"in pdf_autofillr_mapper/configs/{source_type}.py."
        )

    # Credential check for cloud backends
    if source_type in _CREDENTIAL_CHECKS:
        import os
        required = _CREDENTIAL_CHECKS[source_type]
        if not any(os.getenv(var) for var in required):
            raise EnvironmentError(
                f"No credentials found for {source_type!r} storage backend. "
                f"Set at least one of: {required}"
            )

    if source_type not in _instances:
        import importlib
        module_path, class_name = _BACKEND_CLASSES[source_type].rsplit('.', 1)
        module = importlib.import_module(module_path)
        _instances[source_type] = getattr(module, class_name)()
        logger.debug(f"Created storage backend: {source_type}")

    return _instances[source_type]


def clear_cache():
    """Clear cached backend instances (useful for testing)."""
    _instances.clear()
