# """
# Local filesystem storage configuration.
# """

# import os
# import shutil
# import logging
# from typing import Dict, Any, Optional
# from pathlib import Path
# from .base import BaseStorageConfig

# logger = logging.getLogger(__name__)


# class LocalStorageConfig(BaseStorageConfig):
#     """Local filesystem storage implementation."""
    
#     def __init__(self, base_dir: str = None):
#         """
#         Initialize local storage config.
        
#         Args:
#             base_dir: Optional base directory for output files (default: /tmp/pdf_processing)
#         """
#         super().__init__(source_type="local")
#         self.base_dir = base_dir or "/tmp/pdf_processing"
        
#         # Create base directory if it doesn't exist
#         Path(self.base_dir).mkdir(parents=True, exist_ok=True)
    
#     def parse_path(self, file_path: str) -> Dict[str, str]:
#         """
#         Parse local file path.
        
#         Returns:
#             {
#                 "type": "local",
#                 "path": "/full/path/to/file.ext",
#                 "directory": "/full/path/to",
#                 "filename": "file.ext"
#             }
#         """
#         abs_path = os.path.abspath(file_path)
#         directory = os.path.dirname(abs_path)
#         filename = os.path.basename(abs_path)
        
#         return {
#             "type": "local",
#             "path": abs_path,
#             "directory": directory,
#             "filename": filename
#         }
    
#     def download_file(self, source_path: str, local_path: str) -> str:
#         """
#         'Download' file (copy from source to destination for local).
        
#         For local files, this is essentially a copy operation.
#         """
#         source_abs = os.path.abspath(source_path)
#         dest_abs = os.path.abspath(local_path)
        
#         # Create destination directory if needed
#         os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        
#         # Copy file
#         shutil.copy2(source_abs, dest_abs)
#         logger.info(f"Copied {source_abs} to {dest_abs}")
#         return dest_abs
    
#     def upload_file(self, local_path: str, destination_path: str) -> str:
#         """
#         'Upload' file (copy from source to destination for local).
#         """
#         source_abs = os.path.abspath(local_path)
#         dest_abs = os.path.abspath(destination_path)
        
#         # Create destination directory if needed
#         os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        
#         # Copy file
#         shutil.copy2(source_abs, dest_abs)
#         logger.info(f"Copied {source_abs} to {dest_abs}")
#         return dest_abs
    
#     def file_exists(self, file_path: str) -> bool:
#         """Check if local file exists."""
#         return os.path.exists(file_path)
    
#     def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
#         """
#         Generate local output path.
        
#         Example:
#             input: /path/to/file.pdf
#             suffix: _extracted
#             extension: .json
#             output: /path/to/file_extracted.json
#         """
#         parsed = self.parse_path(input_path)
        
#         # Get base path without extension
#         path = parsed["path"]
#         if '.' in path:
#             base_path = path.rsplit('.', 1)[0]
#             original_ext = '.' + path.rsplit('.', 1)[1]
#         else:
#             base_path = path
#             original_ext = ''
        
#         # Use provided extension or keep original
#         new_ext = extension if extension else original_ext
        
#         # Build new path
#         return f"{base_path}{suffix}{new_ext}"
    
#     def get_storage_config(self, file_path: str) -> Dict[str, Any]:
#         """
#         Get storage config for processing modules.
        
#         Returns:
#             {
#                 "type": "local",
#                 "path": "/full/path/to/file",
#                 "directory": "/full/path/to",
#                 "filename": "file.ext"
#             }
#         """
#         return self.parse_path(file_path)
    
#     def get_complete_file_config(
#         self, 
#         input_path: str, 
#         user_id: Optional[int] = None,
#         session_id: Optional[int] = None
#     ) -> Dict[str, Any]:
#         """
#         Generate complete file configuration for local processing.
        
#         Returns config with all pipeline paths in the same directory as input,
#         or in output_base_path if set with proper user/pdf directory structure.
#         """
#         parsed = self.parse_path(input_path)
        
#         # Generate session suffix if applicable
#         session_suffix = ""
#         if user_id is not None and session_id is not None:
#             session_suffix = f"_user{user_id}_session{session_id}"
        
#         # Base paths
#         filename = parsed["filename"]
#         base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
#         # Check if output_base_path is set (for tests or custom directory structure)
#         if hasattr(self, 'output_base_path') and self.output_base_path and user_id is not None:
#             # Create structured output: output_base_path/users/{user_id}/pdfs/{pdf_doc_id}/
#             pdf_doc_id = getattr(self, 'pdf_doc_id', session_id or 1)
#             user_dir = os.path.join(self.output_base_path, "users", str(user_id))
#             pdf_dir = os.path.join(user_dir, "pdfs", str(pdf_doc_id))
            
#             # Create subdirectories for each stage
#             extraction_dir = os.path.join(pdf_dir, "extraction")
#             mapping_dir = os.path.join(pdf_dir, "mapping")
#             embedding_dir = os.path.join(pdf_dir, "embedding")
#             filling_dir = os.path.join(pdf_dir, "filling")
#             headers_dir = os.path.join(pdf_dir, "headers")  # For dual mapper
            
