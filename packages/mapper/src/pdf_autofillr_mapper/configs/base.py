"""
Base storage configuration interface.

Defines the contract that all storage implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseStorageConfig(ABC):
    """
    Abstract base class for storage configurations.
    
    All storage implementations (AWS, Azure, GCP, Local) must implement these methods.
    """
    
    def __init__(self, source_type: str):
        """
        Initialize storage config.
        
        Args:
            source_type: Type of storage (aws, azure, gcp, local)
        """
        self.source_type = source_type
        
        # Cache placeholders - populated by entry points after hash check
        # These are paths to cached files downloaded to /tmp
        self.cached_embedded_pdf: Optional[str] = None
        self.cached_mapping_json: Optional[str] = None
        self.cached_radio_groups: Optional[str] = None
        self.cached_headers_with_fields: Optional[str] = None
        self.cached_final_form_fields: Optional[str] = None
        
        # Cached extraction result - avoids re-extracting PDF if already done for hash check
        self.cached_extraction: Optional[Dict] = None
    
    @abstractmethod
    def parse_path(self, file_path: str) -> Dict[str, str]:
        """
        Parse a file path into its components.
        
        Args:
            file_path: Full file path (cloud URL or local path)
            
        Returns:
            Dict with parsed components (bucket/container, key/blob, etc.)
        """
        pass
    
    @abstractmethod
    def download_file(self, source_path: str, local_path: str) -> str:
        """
        Download file from source to local path.
        
        Args:
            source_path: Source file path (cloud URL or local)
            local_path: Destination local file path
            
        Returns:
            Local file path where file was saved
        """
        pass
    
    @abstractmethod
    def upload_file(self, local_path: str, destination_path: str) -> str:
        """
        Upload file from local path to destination.
        
        Args:
            local_path: Local file path to upload
            destination_path: Destination path (cloud URL or local)
            
        Returns:
            Destination path where file was uploaded
        """
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists at given path.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
        """
        Generate output file path based on input path and suffix.
        
        Args:
            input_path: Input file path
            suffix: Suffix to add (e.g., "_extracted", "_mapped")
            extension: Optional new extension (e.g., ".json", ".pdf")
            
        Returns:
            Generated output path
        """
        pass
    
    @abstractmethod
    def get_storage_config(self, file_path: str) -> Dict[str, Any]:
        """
        Get storage configuration dict for a file path.
        
        This is used by the processing modules (extractor, mapper, etc.)
        
        Args:
            file_path: File path
            
        Returns:
            Storage configuration dict
        """
        pass
    
    @abstractmethod
    def get_complete_file_config(
        self, 
        input_path: str, 
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate complete file configuration for processing pipeline.
        
        Args:
            input_path: Input file path
            user_id: Optional user ID for user-specific paths
            session_id: Optional session ID for session-specific paths
            
        Returns:
            Complete file configuration with all pipeline paths
        """
        pass
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source_type})"
    
    def __repr__(self) -> str:
        return self.__str__()
