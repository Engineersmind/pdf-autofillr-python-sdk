"""
Shared utilities for entrypoint configuration and path building.

This module provides reusable functions for all entrypoints (local, AWS Lambda, HTTP server, etc.)
to avoid code duplication in path building and storage config creation.
"""

import os
import shutil
from typing import Any, Optional

from pdf_autofillr_mapper.core.logger import logger

# ── New clean API ────────────────────────────────────────────────────────────


def create_job_context(storage_config, user_id, session_id, pdf_doc_id):
    """
    Build a JobContext for one processing job.

    Args:
        storage_config:  StorageConfig instance (reads MAPPER_* env vars)
        user_id:         User ID
        session_id:      Session ID
        pdf_doc_id:      PDF document ID

    Returns:
        JobContext ready to pass to operations.handle_*()

    Example:
        from pdf_autofillr_mapper.storage.storage_config import get_storage_config
        ctx = create_job_context(get_storage_config(), "1", "1", "100")
        result = await operations.handle_make_embed_file_operation(config=ctx, ...)
    """
    from pdf_autofillr_mapper.storage.job_context import JobContext

    return JobContext(storage_config, user_id, session_id, pdf_doc_id)


# ── Legacy API (kept for backward compatibility) ─────────────────────────────


def build_all_file_paths(
    file_config,
    user_id: int,
    session_id: str,
    pdf_doc_id: int,
    processing_dir: Optional[str] = None,
) -> dict[str, str]:
    """
    Build all file paths needed for processing.

    This centralizes path building logic used by all entrypoints.

    Args:
        file_config: (legacy) FileConfig instance for path generation
        user_id: User ID
        session_id: Session ID
        pdf_doc_id: PDF document ID
        processing_dir: Optional override for processing directory

    Returns:
        Dictionary with all file paths:
        - processing_dir
        - source_input_* (pdf, json, registry)
        - processing_* (all temp files)
        - source_output_* (all output files)
    """
    paths = {}

    # Processing directory (Docker local / Lambda temp)
    if processing_dir is None:
        processing_dir = file_config.get(
            "local", "processing_dir", fallback="/tmp/processing"
        )
    paths["processing_dir"] = processing_dir

    # Ensure processing directory exists
    os.makedirs(paths["processing_dir"], exist_ok=True)

    # ========================================
    # SOURCE INPUT PATHS (where files come from)
    # ========================================
    paths["source_input_pdf"] = file_config.get_source_input_path(
        "pdf", user_id, session_id, pdf_doc_id
    )
    # Global JSON schema (keys only) — used by map phase
    paths["source_global_json"] = file_config.get_source_input_path(
        "global_json", user_id, session_id, pdf_doc_id
    )
    # Per-user input JSON (actual values) — used by fill phase
    paths["source_input_json"] = file_config.get_source_input_path(
        "json", user_id, session_id, pdf_doc_id
    )
    paths["source_registry"] = file_config.get_source_input_path(
        "registry", user_id, session_id, pdf_doc_id
    )

    # ========================================
    # PROCESSING PATHS (where operations work - /tmp/processing/)
    # ========================================
    processing_paths = file_config.get_all_processing_paths(
        user_id, session_id, pdf_doc_id
    )
    paths.update(processing_paths)

    # ========================================
    # SOURCE OUTPUT PATHS (where results go - source storage)
    # ========================================

    # Core output files (extract, map, embed, fill)
    paths["source_output_extracted"] = file_config.get_source_output_path(
        "extracted_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_mapped"] = file_config.get_source_output_path(
        "mapped_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_radio"] = file_config.get_source_output_path(
        "radio_groups_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_embedded"] = file_config.get_source_output_path(
        "embedded_pdf", user_id, session_id, pdf_doc_id
    )
    paths["source_output_filled"] = file_config.get_source_output_path(
        "filled_pdf", user_id, session_id, pdf_doc_id
    )

    # Dual mapper output paths (semantic + RAG mapper)
    paths["source_output_semantic_mapping"] = file_config.get_source_output_path(
        "semantic_mapping_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_headers"] = file_config.get_source_output_path(
        "headers_with_fields_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_final_fields"] = file_config.get_source_output_path(
        "final_form_fields_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_header_file"] = file_config.get_source_output_path(
        "header_file_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_section_file"] = file_config.get_source_output_path(
        "section_file_json", user_id, session_id, pdf_doc_id
    )
    paths["source_output_java_mapping"] = file_config.get_source_output_path(
        "java_mapping", user_id, session_id, pdf_doc_id
    )
    paths["source_output_final_predictions"] = file_config.get_source_output_path(
        "final_predictions", user_id, session_id, pdf_doc_id
    )
    paths["source_output_llm_predictions"] = file_config.get_source_output_path(
        "llm_predictions", user_id, session_id, pdf_doc_id
    )
    paths["source_output_rag_predictions"] = file_config.get_source_output_path(
        "rag_predictions", user_id, session_id, pdf_doc_id
    )

    # Cache registry — constant shared file, read directly from config.ini
    # NOT a per-user/session output path; always lives at settings.cache_registry_path
    from pdf_autofillr_mapper.core.config import settings

    paths["source_output_cache_registry"] = (
        settings.cache_registry_path
        or os.path.join(
            file_config.get(
                file_config.get_source_type(),
                "output_base_path",
                fallback="/app/data/output",
            ),
            "cache",
            "hash_registry.json",
        )
    )

    return paths


