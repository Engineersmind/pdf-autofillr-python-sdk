"""
Config.ini file loader and path builder.

This module loads configuration from config.ini and builds file paths
based on patterns defined for each storage source.
"""

import os
import configparser
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FileConfig:
    """Loads and manages config.ini configuration."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to config.ini file. If None, looks in module root.
        """
        if config_path is None:
            # Look for config.ini in module root
            module_root = Path(__file__).parent.parent.parent
            config_path = module_root / "config.ini"
        
        self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        self.config.read(self.config_path)
        logger.info(f"Loaded config from: {self.config_path}")
    
    def get(self, section: str, key: str, fallback=None):
        """Get configuration value."""
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise
    
    def get_source_type(self) -> str:
        """Get the source type (aws, azure, gcp, local)."""
        return self.get('general', 'source_type', fallback='local')
    
    def build_file_path(
        self,
        pattern_key: str,
        user_id: int,
        session_id: str,
        pdf_doc_id: int,
        base_path: str = None
    ) -> str:
        """
        Build file path from pattern.
        
        Args:
            pattern_key: Key in [file_naming] section (e.g., 'input_pdf_pattern')
            user_id: User ID
            session_id: Session ID
            pdf_doc_id: PDF document ID
            base_path: Optional base path to prepend
        
        Returns:
            Full file path with variables substituted
        
        Example:
            pattern: "{user_id}_{session_id}_{pdf_doc_id}.pdf"
            result: "553_086d6670-81e5-47f4-aecb-e4f7c3ba2a83_990.pdf"
        """
        try:
            pattern = self.get('file_naming', pattern_key)
        except configparser.NoOptionError:
            raise ValueError(f"File naming pattern '{pattern_key}' not found in config.ini")
        
        # Substitute variables
        filename = pattern.format(
            user_id=user_id,
            session_id=session_id,
            pdf_doc_id=pdf_doc_id
        )
        
        if base_path:
            return os.path.join(base_path, filename)
        return filename
    
    def get_all_processing_paths(
        self,
        user_id: int,
        session_id: str,
        pdf_doc_id: int
    ) -> Dict[str, str]:
        """
        Build all processing paths for a given operation.
        
        Returns dictionary with all file paths needed for processing.
        Paths are in Docker /tmp/processing/ directory.
        
        Args:
            user_id: User ID
            session_id: Session ID  
            pdf_doc_id: PDF document ID
        
        Returns:
            Dictionary with keys:
                - input_pdf, input_json
                - extracted_json, mapped_json, radio_groups_json
                - embedded_pdf, filled_pdf
                - headers_with_fields, final_form_fields
                - llm_predictions, rag_predictions, etc.
        """
        source_type = self.get_source_type()
        processing_dir = self.get(source_type, 'processing_dir', fallback='/tmp/processing')
        
        # Build all paths
        paths = {}
        
        # Define all pattern keys we need
        pattern_keys = [
            'processing_input_pdf',
            'processing_input_json',
            'extracted_json',
            'mapped_json',
            'radio_groups_json',
            'embedded_pdf',
            'filled_pdf',
            'headers_with_fields',
            'final_form_fields',
            'header_file',
            'section_file',
            'llm_predictions',
            'rag_predictions',
            'final_predictions',
            'java_mapping'
        ]
        
        for key in pattern_keys:
            try:
                paths[key] = self.build_file_path(
                    key,
                    user_id,
                    session_id,
                    pdf_doc_id,
                    base_path=processing_dir
                )
            except ValueError:
                # Pattern not found, skip
                logger.debug(f"Pattern '{key}' not found in config, skipping")
                continue
        
        return paths
    
    def get_source_input_path(
        self,
        file_type: str,
        user_id: int,
        session_id: str,
        pdf_doc_id: int
    ) -> str:
        """
        Get input file path in source storage.
        
        Args:
            file_type: 'pdf', 'json', or 'registry'
            user_id: User ID
            session_id: Session ID
            pdf_doc_id: PDF document ID
        
        Returns:
            Full path in source storage (e.g., /app/data/input/xxx.pdf)
        """
        source_type = self.get_source_type()
        
        if file_type == 'registry':
            # Registry is at fixed location
            return self.get(source_type, 'local_global_json', 
                          fallback='/app/data/pdf_registry.json')
        
        # Get input base path
        input_base = self.get(source_type, 'input_base_path', 
                             fallback='/app/data/input')
        
        # Get pattern
        if file_type == 'pdf':
            pattern_key = 'input_pdf_pattern'
        elif file_type == 'json':
            pattern_key = 'input_json_pattern'
        else:
            raise ValueError(f"Unknown file type: {file_type}")
        
        return self.build_file_path(
            pattern_key,
            user_id,
            session_id,
            pdf_doc_id,
            base_path=input_base
        )
    
    def get_source_output_path(
        self,
        file_type: str,
        user_id: int,
        session_id: str,
        pdf_doc_id: int
    ) -> str:
        """
        Get output file path in source storage.
        
        Args:
            file_type: 'embedded_pdf' or 'filled_pdf'
            user_id: User ID
            session_id: Session ID
            pdf_doc_id: PDF document ID
        
        Returns:
            Full path in source storage (e.g., /app/data/output/xxx_filled.pdf)
        """
        source_type = self.get_source_type()
        output_base = self.get(source_type, 'output_base_path',
                              fallback='/app/data/output')
        
        pattern_key = f'output_{file_type}'
        
        return self.build_file_path(
            pattern_key,
            user_id,
            session_id,
            pdf_doc_id,
            base_path=output_base
        )


# Singleton instance
_file_config = None

def get_file_config(config_path: str = None) -> FileConfig:
    """Get singleton FileConfig instance."""
    global _file_config
    if _file_config is None:
        _file_config = FileConfig(config_path)
    return _file_config
