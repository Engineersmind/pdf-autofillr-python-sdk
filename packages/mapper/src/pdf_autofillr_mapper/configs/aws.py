# """
# AWS S3 storage configuration.
# """

# import os
# import logging
# from typing import Dict, Any, Optional
# from .base import BaseStorageConfig

# logger = logging.getLogger(__name__)


# class AWSStorageConfig(BaseStorageConfig):
#     """AWS S3 storage implementation."""
    
#     def __init__(self):
#         super().__init__(source_type="aws")
#         self.s3_client = None
        
#         # AWS-specific constants (loaded from environment)
#         self.global_input_json_s3_uri = os.getenv(
#             'GLOBAL_INPUT_JSON_S3_URI',
#             's3://your-bucket/global_input_keys.json'
#         )
#         self.rag_bucket_name = os.getenv('RAG_BUCKET_NAME', 'rag-bucket-pdf-filler')
#         self.rag_api_url = os.getenv('RAG_API_URL', '')
#         self.rag_api_key = os.getenv('RAG_API_KEY', '')
        
#         # S3 source paths (original remote paths)
#         self.s3_input_pdf = None
#         self.s3_input_json = None
#         self.s3_global_json = None
#         self.s3_extracted_json = None
#         self.s3_mapped_json = None
#         self.s3_radio_json = None
#         self.s3_embedded_pdf = None
#         self.s3_filled_pdf = None
        
#         # Dual mapper (RAG) S3 paths
#         self.s3_headers_with_fields = None
#         self.s3_final_form_fields = None
#         self.s3_header_file = None          # RAG API input
#         self.s3_section_file = None         # RAG API input
#         self.s3_llm_predictions = None
#         self.s3_rag_predictions = None
#         self.s3_final_predictions = None    # Combined predictions
#         self.s3_java_mapping = None         # Java-compatible mapping
        
#         # Local file paths (operations work with these)
#         # These are set by the AWS handler after downloading files
#         self.local_input_pdf = None
#         self.local_input_json = None
#         self.local_global_json = None
#         self.local_extracted_json = None
#         self.local_mapped_json = None
#         self.local_radio_json = None
#         self.local_embedded_pdf = None
#         self.local_filled_pdf = None
        
#         # Dual mapper (RAG) local paths
#         self.local_headers_with_fields = None
#         self.local_final_form_fields = None
#         self.local_header_file = None
#         self.local_section_file = None
#         self.local_llm_predictions = None
#         self.local_rag_predictions = None
#         self.local_final_predictions = None
#         self.local_java_mapping = None
    
#     def _get_s3_client(self):
#         """Lazy load S3 client."""
#         if self.s3_client is None:
#             from pdf_autofillr_mapper.clients.s3_client import S3Client
#             self.s3_client = S3Client()
#         return self.s3_client
    
#     def parse_path(self, file_path: str) -> Dict[str, str]:
#         """
#         Parse S3 path: s3://bucket/key/to/file.ext
        
#         Returns:
#             {
#                 "type": "s3",
#                 "bucket": "bucket-name",
#                 "key": "key/to/file.ext",
#                 "path": "s3://bucket/key/to/file.ext",
#                 "filename": "file.ext"
#             }
#         """
#         if not file_path.startswith("s3://"):
#             raise ValueError(f"Invalid S3 path: {file_path}")
        
#         # Remove s3:// prefix
#         path_without_prefix = file_path[5:]
#         parts = path_without_prefix.split('/', 1)
        
#         bucket = parts[0]
#         key = parts[1] if len(parts) > 1 else ""
#         filename = key.split('/')[-1] if key else ""
        
#         return {
#             "type": "s3",
#             "bucket": bucket,
#             "key": key,
#             "path": file_path,
#             "filename": filename
#         }
    
#     def download_file(self, source_path: str, local_path: str) -> str:
#         """Download file from S3 to local path."""
#         s3_client = self._get_s3_client()
#         s3_client.download_file_from_s3(source_path, local_path)
#         logger.info(f"Downloaded {source_path} to {local_path}")
#         return local_path
    
