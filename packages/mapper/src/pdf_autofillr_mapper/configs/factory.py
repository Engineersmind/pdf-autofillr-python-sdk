"""
Storage configuration factory.

Automatically detects storage type from file path and returns appropriate config.
"""

import logging
from typing import Optional
from .base import BaseStorageConfig
from .aws import AWSStorageConfig
from .azure import AzureStorageConfig
from .gcp import GCPStorageConfig
from .local import LocalStorageConfig

logger = logging.getLogger(__name__)


class StorageFactory:
    """
    Factory for creating storage configuration objects.
    
    Detects storage type from file path prefix:
    - s3:// -> AWS S3
    - azure:// or https://*.blob.core.windows.net -> Azure Blob
    - gs:// -> Google Cloud Storage
    - / or ./ or ~/ -> Local filesystem
    """
    
    _instances = {}  # Cache storage config instances
    
    @classmethod
    def get_storage_config(cls, file_path: str, base_dir: Optional[str] = None) -> BaseStorageConfig:
        """
        Get appropriate storage configuration based on file path.
        
        Args:
            file_path: File path (with scheme prefix for cloud storage)
            base_dir: Optional base directory for local storage
            
        Returns:
            Storage configuration instance
            
        Raises:
            ValueError: If storage type cannot be determined
        """
        storage_type = cls._detect_storage_type(file_path)
        
        # Return cached instance if available (except local with custom base_dir)
        cache_key = storage_type if storage_type != "local" else f"local:{base_dir}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]
        
        # Create new instance
        if storage_type == "aws":
            instance = AWSStorageConfig()
        elif storage_type == "azure":
            instance = AzureStorageConfig()
        elif storage_type == "gcp":
            instance = GCPStorageConfig()
        elif storage_type == "local":
            instance = LocalStorageConfig(base_dir=base_dir)
        else:
            raise ValueError(f"Unknown storage type for path: {file_path}")
        
        # Cache and return
        cls._instances[cache_key] = instance
        logger.debug(f"Created storage config: {instance}")
        return instance
    
    @staticmethod
    def _detect_storage_type(file_path: str) -> str:
        """
        Detect storage type from file path.
        
        Args:
            file_path: File path to analyze
            
        Returns:
            Storage type: "aws", "azure", "gcp", or "local"
        """
        if file_path.startswith("s3://"):
            return "aws"
        elif file_path.startswith("azure://") or "blob.core.windows.net" in file_path:
            return "azure"
        elif file_path.startswith("gs://"):
            return "gcp"
        else:
            # Default to local for absolute paths, relative paths, etc.
            return "local"
    
    @classmethod
    def clear_cache(cls):
        """Clear cached storage config instances."""
        cls._instances.clear()
        logger.debug("Cleared storage config cache")


# Convenience function for easy access
def get_storage_config(file_path: str, base_dir: Optional[str] = None) -> BaseStorageConfig:
    """
    Get storage configuration for a file path.
    
    This is the main entry point for getting storage configs.
    
    Args:
        file_path: File path (with scheme for cloud storage)
        base_dir: Optional base directory for local storage
        
    Returns:
        Appropriate storage configuration instance
        
    Example:
        >>> storage = get_storage_config("s3://my-bucket/file.pdf")
        >>> storage.download_file("s3://my-bucket/file.pdf", "/tmp/file.pdf")
    """
    return StorageFactory.get_storage_config(file_path, base_dir)
