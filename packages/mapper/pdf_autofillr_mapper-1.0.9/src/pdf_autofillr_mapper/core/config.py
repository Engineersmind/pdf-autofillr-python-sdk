# main/modules2/mapper/src/pdf_autofillr_mapper/core/config.py
import os
import configparser
from pathlib import Path
from typing import Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings

# Load config.ini
config_ini = configparser.ConfigParser()

def _find_config_ini():
    """Find config.ini without crashing if it doesn't exist."""
    candidates = [
        Path("config.ini"),
        Path(__file__).parent.parent.parent / "config.ini",
        Path(__file__).parent.parent / "config.ini",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

_cfg_path = _find_config_ini()
if _cfg_path:
    config_ini.read(_cfg_path)

def get_ini_value(section: str, key: str, fallback=None):
    """Helper to safely get value from config.ini"""
    try:
        if fallback is None:
            return config_ini.get(section, key)
        return config_ini.get(section, key, fallback=fallback)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return fallback

def get_ini_int(section: str, key: str, fallback: int):
    """Helper to safely get int value from config.ini"""
    try:
        return config_ini.getint(section, key, fallback=fallback)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback

def get_ini_float(section: str, key: str, fallback: float):
    """Helper to safely get float value from config.ini"""
    try:
        return config_ini.getfloat(section, key, fallback=fallback)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback

def get_ini_bool(section: str, key: str, fallback: bool):
    """Helper to safely get boolean value from config.ini"""
    try:
        return config_ini.getboolean(section, key, fallback=fallback)
    except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
        return fallback

def get_source_type() -> str:
    """Get the source_type from [general] section to determine which config section to use"""
    return get_ini_value("general", "source_type", "local")

class Settings(BaseSettings):
    # LLM Configuration (Legacy - kept for backwards compatibility)
    llm_current_provider: str = "claude"
    llm_max_threads: int = 10
    
    # LiteLLM Configuration (loaded from config.ini [mapping] section)
    llm_model: str = get_ini_value("mapping", "llm_model", "gpt-4o")
    llm_temperature: float = get_ini_float("mapping", "llm_temperature", 0.0)
    llm_max_tokens: int = get_ini_int("mapping", "llm_max_tokens", 4096)
    llm_timeout: int = get_ini_int("mapping", "llm_timeout", 120)
    llm_max_retries: int = get_ini_int("mapping", "llm_max_retries", 3)
    
    # Claude/Bedrock Configuration (Legacy)
    claude_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    claude_region: str = "us-east-1"
    claude_temperature: float = 0.1
    claude_max_tokens: int = 20000
    
    # OpenAI Configuration (Legacy)
    openai_model_id: str = "gpt-4"
    openai_api_key: str = ""
    openai_temperature: float = 0.1
    openai_max_tokens: int = 2048
    
    # File Paths Configuration
    # Input file paths
    data_input_dir: str = "data/input"
    temp_data_dir: str = "data/temp" 
    
    # Output file paths  
    data_output_dir: str = "data/output"
    
    # Mapper Configuration
    mapper_current_method: str = "semantic"
    # mapper_method_llm: str = "claude"
    mapper_method_llm: str = "gpt-4o"
    mapper_method_include_key_variants: int = 0
    mapper_method_include_field_name_variants: int = 0
    mapper_method_include_description: int = 1
    mapper_method_confidence_threshold: float = 0.7
    
    # Feedback Semantic Method
    mapper_feedback_llm1: str = "claude"
    mapper_feedback_llm2: str = "openai"
    
    # Embedding Method
    mapper_embed_provider: str = "claude"
    
    # Chunking Strategy Configuration
    mapper_chunking_current_strategy: str = "page"
    mapper_chunking_page_chunk_size: int = 9
    mapper_chunking_page_overlap: int = 1
    mapper_chunking_window_prefix_threshold: int = 10
    mapper_chunking_window_suffix_threshold: int = 10
    mapper_chunking_window_lines_limit: int = 400
    
    # Legacy Semantic Mapper Configuration (deprecated)
    semantic_mapper_confidence_threshold: float = 0.7
    semantic_mapper_include_key_variants: int = 0
    semantic_mapper_include_field_name_variants: int = 0
    semantic_mapper_include_description: int = 0
    
    # Storage Configuration
    storage_type: str = "local"  # "local" or "s3"
    storage_s3_bucket: str = ""
    storage_s3_prefix: str = ""
    
    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_profile: str = ""
    
    # Notification Configuration
    notifications_enabled: bool = True
    notifications_backend_url: str = ""
    notifications_api_key: str = ""
    notifications_api_token: str = ""
    notifications_timeout_seconds: int = 30
    notifications_max_retries: int = 3
    notifications_retry_delay_seconds: float = 1.0
    notifications_fail_silently: bool = True

    # MS Teams Notification Configuration
    teams_enabled: bool = False
    teams_webhook_url: str = ""
    teams_timeout_seconds: int = 30
    teams_max_retries: int = 3

    mapper_lambda_api_token: str = ""

    # Webhook Adapter Configuration
    webhook_enabled: bool = True
    webhook_lambda_name: str = "pdf-pipeline-webhook-adapter"
    webhook_region: str = "us-east-1"
    
    # Authentication Configuration
    auth_api_base_url: str = "https://dev-autofiller-backend.engineersmind.dev"
    auth_email: str = ""
    auth_password: str = ""
    auth_timeout_seconds: int = 30
    
    # S3 Input Data Bucket for user/session data
    s3_input_data_bucket: str = ""
    
    # Global mapping input JSON (semantic keys definition) used for make_embed_file pipeline
    # Example: s3://my-bucket/global_mapping_keys.json
    global_input_json_s3_uri: str = ""
    
    # PDF Hash Cache Configuration
    pdf_cache_enabled: bool = True  # Enable/disable hash cache for MAP stage optimization
    pdf_cache_bucket: str = ""  # S3 bucket for cache storage (defaults to storage_s3_bucket if empty)
    pdf_cache_prefix: str = "pdf-registry"  # S3 prefix for cache files
    
    # Cache registry path - read from config.ini based on source_type
    # Will use [local], [aws], [azure], or [gcp] section based on source_type in [general]
    cache_registry_path: str = get_ini_value(get_source_type(), "cache_registry_path", "")
    
    # Headers Extraction Configuration (loaded from config.ini [headers] section)
    headers_llm_provider: str = get_ini_value("headers", "headers_llm_provider", "")
    headers_openai_model_id: str = get_ini_value("headers", "headers_openai_model_id", "gpt-4o")
    headers_claude_model_id: str = get_ini_value("headers", "headers_claude_model_id", "claude-3-5-sonnet-20241022")
    headers_chunk_size: int = get_ini_int("headers", "headers_chunk_size", 5)
    headers_max_workers: int = get_ini_int("headers", "headers_max_workers", 3)
    headers_temperature: float = get_ini_float("headers", "headers_temperature", 0.0)
    headers_max_tokens: int = get_ini_int("headers", "headers_max_tokens", 8192)
    
    # RAG API Configuration (for second mapper)
    # Read from .env file - maps RAG_API_ENDPOINT to rag_api_url
    rag_api_url: str = ""
    rag_api_key: str = ""
    rag_bucket_name: str = "rag-bucket-pdf-filler"  # S3 bucket for RAG predictions

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = ""
        extra = "allow"  # Allow extra fields from .env that aren't defined in Settings
        populate_by_name = True  # Allow population by field name or alias

_settings_cache = None

def get_settings():
    """Return singleton Settings instance (lazy — never crashes on import)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = Settings()
    return _settings_cache


class _LazySettings:
    """Proxy that forwards attribute access to get_settings()."""
    def __getattr__(self, name):
        return getattr(get_settings(), name)


settings = _LazySettings()

def get_llm_config() -> Dict[str, Any]:
    """Get LLM configuration in the format expected by LLM clients"""
    return {
        "llm": {
            "current_provider": settings.llm_current_provider,
            "max_threads": settings.llm_max_threads,
            "claude": {
                "model_id": settings.claude_model_id,
                "region": settings.claude_region,
                "temperature": settings.claude_temperature,
                "max_tokens": settings.claude_max_tokens
            },
            "openai": {
                "model_id": settings.openai_model_id,
                "api_key": settings.openai_api_key or os.getenv("OPENAI_API_KEY", ""),
                "temperature": settings.openai_temperature,
                "max_tokens": settings.openai_max_tokens
            }
        }
    }

def get_semantic_mapper_config() -> Dict[str, Any]:
    """Get semantic mapper configuration using new mapper settings"""
    return {
        "confidence_threshold": settings.mapper_method_confidence_threshold,
        "include_key_variants": settings.mapper_method_include_key_variants,
        "include_field_name_variants": settings.mapper_method_include_field_name_variants,
        "include_description": settings.mapper_method_include_description,
        "llm": settings.mapper_method_llm
    }

def get_mapper_config() -> Dict[str, Any]:
    """Get complete mapper configuration based on YAML structure"""
    return {
        "method": {
            "current_method": settings.mapper_current_method,
            "methods": [
                {
                    "name": "semantic",
                    "llm": settings.mapper_method_llm,
                    "include_key_variants": settings.mapper_method_include_key_variants,
                    "include_field_name_variants": settings.mapper_method_include_field_name_variants,
                    "include_description": settings.mapper_method_include_description,
                    "confidence_threshold": settings.mapper_method_confidence_threshold
                },
                {
                    "name": "feedback_semantic",
                    "llm1": settings.mapper_feedback_llm1,
                    "llm2": settings.mapper_feedback_llm2
                },
                {
                    "name": "embed",
                    "embedder": {
                        "current_provider": settings.mapper_embed_provider
                    }
                }
            ]
        },
        "chunking": {
            "current_strategy": settings.mapper_chunking_current_strategy,
            "strategies": [
                {
                    "name": "page",
                    "chunk_size": settings.mapper_chunking_page_chunk_size,
                    "overlap": settings.mapper_chunking_page_overlap
                },
                {
                    "name": "window",
                    "prefix_threshold": settings.mapper_chunking_window_prefix_threshold,
                    "suffix_threshold": settings.mapper_chunking_window_suffix_threshold,
                    "lines_limit": settings.mapper_chunking_window_lines_limit
                }
            ]
        }
    }

def get_file_paths(pdf_filename: str) -> Dict[str, str]:
    """Generate standardized file paths for a PDF processing session"""
    base_name = os.path.splitext(pdf_filename)[0]
    
    return {
        # Input paths
        "extracted_path": os.path.join(settings.temp_data_dir, f"{base_name}_extracted.json"),
        "input_json_path": os.path.join(settings.data_input_dir, f"{base_name}_input_keys.json"),
        "input_key_variants_path": os.path.join(settings.data_input_dir, f"{base_name}_key_variants.json"),
        "field_name_variants_path": os.path.join(settings.data_input_dir, f"{base_name}_field_variants.json"),
        
        # Output paths
        "output_mappings_path": os.path.join(settings.data_output_dir, f"{base_name}_mappings.json"),
        "radio_groups_path": os.path.join(settings.data_output_dir, f"{base_name}_radio_groups.json"),
        "filled_pdf_path": os.path.join(settings.data_output_dir, f"{base_name}_filled.pdf"),
    }

def get_storage_config(pdf_filename: str) -> Dict[str, Any]:
    """Generate storage configuration for semantic mapper output"""
    paths = get_file_paths(pdf_filename)
    
    if settings.storage_type == "s3":
        base_name = os.path.splitext(pdf_filename)[0]
        s3_prefix = settings.storage_s3_prefix.rstrip("/")
        return {
            "type": "s3",
            "output_path": f"s3://{settings.storage_s3_bucket}/{s3_prefix}/output/{base_name}_mappings.json",
            "radio_groups": f"s3://{settings.storage_s3_bucket}/{s3_prefix}/output/{base_name}_radio_groups.json"
        }
    else:
        return {
            "type": "local", 
            "output_path": paths["output_mappings_path"],
            "radio_groups": paths["radio_groups_path"]
        }

def get_chunking_config() -> Dict[str, Any]:
    """Get chunking configuration from mapper settings"""
    return {
        "current_strategy": settings.mapper_chunking_current_strategy,
        "strategies": [
            {
                "name": "page",
                "chunk_size": settings.mapper_chunking_page_chunk_size,
                "overlap": settings.mapper_chunking_page_overlap
            },
            {
                "name": "window",
                "prefix_threshold": settings.mapper_chunking_window_prefix_threshold,
                "suffix_threshold": settings.mapper_chunking_window_suffix_threshold,
                "lines_limit": settings.mapper_chunking_window_lines_limit
            }
        ]
    }

# ============================================================================
# File Naming Configuration Functions
# ============================================================================

def get_extraction_output_config(input_pdf_path: str) -> Dict[str, str]:
    """
    Generate extraction output configuration for PDF files.
    
    When input_pdf is given, save extracted data in the same folder with _extracted.json suffix.
    Supports both local paths and S3 paths.
    
    Args:
        input_pdf_path: Path to input PDF (local or S3 path)
        
    Returns:
        Dictionary with extraction file paths
        
    Examples:
        Local: "/path/to/document.pdf" -> "/path/to/document_extracted.json"
        S3: "s3://bucket/folder/document.pdf" -> "s3://bucket/folder/document_extracted.json"
    """
    if input_pdf_path.startswith("s3://"):
        # S3 path handling
        s3_parts = input_pdf_path.split('/')
        bucket = s3_parts[2]
        key_parts = '/'.join(s3_parts[3:])
        
        # Remove .pdf extension and add _extracted.json
        if key_parts.endswith('.pdf'):
            base_key = key_parts[:-4]  # Remove .pdf
        else:
            base_key = os.path.splitext(key_parts)[0]
            
        extracted_key = f"{base_key}_extracted.json"
        
        return {
            "extracted_path": f"s3://{bucket}/{extracted_key}",
            "storage_type": "s3",
            "bucket": bucket,
            "key": extracted_key,
            "folder": '/'.join(s3_parts[3:-1]) if len(s3_parts) > 4 else ""
        }
    else:
        # Local path handling
        folder = os.path.dirname(input_pdf_path)
        filename = os.path.basename(input_pdf_path)
        base_name = os.path.splitext(filename)[0]
        
        extracted_filename = f"{base_name}_extracted.json"
        extracted_path = os.path.join(folder, extracted_filename)
        
        return {
            "extracted_path": extracted_path,
            "storage_type": "local", 
            "folder": folder,
            "filename": extracted_filename,
            "base_name": base_name
        }

def get_processing_output_config(extracted_json_path: str, user_id: int = None, session_id: int = None) -> Dict[str, str]:
    """
    Generate processing output configuration for extracted JSON files.
    
    When extracted_json is given, save remaining files in same folder:
    - Remove _extracted from name and add _radio_groups.json
    - Remove _extracted from name and add _mapping.json
    - If user_id and session_id provided, add _user_{user_id}_session_{session_id} suffix
    
    Supports both local paths and S3 paths.
    
    Args:
        extracted_json_path: Path to extracted JSON file (local or S3 path)
        user_id: Optional user ID for session-based naming
        session_id: Optional session ID for session-based naming
        
    Returns:
        Dictionary with all processing output file paths
        
    Examples:
        Without session:
            Local: "/path/to/document_extracted.json" -> 
                   "/path/to/document_radio_groups.json", "/path/to/document_mapping.json"
            S3: "s3://bucket/folder/document_extracted.json" ->
                "s3://bucket/folder/document_radio_groups.json", "s3://bucket/folder/document_mapping.json"
        
        With session (user_id=15, session_id=42):
            S3: "s3://bucket/folder/document_extracted.json" ->
                "s3://bucket/folder/document_user_15_session_42_radio_groups.json"
                "s3://bucket/folder/document_user_15_session_42_mapping.json"
                "s3://bucket/folder/document_user_15_session_42_filled.pdf"
    """
    # Generate session suffix if both user_id and session_id provided
    session_suffix = ""
    if user_id is not None and session_id is not None:
        session_suffix = f"_user_{user_id}_session_{session_id}"
    if extracted_json_path.startswith("s3://"):
        # S3 path handling
        s3_parts = extracted_json_path.split('/')
        bucket = s3_parts[2]
        key_parts = '/'.join(s3_parts[3:])

        # Remove _extracted.json, _embedded.pdf, or .json and get base name
        if key_parts.endswith('_extracted.json'):
            base_key = key_parts[:-15]  # Remove _extracted.json
        elif key_parts.endswith('_embedded.pdf'):
            base_key = key_parts[:-13]  # Remove _embedded.pdf
        elif key_parts.endswith('.json'):
            base_key = key_parts[:-5]  # Remove .json
            # If it still contains _extracted, remove it
            if base_key.endswith('_extracted'):
                base_key = base_key[:-10]
        else:
            base_key = os.path.splitext(key_parts)[0]
            if base_key.endswith('_extracted'):
                base_key = base_key[:-10]

        return {
            "radio_groups_path": f"s3://{bucket}/{base_key}{session_suffix}_radio_groups.json",
            "mapping_path": f"s3://{bucket}/{base_key}{session_suffix}_mapping.json", 
            "filled_pdf_path": f"s3://{bucket}/{base_key}{session_suffix}_filled.pdf",
            "storage_type": "s3",
            "bucket": bucket,
            "base_key": base_key,
            "folder": '/'.join(s3_parts[3:-1]) if len(s3_parts) > 4 else "",
            "base_name": base_key.split('/')[-1] if '/' in base_key else base_key,
            "session_suffix": session_suffix
        }
    else:
        # Local path handling
        folder = os.path.dirname(extracted_json_path)
        filename = os.path.basename(extracted_json_path)
        
        # Remove _extracted.json and get base name
        if filename.endswith('_extracted.json'):
            base_name = filename[:-15]  # Remove _extracted.json
        elif filename.endswith('.json'):
            base_name = filename[:-5]  # Remove .json
            # If it still contains _extracted, remove it
            if base_name.endswith('_extracted'):
                base_name = base_name[:-10]
        else:
            base_name = os.path.splitext(filename)[0]
            if base_name.endswith('_extracted'):
                base_name = base_name[:-10]
        
        return {
            "radio_groups_path": os.path.join(folder, f"{base_name}{session_suffix}_radio_groups.json"),
            "mapping_path": os.path.join(folder, f"{base_name}{session_suffix}_mapping.json"),
            "filled_pdf_path": os.path.join(folder, f"{base_name}{session_suffix}_filled.pdf"), 
            "storage_type": "local",
            "folder": folder,
            "base_name": base_name,
            "base_key": base_name,
            "session_suffix": session_suffix
        }

def get_headers_output_config(extracted_json_path: str, user_id: int = None, session_id: int = None) -> Dict[str, str]:
    """
    Generate headers output configuration for extracted JSON files.
    
    Creates output paths for:
    - headers_with_fields.json: Hierarchical headers with field ID mappings
    - final_form_fields.json: Final form fields with complete hierarchy data
    
    Args:
        extracted_json_path: Path to extracted JSON file (local or S3 path)
        user_id: Optional user ID for session-based naming
        session_id: Optional session ID for session-based naming
        
    Returns:
        Dictionary with headers output file paths
        
    Examples:
        Without session:
            Local: "/path/to/document_extracted.json" -> 
                   "/path/to/document_headers_with_fields.json"
                   "/path/to/document_final_form_fields.json"
            S3: "s3://bucket/folder/document_extracted.json" ->
                "s3://bucket/folder/document_headers_with_fields.json"
                "s3://bucket/folder/document_final_form_fields.json"
        
        With session (user_id=15, session_id=42):
            S3: "s3://bucket/folder/document_extracted.json" ->
                "s3://bucket/folder/document_user_15_session_42_headers_with_fields.json"
                "s3://bucket/folder/document_user_15_session_42_final_form_fields.json"
    """
    # Generate session suffix if both user_id and session_id provided
    session_suffix = ""
    if user_id is not None and session_id is not None:
        session_suffix = f"_user_{user_id}_session_{session_id}"
    
    if extracted_json_path.startswith("s3://"):
        # S3 path handling
        s3_parts = extracted_json_path.split('/')
        bucket = s3_parts[2]
        key_parts = '/'.join(s3_parts[3:])

        # Remove _extracted.json and get base name
        if key_parts.endswith('_extracted.json'):
            base_key = key_parts[:-15]  # Remove _extracted.json
        elif key_parts.endswith('.json'):
            base_key = key_parts[:-5]  # Remove .json
            if base_key.endswith('_extracted'):
                base_key = base_key[:-10]
        else:
            base_key = os.path.splitext(key_parts)[0]
            if base_key.endswith('_extracted'):
                base_key = base_key[:-10]

        return {
            "headers_with_fields_path": f"s3://{bucket}/{base_key}{session_suffix}_headers_with_fields.json",
            "final_form_fields_path": f"s3://{bucket}/{base_key}{session_suffix}_final_form_fields.json",
            "storage_type": "s3",
            "bucket": bucket,
            "base_key": base_key,
            "folder": '/'.join(s3_parts[3:-1]) if len(s3_parts) > 4 else "",
            "base_name": base_key.split('/')[-1] if '/' in base_key else base_key,
            "session_suffix": session_suffix
        }
    else:
        # Local path handling
        folder = os.path.dirname(extracted_json_path)
        filename = os.path.basename(extracted_json_path)
        
        # Remove _extracted.json and get base name
        if filename.endswith('_extracted.json'):
            base_name = filename[:-15]  # Remove _extracted.json
        elif filename.endswith('.json'):
            base_name = filename[:-5]  # Remove .json
            if base_name.endswith('_extracted'):
                base_name = base_name[:-10]
        else:
            base_name = os.path.splitext(filename)[0]
            if base_name.endswith('_extracted'):
                base_name = base_name[:-10]
        
        return {
            "headers_with_fields_path": os.path.join(folder, f"{base_name}{session_suffix}_headers_with_fields.json"),
            "final_form_fields_path": os.path.join(folder, f"{base_name}{session_suffix}_final_form_fields.json"),
            "storage_type": "local",
            "folder": folder,
            "base_name": base_name,
            "base_key": base_name,
            "session_suffix": session_suffix
        }

def get_lambda_storage_config(file_path: str, output_type: str = "mapping") -> Dict[str, Any]:
    """
    Generate storage configuration for lambda handlers.
    
    This function provides the storage config format expected by existing lambda functions
    while using the new standardized file naming conventions.
    
    Args:
        file_path: Input file path (PDF for extraction, JSON for processing)
        output_type: Type of output ("extraction", "mapping", "radio_groups", "filled_pdf")
        
    Returns:
        Storage configuration dictionary compatible with existing lambda handlers
    """
    if output_type == "extraction":
        config = get_extraction_output_config(file_path)
        return {
            "type": config["storage_type"],
            "path": config["extracted_path"]
        }
    elif output_type in ["mapping", "radio_groups", "filled_pdf"]:
        config = get_processing_output_config(file_path)
        
        path_key = f"{output_type}_path"
        if output_type == "filled_pdf":
            path_key = "filled_pdf_path"
        
        return {
            "type": config["storage_type"],
            "path": config[path_key],
            "bucket": config.get("bucket", ""),
            "folder": config.get("folder", ""),
            "base_name": config.get("base_name", "")
        }
    else:
        raise ValueError(f"Unsupported output_type: {output_type}")

def get_complete_file_config(
    input_file_path: str, 
    user_id: int = None,
    session_id: int = None
) -> Dict[str, Any]:
    """
    Generate complete file configuration for a processing session.
    
    Now source-agnostic! Uses storage factory to detect and handle S3, Azure, GCS, or local paths.
    
    Args:
        input_file_path: Path to input file (PDF or extracted JSON) - can be s3://, gs://, azure://, or local
        user_id: Optional user ID for user-specific output paths
        session_id: Optional session ID for session-specific output paths
        
    Returns:
        Complete configuration with all file paths using the detected storage system
    """
    from pdf_autofillr_mapper.configs.factory import get_storage_config
    
    # Get appropriate storage config based on file path
    storage = get_storage_config(input_file_path)
    
    # Use storage-specific implementation
    return storage.get_complete_file_config(input_file_path, user_id=user_id, session_id=session_id)

def generate_input_keys_path(extracted_json_path: str) -> str:
    """
    Generate the expected input keys file path based on extracted JSON path.
    
    Args:
        extracted_json_path: Path to extracted JSON file
        
    Returns:
        Path where input keys JSON file should be located
        
    Examples:
        - "/path/document_extracted.json" -> "/path/document_input_keys.json"
        - "s3://bucket/doc_extracted.json" -> "s3://bucket/doc_input_keys.json"
    """
    if extracted_json_path.endswith("_extracted.json"):
        base_path = extracted_json_path[:-15]  # Remove "_extracted.json"
        return f"{base_path}_input_keys.json"
    else:
        # Fallback: replace .json with _input_keys.json
        base_path = extracted_json_path.rsplit('.json', 1)[0]
        return f"{base_path}_input_keys.json"

def get_notification_config() -> Dict[str, Any]:
    """Get notification configuration from settings"""
    return {
        "enabled": settings.notifications_enabled,
        "backend_url": settings.notifications_backend_url,
        "api_key": settings.notifications_api_key,
        "api_token": settings.notifications_api_token,
        "timeout_seconds": settings.notifications_timeout_seconds,
        "max_retries": settings.notifications_max_retries,
        "retry_delay_seconds": settings.notifications_retry_delay_seconds,
        "fail_silently": settings.notifications_fail_silently
    }

def get_teams_config() -> Dict[str, Any]:
    """Get MS Teams notification configuration from settings"""
    return {
        "enabled": settings.teams_enabled,
        "webhook_url": settings.teams_webhook_url,
        "timeout_seconds": settings.teams_timeout_seconds,
        "max_retries": settings.teams_max_retries
    }

def get_webhook_config() -> Dict[str, Any]:
    """Get webhook configuration from settings"""
    return {
        "enabled": settings.webhook_enabled,
        "lambda_name": settings.webhook_lambda_name,
        "region": settings.webhook_region
    }