#     def upload_file(self, local_path: str, destination_path: str) -> str:
#         """Upload file from local to S3."""
#         s3_client = self._get_s3_client()
#         s3_client.upload_file_to_s3(local_path, destination_path)
#         logger.info(f"Uploaded {local_path} to {destination_path}")
#         return destination_path
    
#     def file_exists(self, file_path: str) -> bool:
#         """Check if S3 object exists."""
#         s3_client = self._get_s3_client()
#         return s3_client.object_exists(file_path)
    
#     def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
#         """
#         Generate S3 output path.
        
#         Example:
#             input: s3://bucket/path/file.pdf
#             suffix: _extracted
#             extension: .json
#             output: s3://bucket/path/file_extracted.json
#         """
#         parsed = self.parse_path(input_path)
        
#         # Get base path without extension
#         key = parsed["key"]
#         if '.' in key:
#             base_key = key.rsplit('.', 1)[0]
#             original_ext = '.' + key.rsplit('.', 1)[1]
#         else:
#             base_key = key
#             original_ext = ''
        
#         # Use provided extension or keep original
#         new_ext = extension if extension else original_ext
        
#         # Build new path
#         new_key = f"{base_key}{suffix}{new_ext}"
#         return f"s3://{parsed['bucket']}/{new_key}"
    
#     def get_storage_config(self, file_path: str) -> Dict[str, Any]:
#         """
#         Get storage config for processing modules.
        
#         Returns:
#             {
#                 "type": "s3",
#                 "path": "s3://bucket/key",
#                 "bucket": "bucket-name",
#                 "key": "key/to/file"
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
#         Generate complete file configuration for S3 processing.
        
#         Returns config with all pipeline paths:
#         - extraction paths (extracted JSON, radio groups)
#         - mapping paths
#         - embedding paths
#         - filling paths
#         """
#         parsed = self.parse_path(input_path)
        
#         # Generate session suffix if applicable
#         session_suffix = ""
#         if user_id is not None and session_id is not None:
#             session_suffix = f"_user{user_id}_session{session_id}"
        
#         # Base paths
#         base_key = parsed["key"].rsplit('.', 1)[0] if '.' in parsed["key"] else parsed["key"]
#         bucket = parsed["bucket"]
        
#         # Generate all pipeline paths
#         config = {
#             "source_type": "aws",
#             "input_path": input_path,
#             "input_filename": parsed["filename"],
#             "session_suffix": session_suffix,
            
#             # Extraction stage outputs
#             "extraction": {
#                 "extracted_path": f"s3://{bucket}/{base_key}{session_suffix}_extracted.json",
#                 "radio_groups_path": f"s3://{bucket}/{base_key}{session_suffix}_radio_groups.json"
#             },
            
#             # Mapping stage outputs
#             "mapping": {
#                 "mapping_path": f"s3://{bucket}/{base_key}{session_suffix}_mapped_fields.json",
#                 "radio_groups_path": f"s3://{bucket}/{base_key}{session_suffix}_radio_groups.json",
#                 "semantic_mapping_path": f"s3://{bucket}/{base_key}{session_suffix}_semantic_mapping.json"
#             },
            
#             # Dual mapper (RAG) outputs
#             "dual_mapper": {
#                 "headers_with_fields_path": f"s3://{bucket}/{base_key}{session_suffix}_headers_with_fields.json",
#                 "final_form_fields_path": f"s3://{bucket}/{base_key}{session_suffix}_final_form_fields.json",
#                 "header_file_path": f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/input_file/header_file.json" if user_id and session_id else None,
#                 "section_file_path": f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/input_file/section_file.json" if user_id and session_id else None,
#                 "llm_predictions_path": f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/predictions/llm_predictions.json" if user_id and session_id else None,
#                 "rag_predictions_path": f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/predictions/rag_predictions.json" if user_id and session_id else None,
#                 "final_predictions_path": f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/predictions/final_predictions.json" if user_id and session_id else None,
#                 "java_mapping_path": f"s3://{bucket}/{base_key}{session_suffix}_final_mapping_json_combined_java.json"
#             },
            
#             # Embedding stage output
#             "embedding": {
#                 "embedded_pdf_path": f"s3://{bucket}/{base_key}{session_suffix}_embedded.pdf"
#             },
            
