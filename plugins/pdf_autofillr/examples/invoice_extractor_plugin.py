"""
Example: Custom Invoice Extractor Plugin

This example shows how to create a custom extractor plugin for invoice PDFs.
"""

from typing import Dict, Any
from pdf_autofiller_plugins import plugin
from pdf_autofiller_plugins.interfaces import ExtractorPlugin, PluginMetadata


@plugin(
    category="extractor",
    name="invoice-extractor",
    version="1.0.0",
    author="Example Team",
    description="Specialized extractor for invoice PDFs",
    tags=["invoice", "financial", "extractor"],
    priority=200  # Higher priority than default
)
class InvoiceExtractorPlugin(ExtractorPlugin):
    """
    Custom extractor optimized for invoice PDFs.
    
    Looks for common invoice fields like:
    - Invoice number
    - Date
    - Vendor information
    - Line items
    - Total amount
    """
    
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="invoice-extractor",
            version="1.0.0",
            author="Example Team",
            description="Specialized extractor for invoice PDFs",
            category="extractor",
            tags=["invoice", "financial"],
        )
    
    def supports(self, pdf_path: str, **kwargs) -> bool:
        """
        Check if this is an invoice PDF.
        
        In a real implementation, you might:
        - Check filename for "invoice"
        - Look at PDF metadata
        - Sample first page text
        """
        # Simple check: filename contains "invoice"
        return "invoice" in pdf_path.lower()
    
    def extract(
        self,
        pdf_path: str,
        strategy: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract invoice fields.
        
        In a real implementation, you would:
        - Parse PDF with specialized invoice templates
        - Use OCR if needed
        - Extract line items
        - Calculate totals
        """
        # Example extracted data
        fields = [
            {
                "name": "invoice_number",
                "value": "INV-2026-001",
                "type": "text",
                "confidence": 0.95,
                "bbox": [100, 50, 200, 70]
            },
            {
                "name": "invoice_date",
                "value": "2026-03-03",
                "type": "date",
                "confidence": 0.98,
                "bbox": [100, 80, 200, 100]
            },
            {
                "name": "vendor_name",
                "value": "Acme Corporation",
                "type": "text",
                "confidence": 0.92,
                "bbox": [100, 110, 300, 130]
            },
            {
                "name": "total_amount",
                "value": "1234.56",
                "type": "currency",
                "confidence": 0.99,
                "bbox": [400, 500, 500, 520]
            },
        ]
        
        return {
            "fields": fields,
            "metadata": {
                "page_count": 1,
                "extraction_time": "2026-03-03T12:00:00Z",
                "document_type": "invoice",
            },
            "extractor": "invoice-extractor",
            "confidence": 0.96
        }
    
    def get_supported_strategies(self):
        return ["template", "ml", "hybrid"]


# Example usage:
if __name__ == "__main__":
    from pdf_autofiller_plugins import PluginManager
    
    # Initialize plugin manager
    manager = PluginManager()
    
    # Register plugin manually
    manager.registry.register_plugin(
        InvoiceExtractorPlugin,
        category="extractor",
        name="invoice-extractor"
    )
    
    # Load plugin
    plugin = manager.load_plugin("invoice-extractor", "extractor")
    
    # Test extraction
    result = plugin.extract("sample_invoice.pdf")
    print(f"Extracted {len(result['fields'])} fields")
    print(f"Confidence: {result.get('confidence', 0):.2%}")
