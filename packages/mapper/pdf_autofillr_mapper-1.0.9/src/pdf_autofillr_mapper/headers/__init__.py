"""
Headers module for extracting hierarchical form field data points.
"""

# Both imports are lazy to avoid pulling in litellm/unified_llm_client
# at module load time when only create_rag_api_files is needed.
__all__ = ['get_form_fields_points', 'create_rag_api_files']

def __getattr__(name):
    if name == 'create_rag_api_files':
        from .create_rag_files import create_rag_api_files
        return create_rag_api_files
    if name == 'get_form_fields_points':
        from .get_form_fields_points import get_form_fields_points
        return get_form_fields_points
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")