"""
INI-based configuration loader for file paths and storage settings.

This module reads the config.ini file and provides easy access to configuration values.
It supports different storage backends (AWS, Azure, GCP, Local) and allows users to
customize file paths and settings based on their environment.
"""

import os
import configparser
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class IniConfigLoader:
    """Loads and manages configuration from INI file."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to config.ini file. If None, searches in standard locations.
        """
        self.config = configparser.ConfigParser()
        
        # Find config file
        if config_path:
            self.config_path = config_path
        else:
            self.config_path = self._find_config_file()
        
        # Load configuration
        if self.config_path and os.path.exists(self.config_path):
            logger.info(f"Loading configuration from: {self.config_path}")
            self.config.read(self.config_path)
        else:
            logger.warning(f"Config file not found: {self.config_path}. Using environment variables.")
    
    def _find_config_file(self) -> str:
        """
        Find config.ini file in standard locations.
        
        Search order:
        1. Environment variable: PDF_AUTOFILLER_CONFIG
        2. Current working directory: ./config.ini
        3. Mapper module root: ../config.ini (relative to this file)
        4. Project root: ../../config.ini
        """
        # 1. Check environment variable
        env_config = os.getenv('PDF_AUTOFILLER_CONFIG')
        if env_config and os.path.exists(env_config):
            return env_config
        
        # 2. Current working directory
        cwd_config = os.path.join(os.getcwd(), 'config.ini')
        if os.path.exists(cwd_config):
            return cwd_config
        
        # 3. Mapper module root (modules/mapper/config.ini)
        module_root = Path(__file__).parent.parent.parent
        module_config = module_root / 'config.ini'
        if module_config.exists():
            return str(module_config)
        
        # 4. Project root (../../config.ini from mapper)
        project_config = module_root.parent.parent / 'config.ini'
        if project_config.exists():
            return str(project_config)
        
        logger.warning("Config file not found in standard locations")
        return ""
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """
        Get configuration value.
        
        Falls back to environment variables if key not found in config file.
        Environment variable format: SECTION_KEY (uppercase)
        
        Args:
            section: Section name (e.g., 'general', 'aws')
            key: Key name (e.g., 'source_type', 'cache_registry_path')
            fallback: Default value if not found
            
        Returns:
            Configuration value
        """
        # Try config file first
        if self.config.has_section(section) and self.config.has_option(section, key):
            value = self.config.get(section, key)
            # Handle boolean values
            if value.lower() in ('true', 'yes', '1'):
                return True
            elif value.lower() in ('false', 'no', '0'):
                return False
            # Handle integer values
            try:
                return int(value)
            except ValueError:
                pass
            # Handle float values
            try:
                return float(value)
            except ValueError:
                pass
            return value
        
        # Fall back to environment variable
        env_key = f"{section.upper()}_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            logger.debug(f"Using environment variable {env_key} for {section}.{key}")
            return env_value
        
        return fallback
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get all configuration values from a section.
        
        Args:
            section: Section name
            
        Returns:
            Dictionary of key-value pairs
        """
        if not self.config.has_section(section):
            return {}
        
        return dict(self.config.items(section))
    
    def get_source_type(self) -> str:
        """Get configured storage source type (aws, azure, gcp, or local)."""
        return self.get('general', 'source_type', fallback='aws')
    
    def get_cache_registry_path(self) -> Optional[str]:
        """Get hash cache registry file path."""
        return self.get('general', 'cache_registry_path')
    
    def is_cache_enabled(self) -> bool:
        """Check if PDF hash caching is enabled."""
        return self.get('general', 'pdf_cache_enabled', fallback=True)
    
    def get_storage_config(self) -> Dict[str, Any]:
        """
        Get storage configuration for the active source type.
        
        Returns:
            Dictionary with storage-specific configuration
        """
        source_type = self.get_source_type()
        return self.get_section(source_type)
    
    def get_path_template(self, template_name: str) -> Optional[str]:
        """
        Get path template from [paths] section.
        
        Args:
            template_name: Template name (e.g., 'extraction_template', 'mapping_template')
            
        Returns:
            Path template string with variables like {user_id}, {pdf_doc_id}
        """
        return self.get('paths', template_name)
    
    def format_path(self, template_name: str, **kwargs) -> str:
        """
        Format a path template with provided variables.
        
        Args:
            template_name: Template name from [paths] section
            **kwargs: Variables to substitute (e.g., user_id=123, pdf_doc_id=456)
            
        Returns:
            Formatted path string
            
        Example:
            loader.format_path('extraction_template',
                              output_base_path='s3://bucket/data',
                              user_id=123,
                              pdf_doc_id=456,
                              filename='form')
            # Returns: s3://bucket/data/users/123/pdfs/456/extraction/form_extracted.json
        """
        template = self.get_path_template(template_name)
        if not template:
            raise ValueError(f"Path template not found: {template_name}")
        
        # Add storage config variables (output_base_path, rag_base_path, etc.)
        source_type = self.get_source_type()
        storage_config = self.get_storage_config()
        
        # Merge storage config with provided kwargs
        format_vars = {**storage_config, **kwargs}
        
        try:
            return template.format(**format_vars)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} for template {template_name}")
    
    def get_mapping_config(self) -> Dict[str, Any]:
        """Get mapping configuration."""
        config = self.get_section('mapping')
        # Convert string booleans to actual booleans
        if 'use_second_mapper' in config:
            config['use_second_mapper'] = config['use_second_mapper'].lower() in ('true', 'yes', '1')
        return config
    
    def get_extraction_config(self) -> Dict[str, Any]:
        """Get extraction configuration."""
        return self.get_section('extraction')
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get_section('logging')
    
    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance configuration."""
        return self.get_section('performance')
    
    def get_notification_config(self) -> Dict[str, Any]:
        """Get notification configuration."""
        config = self.get_section('notifications')
        # Convert string booleans
        if 'teams_notifications_enabled' in config:
            config['teams_notifications_enabled'] = config['teams_notifications_enabled'].lower() in ('true', 'yes', '1')
        if 'include_metadata' in config:
            config['include_metadata'] = config['include_metadata'].lower() in ('true', 'yes', '1')
        return config


# Global configuration instance
_ini_config_loader = None


def get_ini_config() -> IniConfigLoader:
    """
    Get global INI configuration loader instance (singleton).
    
    Returns:
        IniConfigLoader instance
    """
    global _ini_config_loader
    if _ini_config_loader is None:
        _ini_config_loader = IniConfigLoader()
    return _ini_config_loader


def reload_ini_config(config_path: Optional[str] = None):
    """
    Reload INI configuration from file.
    
    Args:
        config_path: Optional path to config file
    """
    global _ini_config_loader
    _ini_config_loader = IniConfigLoader(config_path)


# Convenience functions
def get_source_type() -> str:
    """Get configured storage source type."""
    return get_ini_config().get_source_type()


def get_cache_registry_path() -> Optional[str]:
    """Get hash cache registry file path."""
    return get_ini_config().get_cache_registry_path()


def is_cache_enabled() -> bool:
    """Check if PDF hash caching is enabled."""
    return get_ini_config().is_cache_enabled()


def get_storage_config() -> Dict[str, Any]:
    """Get storage configuration for active source type."""
    return get_ini_config().get_storage_config()


def format_output_path(template_name: str, **kwargs) -> str:
    """
    Format an output path using template from config.
    
    Args:
        template_name: Template name (e.g., 'extraction_template')
        **kwargs: Variables for template (user_id, pdf_doc_id, filename, etc.)
        
    Returns:
        Formatted path string
    """
    return get_ini_config().format_path(template_name, **kwargs)