#             # Filling stage output
#             "filling": {
#                 "filled_pdf_path": f"s3://{bucket}/{base_key}{session_suffix}_filled.pdf"
#             }
#         }
        
#         return config










"""
AWS S3 storage configuration.
"""

import os
import logging
from typing import Dict, Any, Optional
from .base import BaseStorageConfig

logger = logging.getLogger(__name__)


class AWSStorageConfig(BaseStorageConfig):
    """AWS S3 storage implementation."""
    
    def __init__(self):
        super().__init__(source_type="aws")
        self.s3_client = None
        
        # AWS-specific constants (loaded from environment)
        self.global_input_json_s3_uri = os.getenv(
            'GLOBAL_INPUT_JSON_S3_URI',
            's3://your-bucket/global_input_keys.json'
        )
        self.rag_bucket_name = os.getenv('RAG_BUCKET_NAME', 'rag-bucket-pdf-filler')
        self.rag_api_url     = os.getenv('RAG_API_URL', '')
        self.rag_api_key     = os.getenv('RAG_API_KEY', '')

        # RAG integration flags (read from env — same source as MapperConfig.from_env)
        self.rag_enabled = os.getenv('RAG_ENABLED', 'false').lower() == 'true'
        self.rag_mode    = os.getenv('RAG_MODE', 'inprocess')
        
        # S3 source paths (original remote paths)
        self.s3_input_pdf       = None
        self.s3_input_json      = None
        self.s3_global_json     = None
        self.s3_extracted_json  = None
        self.s3_mapped_json     = None
        self.s3_radio_json      = None
        self.s3_embedded_pdf    = None
        self.s3_filled_pdf      = None
        
        # Dual mapper (RAG) S3 paths
        self.s3_headers_with_fields = None
        self.s3_final_form_fields   = None
        self.s3_header_file         = None   # RAG API input
        self.s3_section_file        = None   # RAG API input
        self.s3_llm_predictions     = None
        self.s3_rag_predictions     = None
        self.s3_final_predictions   = None   # Combined predictions
        self.s3_java_mapping        = None   # Java-compatible mapping
        
        # Local file paths (operations work with these)
        # These are set by the AWS handler after downloading files
        self.local_input_pdf       = None
        self.local_input_json      = None
        self.local_global_json     = None
        self.local_extracted_json  = None
        self.local_mapped_json     = None
        self.local_radio_json      = None
        self.local_embedded_pdf    = None
        self.local_filled_pdf      = None
        
        # Dual mapper (RAG) local paths
        self.local_headers_with_fields = None
        self.local_final_form_fields   = None
        self.local_header_file         = None
        self.local_section_file        = None
        self.local_llm_predictions     = None
        self.local_rag_predictions     = None
        self.local_final_predictions   = None
        self.local_java_mapping        = None
    
    def _get_s3_client(self):
        """Lazy load S3 client."""
        if self.s3_client is None:
            from pdf_autofillr_mapper.clients.s3_client import S3Client
            self.s3_client = S3Client()
        return self.s3_client
    
    def parse_path(self, file_path: str) -> Dict[str, str]:
        """
        Parse S3 path: s3://bucket/key/to/file.ext
        
        Returns:
            {
                "type": "s3",
                "bucket": "bucket-name",
                "key": "key/to/file.ext",
                "path": "s3://bucket/key/to/file.ext",
                "filename": "file.ext"
            }
        """
        if not file_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {file_path}")
        
        # Remove s3:// prefix
        path_without_prefix = file_path[5:]
        parts = path_without_prefix.split('/', 1)
        
        bucket   = parts[0]
        key      = parts[1] if len(parts) > 1 else ""
        filename = key.split('/')[-1] if key else ""
        
        return {
            "type":     "s3",
            "bucket":   bucket,
            "key":      key,
            "path":     file_path,
            "filename": filename
        }
    
    def download_file(self, source_path: str, local_path: str) -> str:
        """Download file from S3 to local path."""
        s3_client = self._get_s3_client()
        s3_client.download_file_from_s3(source_path, local_path)
        logger.info(f"Downloaded {source_path} to {local_path}")
        return local_path
    
    def upload_file(self, local_path: str, destination_path: str) -> str:
        """Upload file from local to S3."""
        s3_client = self._get_s3_client()
        s3_client.upload_file_to_s3(local_path, destination_path)
        logger.info(f"Uploaded {local_path} to {destination_path}")
        return destination_path
    
    def file_exists(self, file_path: str) -> bool:
        """Check if S3 object exists."""
        s3_client = self._get_s3_client()
        return s3_client.object_exists(file_path)
    
    def generate_output_path(self, input_path: str, suffix: str, extension: str = None) -> str:
        """
        Generate S3 output path.
        
        Example:
            input: s3://bucket/path/file.pdf
            suffix: _extracted
            extension: .json
            output: s3://bucket/path/file_extracted.json
        """
        parsed = self.parse_path(input_path)
        
        key = parsed["key"]
        if '.' in key:
            base_key     = key.rsplit('.', 1)[0]
            original_ext = '.' + key.rsplit('.', 1)[1]
        else:
            base_key     = key
            original_ext = ''
        
        new_ext  = extension if extension else original_ext
        new_key  = f"{base_key}{suffix}{new_ext}"
        return f"s3://{parsed['bucket']}/{new_key}"
    
    def get_storage_config(self, file_path: str) -> Dict[str, Any]:
        """Get storage config for processing modules."""
        return self.parse_path(file_path)
    
    def get_complete_file_config(
        self, 
        input_path: str, 
        user_id: Optional[int] = None,
        session_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate complete file configuration for S3 processing.
        
        Returns config with all pipeline paths:
        - extraction paths (extracted JSON, radio groups)
        - mapping paths
        - embedding paths
        - filling paths
        """
        parsed = self.parse_path(input_path)
        
        # Generate session suffix if applicable
        session_suffix = ""
        if user_id is not None and session_id is not None:
            session_suffix = f"_user{user_id}_session{session_id}"
        
        # Base paths
        base_key = parsed["key"].rsplit('.', 1)[0] if '.' in parsed["key"] else parsed["key"]
        bucket   = parsed["bucket"]
        
        # Generate all pipeline paths
        config = {
            "source_type":      "aws",
            "input_path":       input_path,
            "input_filename":   parsed["filename"],
            "session_suffix":   session_suffix,
            
            # Extraction stage outputs
            "extraction": {
                "extracted_path":   f"s3://{bucket}/{base_key}{session_suffix}_extracted.json",
                "radio_groups_path": f"s3://{bucket}/{base_key}{session_suffix}_radio_groups.json"
            },
            
            # Mapping stage outputs
            "mapping": {
                "mapping_path":          f"s3://{bucket}/{base_key}{session_suffix}_mapped_fields.json",
                "radio_groups_path":     f"s3://{bucket}/{base_key}{session_suffix}_radio_groups.json",
                "semantic_mapping_path": f"s3://{bucket}/{base_key}{session_suffix}_semantic_mapping.json"
            },
            
            # Dual mapper (RAG) outputs
            "dual_mapper": {
                "headers_with_fields_path": f"s3://{bucket}/{base_key}{session_suffix}_headers_with_fields.json",
                "final_form_fields_path":   f"s3://{bucket}/{base_key}{session_suffix}_final_form_fields.json",
                "header_file_path":         f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/input_file/header_file.json" if user_id and session_id else None,
                "section_file_path":        f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/input_file/section_file.json" if user_id and session_id else None,
                "llm_predictions_path":     f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/predictions/llm_predictions.json" if user_id and session_id else None,
                "rag_predictions_path":     f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/predictions/rag_predictions.json" if user_id and session_id else None,
                "final_predictions_path":   f"s3://{self.rag_bucket_name}/predictions/{user_id}/{session_id}/{base_key.split('/')[-1]}/predictions/final_predictions.json" if user_id and session_id else None,
                "java_mapping_path":        f"s3://{bucket}/{base_key}{session_suffix}_final_mapping_json_combined_java.json"
            },
            
            # Embedding stage output
            "embedding": {
                "embedded_pdf_path": f"s3://{bucket}/{base_key}{session_suffix}_embedded.pdf"
            },
            
            # Filling stage output
            "filling": {
                "filled_pdf_path": f"s3://{bucket}/{base_key}{session_suffix}_filled.pdf"
            }
        }
        
        return config
