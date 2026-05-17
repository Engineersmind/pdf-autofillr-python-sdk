"""
Embedder Plugin Interface

For custom metadata embedding strategies.
"""

from abc import abstractmethod
from typing import Dict, Any, Optional
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class EmbedderPlugin(BasePlugin):
    """
    Base class for metadata embedder plugins.
    
    Embedder plugins embed metadata into PDFs.
    """
    
    @abstractmethod
    def embed(
        self,
        pdf_path: str,
        metadata: Dict[str, Any],
        output_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Embed metadata into PDF.
        
        Args:
            pdf_path: Path to source PDF
            metadata: Metadata to embed
            output_path: Path for output PDF (optional)
            **kwargs: Additional embedder-specific parameters
            
        Returns:
            Dict with results:
            {
                "output_path": "...",
                "embedded_keys": [...],
                "embedder": "plugin-name"
            }
        """
        pass
    
    @abstractmethod
    def check(
        self,
        pdf_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Check if PDF has embedded metadata.
        
        Args:
            pdf_path: Path to PDF file
            **kwargs: Additional parameters
            
        Returns:
            Dict with metadata info:
            {
                "has_metadata": True,
                "metadata": {...},
                "embedded_keys": [...]
            }
        """
        pass
    
    def supports_format(self, format_type: str) -> bool:
        """
        Check if embedding format is supported.
        
        Args:
            format_type: Format type (e.g., "xmp", "custom")
            
        Returns:
            True if supported
        """
        return format_type == "custom"
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for embedders"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom metadata embedder",
            category="embedder"
        )
