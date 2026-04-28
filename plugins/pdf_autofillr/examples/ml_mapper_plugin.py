"""
Example: Custom ML Mapper Plugin

This example shows how to create a custom mapper plugin using ML.
"""

from typing import Dict, Any, List, Optional
from pdf_autofiller_plugins import plugin
from pdf_autofiller_plugins.interfaces import MapperPlugin, PluginMetadata


@plugin(
    category="mapper",
    name="ml-mapper",
    version="1.0.0",
    author="Example Team",
    description="ML-based field mapper",
    tags=["ml", "ai", "mapper"],
    priority=150
)
class MLMapperPlugin(MapperPlugin):
    """
    Custom mapper that uses ML to map fields.
    
    In a real implementation, this would:
    - Use embeddings to match field names
    - Learn from historical mappings
    - Handle fuzzy matching
    """
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ml-mapper",
            version="1.0.0",
            author="Example Team",
            description="ML-based field mapper",
            category="mapper",
            tags=["ml", "ai"],
            dependencies=["numpy", "scikit-learn"]  # If you need these
        )
    
    def supports_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Check if we can map to this schema.
        
        In a real implementation, you might check:
        - Schema format
        - Required fields
        - Complexity
        """
        # Accept all schemas for this example
        return True
    
    def map_fields(
        self,
        extracted_fields: List[Dict[str, Any]],
        target_schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Map extracted fields using ML.
        
        In a real implementation:
        - Calculate field embeddings
        - Use trained model to predict mappings
        - Apply confidence thresholds
        """
        mapped_fields = {}
        mapping_info = []
        
        for field in extracted_fields:
            field_name = field.get("name", "")
            field_value = field.get("value", "")
            
            # Simple example: map based on name similarity
            # In reality, use ML model here
            target_field = self._predict_target_field(field_name, target_schema)
            
            if target_field:
                mapped_fields[target_field] = field_value
                mapping_info.append({
                    "source": field_name,
                    "target": target_field,
                    "confidence": 0.85,
                    "method": "ml-prediction"
                })
        
        return {
            "mapped_fields": mapped_fields,
            "mapping_info": mapping_info,
            "mapper": "ml-mapper",
            "confidence": 0.85
        }
    
    def _predict_target_field(
        self,
        source_field: str,
        target_schema: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Predict target field name using ML.
        
        In a real implementation:
        - Use trained neural network
        - Calculate semantic similarity
        - Use ensemble of models
        """
        # Simple mapping for example
        mappings = {
            "first_name": "firstName",
            "last_name": "lastName",
            "email": "emailAddress",
            "phone": "phoneNumber",
            "invoice_number": "invoiceNo",
        }
        return mappings.get(source_field.lower())
    
    def get_mapping_confidence(
        self,
        extracted_fields: List[Dict[str, Any]],
        target_schema: Dict[str, Any]
    ) -> float:
        """Calculate confidence score"""
        # In reality, use model's confidence scores
        return 0.85


# Example usage:
if __name__ == "__main__":
    from pdf_autofiller_plugins import PluginManager
    
    manager = PluginManager()
    manager.registry.register_plugin(MLMapperPlugin, "mapper", "ml-mapper")
    
    plugin = manager.load_plugin("ml-mapper", "mapper")
    
    # Test mapping
    extracted = [
        {"name": "first_name", "value": "John"},
        {"name": "last_name", "value": "Doe"},
        {"name": "email", "value": "john@example.com"},
    ]
    
    result = plugin.map_fields(extracted)
    print(f"Mapped {len(result['mapped_fields'])} fields")
    print(f"Mappings: {result['mapped_fields']}")
