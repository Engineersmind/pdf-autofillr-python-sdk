"""
Transformer Plugin Interface

For custom data transformation logic.
"""

from abc import abstractmethod
from typing import Any, Dict, Optional
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class TransformerPlugin(BasePlugin):
    """
    Base class for data transformer plugins.
    
    Transformer plugins transform field values.
    """
    
    @abstractmethod
    def transform(
        self,
        value: Any,
        transform_type: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Transform a value.
        
        Args:
            value: Value to transform
            transform_type: Type of transformation (optional)
            **kwargs: Additional transformer-specific parameters
            
        Returns:
            Transformed value
        """
        pass
    
    @abstractmethod
    def supports_type(self, value_type: type) -> bool:
        """
        Check if transformer supports this value type.
        
        Args:
            value_type: Python type
            
        Returns:
            True if supported
        """
        pass
    
    def get_supported_transformations(self) -> list[str]:
        """
        Get list of supported transformation types.
        
        Returns:
            List of transformation type names
        """
        return ["default"]
    
    def can_reverse(self) -> bool:
        """
        Check if transformation is reversible.
        
        Returns:
            True if can reverse transformation
        """
        return False
    
    def reverse(self, value: Any, **kwargs) -> Any:
        """
        Reverse a transformation.
        
        Args:
            value: Transformed value
            **kwargs: Additional parameters
            
        Returns:
            Original value
        """
        raise NotImplementedError("Transformation is not reversible")
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for transformers"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom data transformer",
            category="transformer"
        )
