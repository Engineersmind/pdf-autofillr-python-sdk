"""
Validator Plugin Interface

For custom field validation rules.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class ValidatorPlugin(BasePlugin):
    """
    Base class for field validator plugins.
    
    Validator plugins validate field values against rules.
    """
    
    @abstractmethod
    def validate(
        self,
        field_name: str,
        field_value: Any,
        rules: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Validate field value.
        
        Args:
            field_name: Name of field
            field_value: Value to validate
            rules: Validation rules (optional)
            **kwargs: Additional validator-specific parameters
            
        Returns:
            Dict with validation results:
            {
                "valid": True/False,
                "errors": [...],
                "warnings": [...],
                "validator": "plugin-name"
            }
        """
        pass
    
    @abstractmethod
    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type.
        
        Args:
            field_type: Field type (e.g., "email", "phone", "date")
            
        Returns:
            True if supported
        """
        pass
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """
        Get default validation rules for this validator.
        
        Returns:
            Dict of validation rules
        """
        return {}
    
    def validate_batch(
        self,
        fields: Dict[str, Any],
        rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validate multiple fields at once.
        
        Args:
            fields: Dict of field_name -> field_value
            rules: Validation rules (optional)
            
        Returns:
            Dict with validation results for all fields
        """
        results = {}
        for field_name, field_value in fields.items():
            results[field_name] = self.validate(field_name, field_value, rules)
        return results
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for validators"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom field validator",
            category="validator"
        )
