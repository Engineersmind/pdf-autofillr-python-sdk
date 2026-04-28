"""
Mapper Plugin Interface

For custom field mapping strategies.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class MapperPlugin(BasePlugin):
    """
    Base class for field mapper plugins.
    
    Mapper plugins map extracted fields to target schemas.
    """
    
    @abstractmethod
    def map_fields(
        self,
        extracted_fields: List[Dict[str, Any]],
        target_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Map extracted fields to target schema.
        
        Args:
            extracted_fields: List of extracted fields
            target_schema: Target schema (optional)
            **kwargs: Additional mapper-specific parameters
            
        Returns:
            Dict with mapped data:
            {
                "mapped_fields": {...},
                "mapping_info": {...},
                "mapper": "plugin-name"
            }
        """
        pass
    
    @abstractmethod
    def supports_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Check if this plugin can handle the target schema.
        
        Args:
            schema: Target schema
            
        Returns:
            True if plugin can map to this schema
        """
        pass
    
    def get_mapping_confidence(
        self,
        extracted_fields: List[Dict[str, Any]],
        target_schema: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for mapping.
        
        Args:
            extracted_fields: Extracted fields
            target_schema: Target schema
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        return 0.5  # Default: medium confidence
    
    def validate_mapping(
        self,
        mapped_fields: Dict[str, Any],
        target_schema: Dict[str, Any]
    ) -> bool:
        """
        Validate that mapping conforms to target schema.
        
        Args:
            mapped_fields: Mapped fields
            target_schema: Target schema
            
        Returns:
            True if valid
        """
        # Default: assume valid
        return True
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for mappers"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom field mapper",
            category="mapper"
        )
