"""
Google Cloud Storage (GCS) configuration.
"""

import os
import logging
from typing import Dict, Any, Optional
from .base import BaseStorageConfig

logger = logging.getLogger(__name__)


class GCPStorageConfig(BaseStorageConfig):
    """Google Cloud Storage implementation."""
    
    def __init__(self):
        super().__init__(source_type="gcp")
        self.gcs_client = None
        logger.warning("GCP storage not fully implemented yet")
    
    def parse_path(self, file_path: str) -> Dict[str, str]:
        """
        Parse GCS path: gs://bucket/path/to/object.ext
        
        Returns:
            {
                "type": "gcs",
                "bucket": "bucket-name",
                "object": "path/to/object.ext",
                "path": "gs://bucket/object",
                "filename": "object.ext"
            }
        """
        if not file_path.startswith("gs://"):
            raise ValueError(f"Invalid GCS path: {file_path}")
        
        # Remove gs:// prefix
        path_without_prefix = file_path[5:]
        parts = path_without_prefix.split('/', 1)
        
        bucket = parts[0]
        obj = parts[1] if len(parts) > 1 else ""
        filename = obj.split('/')[-1] if obj else ""
        
        return {
            "type": "gcs",
            "bucket": bucket,
            "object": obj,
            "path": file_path,
            "filename": filename
        }
    
    def download_file(self, source_path: str, local_path: str) -> str:
        """Download file from GCS to local path."""
        raise NotImplementedError("GCS download not implemented yet")
    
    def upload_file(self, local_path: str, destination_path: str) -> str:
        """Upload file from local to GCS."""
        raise NotImplementedError("GCS upload not implemented yet")
    
    def file_exists(self, file_path: str) -> bool:
        """Check if GCS object exists."""
        raise NotImplementedError("GCS existence check not implemented yet")
    
    def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
        """Generate GCS output path."""
        parsed = self.parse_path(input_path)
        
        # Get base path without extension
        obj = parsed["object"]
        if '.' in obj:
            base_obj = obj.rsplit('.', 1)[0]
            original_ext = '.' + obj.rsplit('.', 1)[1]
        else:
            base_obj = obj
            original_ext = ''
        
        # Use provided extension or keep original
        new_ext = extension if extension else original_ext
        
        # Build new path
        new_obj = f"{base_obj}{suffix}{new_ext}"
        return f"gs://{parsed['bucket']}/{new_obj}"
    
    def get_storage_config(self, file_path: str) -> Dict[str, Any]:
        """Get storage config for processing modules."""
        return self.parse_path(file_path)
    
    def get_complete_file_config(
        self, 
        input_path: str, 
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate complete file configuration for GCS processing."""
        parsed = self.parse_path(input_path)
        
        # Generate session suffix
        session_suffix = ""
        if user_id is not None and session_id is not None:
            session_suffix = f"_user{user_id}_session{session_id}"
        
        # Base paths
        base_obj = parsed["object"].rsplit('.', 1)[0] if '.' in parsed["object"] else parsed["object"]
        bucket = parsed["bucket"]
        
        config = {
            "source_type": "gcp",
            "input_path": input_path,
            "input_filename": parsed["filename"],
            "session_suffix": session_suffix,
            
            "extraction": {
                "extracted_path": f"gs://{bucket}/{base_obj}{session_suffix}_extracted.json",
                "radio_groups_path": f"gs://{bucket}/{base_obj}{session_suffix}_radio_groups.json"
            },
            
            "mapping": {
                "mapping_path": f"gs://{bucket}/{base_obj}{session_suffix}_mapped_fields.json",
                "radio_groups_path": f"gs://{bucket}/{base_obj}{session_suffix}_radio_groups.json"
            },
            
            "embedding": {
                "embedded_pdf_path": f"gs://{bucket}/{base_obj}{session_suffix}_embedded.pdf"
            },
            
            "filling": {
                "filled_pdf_path": f"gs://{bucket}/{base_obj}{session_suffix}_filled.pdf"
            }
        }
        
        return config