def create_storage_config_from_paths(
    paths: dict[str, str], source_type: str = "local"
) -> Any:
    """
    Create a storage config object from file paths.

    This sets up the config that operations.py expects, with all paths pre-configured.

    Args:
        paths: Dictionary from build_all_file_paths()
        source_type: Storage type ('local', 'aws', 'azure', 'gcp')

    Returns:
        Storage config object (LocalStorageConfig, AWSStorageConfig, etc.)
    """
    if source_type == "local":
        from pdf_autofillr_mapper.configs.local import LocalStorageConfig

        config = LocalStorageConfig()
    elif source_type == "aws":
        from pdf_autofillr_mapper.configs.aws import AWSStorageConfig

        config = AWSStorageConfig()
    elif source_type == "azure":
        from pdf_autofillr_mapper.configs.azure import AzureStorageConfig

        config = AzureStorageConfig()
    elif source_type == "gcp":
        from pdf_autofillr_mapper.configs.gcp import GCPStorageConfig

        config = GCPStorageConfig()
    else:
        raise ValueError(f"Unknown source_type: {source_type}")

    # Set source type
    config.source_type = source_type

    # ========================================
    # INPUT PATHS (from source storage)
    # ========================================
    config.source_input_pdf = paths.get("source_input_pdf")
    config.source_global_json = paths.get("source_global_json")  # keys-only schema
    config.source_input_json = paths.get("source_input_json")  # per-user data
    config.local_input_pdf = paths.get("source_input_pdf")
    config.local_global_json = paths.get("source_global_json")  # schema → map phase
    config.local_input_json = paths.get("source_input_json")  # user data → fill phase

    # For cloud storage, set S3/Azure/GCS paths
    if source_type == "aws":
        config.s3_input_pdf = paths.get("source_input_pdf")
        config.s3_global_json = paths.get("source_global_json")
        config.s3_input_json = paths.get("source_input_json")

    # ========================================
    # PROCESSING PATHS (temp files in /tmp/processing/)
    # ========================================
    config.local_input_pdf = paths.get(
        "processing_input_pdf"
    )  # override with processing path
    config.local_global_json = paths.get("processing_global_json")  # schema → map phase
    config.local_input_json = paths.get(
        "processing_input_json"
    )  # user data → fill phase
    config.local_extracted_json = paths.get("extracted_json")
    config.local_mapped_json = paths.get("mapped_json")
    config.local_radio_json = paths.get("radio_groups_json")
    config.local_embedded_pdf = paths.get("embedded_pdf")
    config.local_filled_pdf = paths.get("filled_pdf")

    # Dual mapper processing paths
    config.local_semantic_mapping = paths.get("semantic_mapping")
    config.local_headers_with_fields = paths.get("headers_with_fields")
    config.local_final_form_fields = paths.get("final_form_fields")
    config.local_header_file = paths.get("header_file")
    config.local_section_file = paths.get("section_file")
    config.local_java_mapping = paths.get("java_mapping")
    config.local_final_predictions = paths.get("final_predictions")
    config.local_llm_predictions = paths.get("llm_predictions")
    config.local_rag_predictions = paths.get("rag_predictions")

    # Cache registry — constant shared file from config.ini, not a per-request path
    config.local_cache_registry = paths.get("source_output_cache_registry")

    # ========================================
    # OUTPUT DESTINATION PATHS (where to save results)
    # ========================================
    config.dest_extracted_json = paths.get("source_output_extracted")
    config.dest_mapped_json = paths.get("source_output_mapped")
    config.dest_radio_json = paths.get("source_output_radio")
    config.dest_embedded_pdf = paths.get("source_output_embedded")
    config.dest_filled_pdf = paths.get("source_output_filled")
    config.dest_semantic_mapping = paths.get("source_output_semantic_mapping")
    config.dest_headers_with_fields = paths.get("source_output_headers")
    config.dest_final_form_fields = paths.get("source_output_final_fields")
    config.dest_header_file = paths.get("source_output_header_file")
    config.dest_section_file = paths.get("source_output_section_file")
    config.dest_cache_registry = paths.get("source_output_cache_registry")
    config.dest_java_mapping = paths.get("source_output_java_mapping")
    config.dest_final_predictions = paths.get("source_output_final_predictions")
    config.dest_llm_predictions = paths.get("source_output_llm_predictions")
    config.dest_rag_predictions = paths.get("source_output_rag_predictions")

    return config


