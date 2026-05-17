"""
Azure Blob Storage configuration.
"""

import os
import logging
from typing import Dict, Any, Optional
from .base import BaseStorageConfig

logger = logging.getLogger(__name__)


class AzureStorageConfig(BaseStorageConfig):
    """Azure Blob Storage implementation."""
    
    def __init__(self):
        super().__init__(source_type="azure")
        self.blob_client = None
        logger.warning("Azure storage not fully implemented yet")
    
    def parse_path(self, file_path: str) -> Dict[str, str]:
        """
        Parse Azure blob path: https://{account}.blob.core.windows.net/{container}/{blob}
        or: azure://{container}/{blob}
        
        Returns:
            {
                "type": "azure",
                "container": "container-name",
                "blob": "path/to/blob.ext",
                "path": "azure://container/blob",
                "filename": "blob.ext"
            }
        """
        if file_path.startswith("https://") and "blob.core.windows.net" in file_path:
            # Parse full Azure URL
            # https://account.blob.core.windows.net/container/path/to/blob
            parts = file_path.split("blob.core.windows.net/", 1)
            if len(parts) == 2:
                container_and_blob = parts[1].split('/', 1)
                container = container_and_blob[0]
                blob = container_and_blob[1] if len(container_and_blob) > 1 else ""
            else:
                raise ValueError(f"Invalid Azure blob URL: {file_path}")
        elif file_path.startswith("azure://"):
            # Parse simplified azure:// format
            path_without_prefix = file_path[8:]
            parts = path_without_prefix.split('/', 1)
            container = parts[0]
            blob = parts[1] if len(parts) > 1 else ""
        else:
            raise ValueError(f"Invalid Azure path: {file_path}")
        
        filename = blob.split('/')[-1] if blob else ""
        
        return {
            "type": "azure",
            "container": container,
            "blob": blob,
            "path": f"azure://{container}/{blob}",
            "filename": filename
        }
    
    def download_file(self, source_path: str, local_path: str) -> str:
        """Download file from Azure Blob to local path."""
        raise NotImplementedError("Azure Blob download not implemented yet")
    
    def upload_file(self, local_path: str, destination_path: str) -> str:
        """Upload file from local to Azure Blob."""
        raise NotImplementedError("Azure Blob upload not implemented yet")
    
    def file_exists(self, file_path: str) -> bool:
        """Check if Azure blob exists."""
        raise NotImplementedError("Azure Blob existence check not implemented yet")
    
    def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
        """Generate Azure blob output path."""
        parsed = self.parse_path(input_path)
        
        # Get base path without extension
        blob = parsed["blob"]
        if '.' in blob:
            base_blob = blob.rsplit('.', 1)[0]
            original_ext = '.' + blob.rsplit('.', 1)[1]
        else:
            base_blob = blob
            original_ext = ''
        
        # Use provided extension or keep original
        new_ext = extension if extension else original_ext
        
        # Build new path
        new_blob = f"{base_blob}{suffix}{new_ext}"
        return f"azure://{parsed['container']}/{new_blob}"
    
    def get_storage_config(self, file_path: str) -> Dict[str, Any]:
        """Get storage config for processing modules."""
        return self.parse_path(file_path)
    
    def get_complete_file_config(
        self, 
        input_path: str, 
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate complete file configuration for Azure processing."""
        parsed = self.parse_path(input_path)
        
        # Generate session suffix
        session_suffix = ""
        if user_id is not None and session_id is not None:
            session_suffix = f"_user{user_id}_session{session_id}"
        
        # Base paths
        base_blob = parsed["blob"].rsplit('.', 1)[0] if '.' in parsed["blob"] else parsed["blob"]
        container = parsed["container"]
        
        config = {
            "source_type": "azure",
            "input_path": input_path,
            "input_filename": parsed["filename"],
            "session_suffix": session_suffix,
            
            "extraction": {
                "extracted_path": f"azure://{container}/{base_blob}{session_suffix}_extracted.json",
                "radio_groups_path": f"azure://{container}/{base_blob}{session_suffix}_radio_groups.json"
            },
            
            "mapping": {
                "mapping_path": f"azure://{container}/{base_blob}{session_suffix}_mapped_fields.json",
                "radio_groups_path": f"azure://{container}/{base_blob}{session_suffix}_radio_groups.json"
            },
            
            "embedding": {
                "embedded_pdf_path": f"azure://{container}/{base_blob}{session_suffix}_embedded.pdf"
            },
            
            "filling": {
                "filled_pdf_path": f"azure://{container}/{base_blob}{session_suffix}_filled.pdf"
            }
        }
        
        return config
