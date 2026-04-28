"""
Extractor Plugin Interface

For custom PDF field extractors.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class ExtractorPlugin(BasePlugin):
    """
    Base class for field extractor plugins.
    
    Extractor plugins extract structured data from PDFs.
    """
    
    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        strategy: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract fields from PDF.
        
        Args:
            pdf_path: Path to PDF file (local or cloud URL)
            strategy: Extraction strategy (optional)
            **kwargs: Additional extractor-specific parameters
            
        Returns:
            Dict with extracted data:
            {
                "fields": [{"name": "field1", "value": "...", ...}],
                "metadata": {...},
                "extractor": "plugin-name"
            }
        """
        pass
    
    @abstractmethod
    def supports(self, pdf_path: str, **kwargs) -> bool:
        """
        Check if this plugin can handle the PDF.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional context
            
        Returns:
            True if plugin can extract from this PDF
        """
        pass
    
    def get_supported_strategies(self) -> List[str]:
        """
        Get list of extraction strategies supported by this plugin.
        
        Returns:
            List of strategy names
        """
        return ["default"]
    
    def validate_pdf(self, pdf_path: str) -> bool:
        """
        Validate that PDF is accessible and readable.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if valid
        """
        # Default: assume valid
        return True
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for extractors"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom PDF extractor",
            category="extractor"
        )


class ExtractorResult:
    """Helper class for extractor results"""
    
    def __init__(
        self,
        fields: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        extractor: Optional[str] = None,
        confidence: Optional[float] = None
    ):
        self.fields = fields
        self.metadata = metadata or {}
        self.extractor = extractor
        self.confidence = confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "fields": self.fields,
            "metadata": self.metadata,
        }
        if self.extractor:
            result["extractor"] = self.extractor
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result
