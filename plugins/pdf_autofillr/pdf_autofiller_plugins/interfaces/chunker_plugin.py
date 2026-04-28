"""
Chunker Plugin Interface

For custom PDF chunking strategies.
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional
from pdf_autofiller_plugins.interfaces.base_plugin import BasePlugin, PluginMetadata


class ChunkerPlugin(BasePlugin):
    """
    Base class for PDF chunker plugins.
    
    Chunker plugins split PDFs into logical chunks for processing.
    """
    
    @abstractmethod
    def chunk(
        self,
        pdf_path: str,
        chunk_size: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Chunk PDF into logical segments.
        
        Args:
            pdf_path: Path to PDF file
            chunk_size: Target chunk size (optional)
            **kwargs: Additional chunker-specific parameters
            
        Returns:
            List of chunks:
            [
                {
                    "chunk_id": "...",
                    "content": "...",
                    "page_numbers": [1, 2],
                    "metadata": {...}
                },
                ...
            ]
        """
        pass
    
    def get_optimal_chunk_size(self, pdf_path: str) -> int:
        """
        Calculate optimal chunk size for this PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Optimal chunk size
        """
        return 1000  # Default: 1000 chars per chunk
    
    def supports_chunking_strategy(self, strategy: str) -> bool:
        """
        Check if chunking strategy is supported.
        
        Args:
            strategy: Chunking strategy name
            
        Returns:
            True if supported
        """
        return strategy in ["page", "paragraph", "fixed"]
    
    def get_metadata(self) -> PluginMetadata:
        """Default metadata for chunkers"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            author="Unknown",
            description="Custom PDF chunker",
            category="chunker"
        )