#             # Create directories
#             os.makedirs(extraction_dir, exist_ok=True)
#             os.makedirs(mapping_dir, exist_ok=True)
#             os.makedirs(embedding_dir, exist_ok=True)
#             os.makedirs(filling_dir, exist_ok=True)
#             os.makedirs(headers_dir, exist_ok=True)
            
#             # Set output directories for structured layout
#             extraction_output_dir = extraction_dir
#             mapping_output_dir = mapping_dir
#             embedding_output_dir = embedding_dir
#             filling_output_dir = filling_dir
#             headers_output_dir = headers_dir
#         else:
#             # Default: all in same directory as input
#             directory = parsed["directory"]
#             extraction_output_dir = directory
#             mapping_output_dir = directory
#             embedding_output_dir = directory
#             filling_output_dir = directory
#             headers_output_dir = directory
        
#         # Generate all pipeline paths
#         config = {
#             "source_type": "local",
#             "input_path": parsed["path"],
#             "input_filename": filename,
#             "session_suffix": session_suffix,
            
#             # Extraction stage outputs
#             "extraction": {
#                 "extracted_path": os.path.join(extraction_output_dir, f"{base_name}{session_suffix}_extracted.json"),
#                 "radio_groups_path": os.path.join(extraction_output_dir, f"{base_name}{session_suffix}_radio_groups.json")
#             },
            
#             # Mapping stage outputs
#             "mapping": {
#                 "mapping_path": os.path.join(mapping_output_dir, f"{base_name}{session_suffix}_mapped_fields.json"),
#                 "radio_groups_path": os.path.join(mapping_output_dir, f"{base_name}{session_suffix}_radio_groups.json")
#             },
            
#             # Embedding stage output
#             "embedding": {
#                 "embedded_pdf_path": os.path.join(embedding_output_dir, f"{base_name}{session_suffix}_embedded.pdf")
#             },
            
#             # Filling stage output
#             "filling": {
#                 "filled_pdf_path": os.path.join(filling_output_dir, f"{base_name}{session_suffix}_filled.pdf")
#             },
            
#             # Headers stage (for dual mapper / RAG)
#             "headers": {
#                 "headers_with_fields_path": os.path.join(headers_output_dir, f"{base_name}{session_suffix}_headers_with_fields.json"),
#                 "final_form_fields_path": os.path.join(headers_output_dir, f"{base_name}{session_suffix}_final_form_fields.json")
#             }
#         }
        
#         return config























"""
Local filesystem storage configuration.
"""

import os
import shutil
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from .base import BaseStorageConfig

logger = logging.getLogger(__name__)


