"""
Storage Interface - Abstract storage operations for multi-cloud support.

Provides a unified interface for S3, Azure Blob Storage, Google Cloud Storage, and local file systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, BinaryIO, List
from enum import Enum


class StorageProvider(Enum):
    """Supported storage providers."""
    AWS_S3 = "aws"
    AZURE_BLOB = "azure"
    GCP_STORAGE = "gcp"
    LOCAL = "local"


@dataclass
class StorageConfig:
    """Configuration for storage operations."""
    
    provider: StorageProvider
    bucket_name: Optional[str] = None  # S3 bucket, Azure container, GCS bucket
    region: Optional[str] = None  # AWS region, Azure region, GCP region
    prefix: Optional[str] = None  # Key prefix / path prefix
    
    # Provider-specific credentials (optional - can use environment)
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    connection_string: Optional[str] = None
    
    # Local storage
    local_base_path: Optional[str] = None
    
    # Additional options
    encryption: bool = False
    public_read: bool = False
    metadata: Optional[Dict[str, str]] = None


class StorageInterface(ABC):
    """
    Abstract interface for storage operations.
    
    All modules should use this interface instead of directly calling
    cloud provider SDKs. This enables:
    - Multi-cloud support
    - Easy testing with mocks
    - Consistent error handling
    - Portable code
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize storage with configuration.
        
        Args:
            config: Storage configuration
        """
        self.config = config
    
    @abstractmethod
    def upload_file(
        self,
        file_path: str,
        key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload a file to storage.
        
        Args:
            file_path: Local file path to upload
            key: Storage key (S3 key, blob name, GCS object name)
            metadata: Optional metadata to attach
            
        Returns:
            Storage URL or path
        """
        pass
    
    @abstractmethod
    def upload_bytes(
        self,
        data: bytes,
        key: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload bytes to storage.
        
        Args:
            data: Bytes to upload
            key: Storage key
            metadata: Optional metadata to attach
            
        Returns:
            Storage URL or path
        """
        pass
    
    @abstractmethod
    def download_file(
        self,
        key: str,
        local_path: str
    ) -> str:
        """
        Download a file from storage.
        
        Args:
            key: Storage key
            local_path: Local path to save file
            
        Returns:
            Local file path
        """
        pass
    
    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """
        Download file as bytes.
        
        Args:
            key: Storage key
            
        Returns:
            File bytes
        """
        pass
    
    @abstractmethod
    def get_download_url(
        self,
        key: str,
        expiration: int = 3600
    ) -> str:
        """
        Get a presigned/temporary download URL.
        
        Args:
            key: Storage key
            expiration: URL expiration in seconds
            
        Returns:
            Temporary download URL
        """
        pass
    
    @abstractmethod
    def get_upload_url(
        self,
        key: str,
        expiration: int = 3600
    ) -> str:
        """
        Get a presigned/temporary upload URL.
        
        Args:
            key: Storage key
            expiration: URL expiration in seconds
            
        Returns:
            Temporary upload URL
        """
        pass
    
    @abstractmethod
    def delete_file(self, key: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            key: Storage key
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            key: Storage key
            
        Returns:
            True if exists, False otherwise
        """
        pass
    
    @abstractmethod
    def list_files(
        self,
        prefix: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[str]:
        """
        List files in storage.
        
        Args:
            prefix: Optional prefix to filter
            max_results: Maximum number of results
            
        Returns:
            List of storage keys
        """
        pass
    
    @abstractmethod
    def get_metadata(self, key: str) -> Dict[str, Any]:
        """
        Get file metadata.
        
        Args:
            key: Storage key
            
        Returns:
            Metadata dictionary
        """
        pass
    
    @abstractmethod
    def copy_file(
        self,
        source_key: str,
        dest_key: str
    ) -> str:
        """
        Copy a file within storage.
        
        Args:
            source_key: Source storage key
            dest_key: Destination storage key
            
        Returns:
            Destination URL or path
        """
        pass


# =============================================================================
# Factory Pattern for Storage
# =============================================================================

def create_storage(config: StorageConfig) -> StorageInterface:
    """
    Factory function to create appropriate storage implementation.
    
    Args:
        config: Storage configuration
        
    Returns:
        StorageInterface implementation
        
    Raises:
        ValueError: If provider is not supported
    """
    if config.provider == StorageProvider.AWS_S3:
        from .storage_aws import S3Storage
        return S3Storage(config)
    
    elif config.provider == StorageProvider.AZURE_BLOB:
        from .storage_azure import AzureBlobStorage
        return AzureBlobStorage(config)
    
    elif config.provider == StorageProvider.GCP_STORAGE:
        from .storage_gcp import GCSStorage
        return GCSStorage(config)
    
    elif config.provider == StorageProvider.LOCAL:
        from .storage_local import LocalStorage
        return LocalStorage(config)
    
    else:
        raise ValueError(f"Unsupported storage provider: {config.provider}")