def prepare_input_files(paths: dict[str, str], file_config) -> None:
    """
    Copy input files from source storage to processing directory.

    Args:
        paths: Dictionary from build_all_file_paths()
        file_config: FileConfig instance
    """
    # Copy input PDF
    if os.path.exists(paths["source_input_pdf"]):
        shutil.copy2(paths["source_input_pdf"], paths["processing_input_pdf"])
        logger.info(
            f"Copied input PDF: {paths['source_input_pdf']} → {paths['processing_input_pdf']}"
        )
    else:
        logger.warning(f"Input PDF not found: {paths['source_input_pdf']}")

    # Copy global JSON schema (keys only — used by map phase)
    if paths.get("source_global_json") and os.path.exists(paths["source_global_json"]):
        shutil.copy2(paths["source_global_json"], paths["processing_global_json"])
        logger.info(
            f"Copied global JSON (schema): {paths['source_global_json']} → {paths['processing_global_json']}"
        )
    else:
        logger.warning(
            f"Global JSON schema not found: {paths.get('source_global_json')}"
        )

    # Copy per-user input JSON (actual values — used by fill phase)
    if paths.get("source_input_json") and os.path.exists(paths["source_input_json"]):
        shutil.copy2(paths["source_input_json"], paths["processing_input_json"])
        logger.info(
            f"Copied input JSON (user data): {paths['source_input_json']} → {paths['processing_input_json']}"
        )
    else:
        logger.warning(f"Input JSON not found: {paths.get('source_input_json')}")


def cleanup_processing_directory(processing_dir: str) -> None:
    """
    Clean up temporary processing directory.

    Args:
        processing_dir: Path to processing directory to clean
    """
    if os.path.exists(processing_dir):
        try:
            shutil.rmtree(processing_dir)
            logger.info(f"Cleaned up processing directory: {processing_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup processing directory: {e}")


def validate_input_files(paths: dict[str, str]) -> None:
    """
    Validate that all required input files exist.

    Args:
        paths: Dictionary from build_all_file_paths()

    Raises:
        FileNotFoundError: If required input file is missing
    """
    required_files = {
        "source_input_pdf": "Input PDF file",
        "source_input_json": "Input JSON file",
    }

    for path_key, description in required_files.items():
        path = paths.get(path_key)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"{description} not found: {path}")

    logger.info("All required input files validated")


def extract_event_params(event: dict[str, Any]) -> tuple:
    """
    Extract common parameters from event dictionary.

    Args:
        event: Event dictionary from HTTP request or Lambda

    Returns:
        Tuple of (operation, user_id, session_id, pdf_doc_id)
    """
    operation = event.get("operation", "make_embed_file")
    user_id = event.get("user_id")
    session_id = event.get("session_id")
    pdf_doc_id = event.get("pdf_doc_id")

    # Validate required parameters
    if not user_id:
        raise ValueError("user_id is required")
    if not pdf_doc_id:
        raise ValueError("pdf_doc_id is required")
    if not session_id:
        raise ValueError("session_id is required")

    return operation, user_id, session_id, pdf_doc_id
