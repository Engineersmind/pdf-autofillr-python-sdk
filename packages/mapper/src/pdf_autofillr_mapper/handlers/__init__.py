"""
Core operation handlers - source-agnostic business logic.

These handlers work with any storage backend (S3, GCS, Azure, local).
Platform wrappers (lambda, azure function, gcp function) call these.
"""

from .operations import (
    handle_extract_operation,
    handle_map_operation,
    handle_embed_operation,
    handle_fill_operation,
    handle_run_all_operation,
    handle_refresh_operation,
    handle_make_embed_file_operation,
    handle_make_form_fields_data_points,
    handle_fill_pdf_operation,
    handle_check_embed_file_operation
)

__all__ = [
    'handle_extract_operation',
    'handle_map_operation',
    'handle_embed_operation',
    'handle_fill_operation',
    'handle_run_all_operation',
    'handle_refresh_operation',
    'handle_make_embed_file_operation',
    'handle_make_form_fields_data_points',
    'handle_fill_pdf_operation',
    'handle_check_embed_file_operation'
]
