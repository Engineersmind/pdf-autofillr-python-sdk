"""
File Handlers - Unified interface for input/output file operations.

This module provides a source-agnostic way to handle files in operations:
- InputFileHandler: Download/copy files from source storage
- OutputFileHandler: Upload/copy files to source storage

Usage in operations:
    from pdf_autofillr_mapper.handlers.file_handlers import create_file_handlers
    
    input_handler, output_handler = create_file_handlers(config)
    
    # Get input file (already downloaded)
    pdf_path = input_handler.get_input('input_pdf')
    
    # After creating output file
    output_handler.save_output('/tmp/processing/output.json', 'extracted_json')
"""

from .input_handler import InputFileHandler, create_input_handler
from .output_handler import OutputFileHandler, create_output_handler


def create_file_handlers(config):
    """
    Create both input and output handlers from config.
    Args:
        config: Storage config (LocalStorageConfig, AWSStorageConfig, etc.)
    Returns:
        Tuple of (InputFileHandler, OutputFileHandler)
    Example:
        input_handler, output_handler = create_file_handlers(config)
        
        # Download input
        pdf = input_handler.get_input('input_pdf')
        
        # Save output
        output_handler.save_output(local_file, 'extracted_json')
    """
    input_handler = create_input_handler(config)
    output_handler = create_output_handler(config)
    
    return input_handler, output_handler


__all__ = [
    'InputFileHandler',
    'OutputFileHandler',
    'create_input_handler',
    'create_output_handler',
    'create_file_handlers'
]