class LocalStorageConfig(BaseStorageConfig):
    """Local filesystem storage implementation."""
    
    def __init__(self, base_dir: str = None):
        """
        Initialize local storage config.
        
        Args:
            base_dir: Optional base directory for output files (default: /tmp/pdf_processing)
        """
        super().__init__(source_type="local")
        self.base_dir = base_dir or "/tmp/pdf_processing"

        # RAG integration flags (read from env — same source as MapperConfig.from_env)
        self.rag_enabled = os.getenv('RAG_ENABLED', 'false').lower() == 'true'
        self.rag_mode    = os.getenv('RAG_MODE', 'inprocess')
        self.rag_api_url = os.getenv('RAG_API_URL', '')
        self.rag_api_key = os.getenv('RAG_API_KEY', '')

        # RAG local file paths (set by operations after calling create_rag_api_files)
        self.local_header_file       = None
        self.local_section_file      = None
        self.local_rag_predictions   = None
        self.local_llm_predictions   = None
        self.local_final_predictions = None
        
        # Create base directory if it doesn't exist
        Path(self.base_dir).mkdir(parents=True, exist_ok=True)
    
    def parse_path(self, file_path: str) -> Dict[str, str]:
        """
        Parse local file path.
        
        Returns:
            {
                "type": "local",
                "path": "/full/path/to/file.ext",
                "directory": "/full/path/to",
                "filename": "file.ext"
            }
        """
        abs_path  = os.path.abspath(file_path)
        directory = os.path.dirname(abs_path)
        filename  = os.path.basename(abs_path)
        
        return {
            "type":      "local",
            "path":      abs_path,
            "directory": directory,
            "filename":  filename
        }
    
    def download_file(self, source_path: str, local_path: str) -> str:
        """
        'Download' file (copy from source to destination for local).
        
        For local files, this is essentially a copy operation.
        """
        source_abs = os.path.abspath(source_path)
        dest_abs   = os.path.abspath(local_path)
        
        # Create destination directory if needed
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        
        # Copy file
        shutil.copy2(source_abs, dest_abs)
        logger.info(f"Copied {source_abs} to {dest_abs}")
        return dest_abs
    
    def upload_file(self, local_path: str, destination_path: str) -> str:
        """
        'Upload' file (copy from source to destination for local).
        """
        source_abs = os.path.abspath(local_path)
        dest_abs   = os.path.abspath(destination_path)
        
        # Create destination directory if needed
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        
        # Copy file
        shutil.copy2(source_abs, dest_abs)
        logger.info(f"Copied {source_abs} to {dest_abs}")
        return dest_abs
    
    def file_exists(self, file_path: str) -> bool:
        """Check if local file exists."""
        return os.path.exists(file_path)
    
    def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
        """
        Generate local output path.
        
        Example:
            input: /path/to/file.pdf
            suffix: _extracted
            extension: .json
            output: /path/to/file_extracted.json
        """
        parsed = self.parse_path(input_path)
        
        path = parsed["path"]
        if '.' in path:
            base_path    = path.rsplit('.', 1)[0]
            original_ext = '.' + path.rsplit('.', 1)[1]
        else:
            base_path    = path
            original_ext = ''
        
        new_ext = extension if extension else original_ext
        return f"{base_path}{suffix}{new_ext}"
    
    def get_storage_config(self, file_path: str) -> Dict[str, Any]:
        """
        Get storage config for processing modules.
        
        Returns:
            {
                "type": "local",
                "path": "/full/path/to/file",
                "directory": "/full/path/to",
                "filename": "file.ext"
            }
        """
        return self.parse_path(file_path)
    
    def get_complete_file_config(
        self, 
        input_path: str, 
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate complete file configuration for local processing.
        
        Returns config with all pipeline paths in the same directory as input,
        or in output_base_path if set with proper user/pdf directory structure.
        """
        parsed = self.parse_path(input_path)
        
        # Generate session suffix if applicable
        session_suffix = ""
        if user_id is not None and session_id is not None:
            session_suffix = f"_user{user_id}_session{session_id}"
        
        # Base paths
        filename  = parsed["filename"]
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # Check if output_base_path is set (for tests or custom directory structure)
        if hasattr(self, 'output_base_path') and self.output_base_path and user_id is not None:
            # Create structured output: output_base_path/users/{user_id}/pdfs/{pdf_doc_id}/
            pdf_doc_id = getattr(self, 'pdf_doc_id', session_id or 1)
            user_dir   = os.path.join(self.output_base_path, "users", str(user_id))
            pdf_dir    = os.path.join(user_dir, "pdfs", str(pdf_doc_id))
            
            # Create subdirectories for each stage
            extraction_dir = os.path.join(pdf_dir, "extraction")
            mapping_dir    = os.path.join(pdf_dir, "mapping")
            embedding_dir  = os.path.join(pdf_dir, "embedding")
            filling_dir    = os.path.join(pdf_dir, "filling")
            headers_dir    = os.path.join(pdf_dir, "headers")   # For dual mapper / RAG
            
            for d in [extraction_dir, mapping_dir, embedding_dir, filling_dir, headers_dir]:
                os.makedirs(d, exist_ok=True)
            
            extraction_output_dir = extraction_dir
            mapping_output_dir    = mapping_dir
            embedding_output_dir  = embedding_dir
            filling_output_dir    = filling_dir
            headers_output_dir    = headers_dir
        else:
            # Default: all in same directory as input
            directory             = parsed["directory"]
            extraction_output_dir = directory
            mapping_output_dir    = directory
            embedding_output_dir  = directory
            filling_output_dir    = directory
            headers_output_dir    = directory
        
        # Generate all pipeline paths
        config = {
            "source_type":    "local",
            "input_path":     parsed["path"],
            "input_filename": filename,
            "session_suffix": session_suffix,
            
            # Extraction stage outputs
            "extraction": {
                "extracted_path":    os.path.join(extraction_output_dir, f"{base_name}{session_suffix}_extracted.json"),
                "radio_groups_path": os.path.join(extraction_output_dir, f"{base_name}{session_suffix}_radio_groups.json")
            },
            
            # Mapping stage outputs
            "mapping": {
                "mapping_path":      os.path.join(mapping_output_dir, f"{base_name}{session_suffix}_mapped_fields.json"),
                "radio_groups_path": os.path.join(mapping_output_dir, f"{base_name}{session_suffix}_radio_groups.json")
            },
            
            # Embedding stage output
            "embedding": {
                "embedded_pdf_path": os.path.join(embedding_output_dir, f"{base_name}{session_suffix}_embedded.pdf")
            },
            
            # Filling stage output
            "filling": {
                "filled_pdf_path": os.path.join(filling_output_dir, f"{base_name}{session_suffix}_filled.pdf")
            },
            
            # Headers stage (for dual mapper / RAG)
            "headers": {
                "headers_with_fields_path": os.path.join(headers_output_dir, f"{base_name}{session_suffix}_headers_with_fields.json"),
                "final_form_fields_path":   os.path.join(headers_output_dir, f"{base_name}{session_suffix}_final_form_fields.json")
            }
        }
        
        return config
