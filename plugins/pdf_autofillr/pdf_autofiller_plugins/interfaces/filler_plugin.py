"""
Filler Plugin Interface

For custom PDF filling strategies.
"""

from abc import abstractmethod
from typing import Dict, Any, Optional, List
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class FillerPlugin(BasePlugin):
    """
    Base class for PDF filler plugins.
    
    Filler plugins fill PDFs with data.
    """
    
    @abstractmethod
    def fill(
        self,
        pdf_path: str,
        data: Dict[str, Any],
        output_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fill PDF with data.
        
        Args:
            pdf_path: Path to template PDF
            data: Data to fill
            output_path: Path for output PDF (optional)
            **kwargs: Additional filler-specific parameters
            
        Returns:
            Dict with results:
            {
                "output_path": "...",
                "filled_fields": [...],
                "unfilled_fields": [...],
                "filler": "plugin-name"
            }
        """
        pass
    
    @abstractmethod
    def supports_pdf_type(self, pdf_path: str) -> bool:
        """
        Check if filler supports this PDF type.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if supported
        """
        pass
    
    def get_fillable_fields(self, pdf_path: str) -> List[str]:
        """
        Get list of fillable fields in PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of field names
        """
        return []
    
    def validate_data(
        self,
        pdf_path: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that data can fill the PDF.
        
        Args:
            pdf_path: Path to PDF file
            data: Data to validate
            
        Returns:
            Validation results
        """
        return {"valid": True, "errors": []}
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for fillers"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom PDF filler",
            category="filler"
        )
