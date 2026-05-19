"""
Local deployment entrypoint.

This module handles local deployment where:
1. Files are copied from /app/data/input/ -> /tmp/processing/
2. Operations process files in /tmp/processing/
3. Results are copied from /tmp/processing/ -> /app/data/output/
4. Temp files in /tmp/processing/ are deleted (like Lambda ephemeral storage)
"""

import os
import shutil
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

from pdf_autofillr_mapper.configs.file_config import get_file_config
from pdf_autofillr_mapper.configs.local import LocalStorageConfig
from pdf_autofillr_mapper.handlers import operations
from pdf_autofillr_mapper.core.logger import logger


async def handle_local_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle local deployment event.
    
    This is the main entry point for local deployment, analogous to AWS Lambda handler.
    
    Flow:
        1. Load config.ini and .env
        2. Build file paths from patterns
        3. Copy files from source (/app/data/input/) to processing (/tmp/processing/)
        4. Call operations (source-agnostic orchestrator)
        5. Copy results from processing to source (/app/data/output/)
        6. Cleanup temp files
        7. Return result with source paths
    
    Args:
        event: Event dictionary with:
            - operation: "make_embed_file", "fill_pdf", "run_all", etc.
            - user_id: User ID
            - session_id: Session ID
            - pdf_doc_id: PDF document ID
            - investor_type: Optional investor type
            - use_second_mapper: Optional boolean for RAG
    
    Returns:
        Result dictionary with:
            - status: "success" or "error"
            - output_paths: Dictionary of output file paths in source storage
            - metadata: Processing metadata
    
    Example:
        event = {
            "operation": "make_embed_file",
            "user_id": 553,
            "session_id": "086d6670-81e5-47f4-aecb-e4f7c3ba2a83",
            "pdf_doc_id": 990,
            "investor_type": "individual",
            "use_second_mapper": True
        }
        
        result = handle_local_event(event)
        # Returns: {"status": "success", "output_paths": {...}, ...}
    """
    try:
        logger.info(f"Local entrypoint: Processing event {event.get('operation')}")
        
        # 1. Load configuration
        load_dotenv()
        file_config = get_file_config()
        
        # 2. Extract event parameters
        operation = event.get('operation')
        user_id = event['user_id']
        session_id = event['session_id']
        pdf_doc_id = event['pdf_doc_id']
        use_second_mapper = event.get('use_second_mapper', False)
        
        logger.info(f"Processing: user={user_id}, session={session_id}, pdf={pdf_doc_id}")
        
        # 3. Build all file paths
        paths = _build_file_paths(file_config, user_id, session_id, pdf_doc_id)
        logger.debug(f"File paths built: {paths}")
        
        # 3.5. Validate input files exist in source storage
        logger.info("=" * 60)
        logger.info("VALIDATING INPUT FILES")
        logger.info("=" * 60)
        
        input_base = file_config.get('local', 'input_base_path', fallback='data/input')
        logger.info(f"Input directory: {input_base}")
        logger.info(f"Expected naming: {{user_id}}_{{session_id}}_{{pdf_doc_id}}.{{ext}}")
        logger.info(f"Current IDs: user={user_id}, session={session_id}, pdf_doc={pdf_doc_id}")
        
        missing_files = []
        
        # Check input PDF
        if not os.path.exists(paths['source_input_pdf']):
            missing_files.append(("Input PDF", paths['source_input_pdf']))
            logger.error(f"❌ Input PDF NOT FOUND: {paths['source_input_pdf']}")
        else:
            pdf_size = os.path.getsize(paths['source_input_pdf'])
            logger.info(f"✅ Input PDF found: {paths['source_input_pdf']} ({pdf_size:,} bytes)")
        
        # Check input JSON
        if not os.path.exists(paths['source_input_json']):
            missing_files.append(("Input JSON", paths['source_input_json']))
            logger.error(f"❌ Input JSON NOT FOUND: {paths['source_input_json']}")
        else:
            json_size = os.path.getsize(paths['source_input_json'])
            logger.info(f"✅ Input JSON found: {paths['source_input_json']} ({json_size:,} bytes)")
        
        # Check global JSON registry (optional)
        if not os.path.exists(paths['source_registry']):
            logger.warning(f"⚠️  Global JSON registry NOT FOUND: {paths['source_registry']}")
            logger.warning("   (Optional - used as fallback if input JSON is missing)")
        else:
            reg_size = os.path.getsize(paths['source_registry'])
            logger.info(f"✅ Global JSON registry found: {paths['source_registry']} ({reg_size:,} bytes)")
        
        logger.info("=" * 60)
        
        # Raise error if required files are missing
        if missing_files:
            error_msg = "\n" + "=" * 60 + "\n"
            error_msg += "❌ MISSING REQUIRED INPUT FILES\n"
            error_msg += "=" * 60 + "\n\n"
            
            for file_type, file_path in missing_files:
                error_msg += f"  ❌ {file_type}: {file_path}\n"
            
            error_msg += f"\n📝 Please place your files in: {input_base}/\n"
            error_msg += f"\n   Expected file names:\n"
            error_msg += f"   - {user_id}_{session_id}_{pdf_doc_id}.pdf\n"
            error_msg += f"   - {user_id}_{session_id}_{pdf_doc_id}.json\n"
            error_msg += f"\n   Example JSON content:\n"
            error_msg += "   {\n"
            error_msg += '     "firstName": "John",\n'
            error_msg += '     "lastName": "Doe",\n'
            error_msg += '     "email": "john@example.com"\n'
            error_msg += "   }\n"
            error_msg += "\n" + "=" * 60 + "\n"
            
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        logger.info("✅ All required input files validated\n")
        
        # 4. Prepare input files (copy from source to processing)
        _prepare_input_files(paths, file_config)
        
        # 5. Create storage config for operations
        config = _create_storage_config(paths)
        
        # 6. Call orchestrator (source-agnostic!)
        result = await _call_operation(
            operation=operation,
            config=config,
            event=event
        )
        
        # 7. Save results (copy from processing to source)
        output_paths = _save_results(result, paths, file_config, user_id, session_id, pdf_doc_id)
        
        # 8. Cleanup temp files (like Lambda!)
        _cleanup_temp_files(paths['processing_dir'])
        
        # 9. Return result with source paths
        return {
            "status": "success",
            "operation": operation,
            "output_paths": output_paths,
            "metadata": result
        }
        
    except Exception as e:
        logger.error(f"Local entrypoint error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "operation": event.get('operation')
        }


def _build_file_paths(
    file_config,
    user_id: int,
    session_id: str,
    pdf_doc_id: int
) -> Dict[str, str]:
    """Build all file paths needed for processing."""
    
    paths = {}
    
    # Processing directory (Docker local)
    paths['processing_dir'] = file_config.get('local', 'processing_dir', 
                                              fallback='/tmp/processing')
    
    # Ensure processing directory exists
    os.makedirs(paths['processing_dir'], exist_ok=True)
    
    # Source input paths (where files come from)
    paths['source_input_pdf'] = file_config.get_source_input_path(
        'pdf', user_id, session_id, pdf_doc_id
    )
    paths['source_input_json'] = file_config.get_source_input_path(
        'json', user_id, session_id, pdf_doc_id
    )
    paths['source_registry'] = file_config.get_source_input_path(
        'registry', user_id, session_id, pdf_doc_id
    )
    
    # Processing paths (where operations work)
    processing_paths = file_config.get_all_processing_paths(
        user_id, session_id, pdf_doc_id
    )
    paths.update(processing_paths)
    
    # Source output paths (where results go)
    paths['source_output_extracted'] = file_config.get_source_output_path(
        'extracted_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_mapped'] = file_config.get_source_output_path(
        'mapped_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_radio'] = file_config.get_source_output_path(
        'radio_groups_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_embedded'] = file_config.get_source_output_path(
        'embedded_pdf', user_id, session_id, pdf_doc_id
    )
    paths['source_output_filled'] = file_config.get_source_output_path(
        'filled_pdf', user_id, session_id, pdf_doc_id
    )
    
    # Dual mapper output paths (if used)
    paths['source_output_semantic_mapping'] = file_config.get_source_output_path(
        'semantic_mapping_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_headers'] = file_config.get_source_output_path(
        'headers_with_fields_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_final_fields'] = file_config.get_source_output_path(
        'final_form_fields_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_header_file'] = file_config.get_source_output_path(
        'header_file_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_section_file'] = file_config.get_source_output_path(
        'section_file_json', user_id, session_id, pdf_doc_id
    )
    paths['source_output_java_mapping'] = file_config.get_source_output_path(
        'java_mapping', user_id, session_id, pdf_doc_id
    )
    paths['source_output_final_predictions'] = file_config.get_source_output_path(
        'final_predictions', user_id, session_id, pdf_doc_id
    )
    paths['source_output_llm_predictions'] = file_config.get_source_output_path(
        'llm_predictions', user_id, session_id, pdf_doc_id
    )
    paths['source_output_rag_predictions'] = file_config.get_source_output_path(
        'rag_predictions', user_id, session_id, pdf_doc_id
    )
    paths['source_output_cache_registry'] = file_config.get_source_output_path(
        'cache_registry_json', user_id, session_id, pdf_doc_id
    )
    
    return paths


def _prepare_input_files(paths: Dict[str, str], file_config):
    """
    Copy input files from source storage to processing directory.
    
    Like AWS Lambda downloading from S3 to /tmp/
    """
    logger.info("Preparing input files (copy source -> processing)")
    
    # Ensure output directory exists
    output_base = file_config.get('local', 'output_base_path', fallback='/app/data/output')
    os.makedirs(output_base, exist_ok=True)
    
    # Copy input PDF
    if os.path.exists(paths['source_input_pdf']):
        shutil.copy2(paths['source_input_pdf'], paths['processing_input_pdf'])
        logger.info(f"Copied PDF: {paths['source_input_pdf']} -> {paths['processing_input_pdf']}")
    else:
        raise FileNotFoundError(f"Input PDF not found: {paths['source_input_pdf']}")
    
    # Copy input JSON
    if os.path.exists(paths['source_input_json']):
        shutil.copy2(paths['source_input_json'], paths['processing_input_json'])
        logger.info(f"Copied JSON: {paths['source_input_json']} -> {paths['processing_input_json']}")
    else:
        logger.warning(f"Input JSON not found: {paths['source_input_json']}, will use registry")
    
    # Copy registry if exists (optional)
    if os.path.exists(paths['source_registry']):
        registry_dest = os.path.join(paths['processing_dir'], 'pdf_registry.json')
        shutil.copy2(paths['source_registry'], registry_dest)
        logger.info(f"Copied registry: {paths['source_registry']} -> {registry_dest}")
    else:
        logger.info(f"Registry not found: {paths['source_registry']}, will create if needed")


def _create_storage_config(paths: Dict[str, str]) -> LocalStorageConfig:
    """
    Create LocalStorageConfig with processing paths and output destination paths.
    
    Operations work with processing paths (source-agnostic).
    OutputFileHandler uses destination paths to save files.
    """
    config = LocalStorageConfig()
    
    # Set processing directory for temp file operations
    config.processing_dir = paths['processing_dir']
    
    # Set all local paths (in /tmp/processing/ - where operations work)
    config.local_input_pdf = paths['processing_input_pdf']
    config.local_input_json = paths['processing_input_json']
    config.local_extracted_json = paths['extracted_json']
    config.local_mapped_json = paths['mapped_json']
    config.local_radio_json = paths['radio_groups_json']
    config.local_embedded_pdf = paths['embedded_pdf']
    config.local_filled_pdf = paths['filled_pdf']
    
    # Dual mapper paths
    config.local_headers_with_fields = paths.get('headers_with_fields')
    config.local_final_form_fields = paths.get('final_form_fields')
    config.local_header_file = paths.get('header_file')
    config.local_section_file = paths.get('section_file')
    config.local_llm_predictions = paths.get('llm_predictions')
    config.local_rag_predictions = paths.get('rag_predictions')
    config.local_final_predictions = paths.get('final_predictions')
    config.local_java_mapping = paths.get('java_mapping')
    
    # Set destination paths (in ../../data/output/ - where files should be saved)
    # These are used by OutputFileHandler to know where to save files
    config.dest_extracted_json = paths.get('source_output_extracted')
    config.dest_mapped_json = paths.get('source_output_mapped')
    config.dest_radio_json = paths.get('source_output_radio')
    config.dest_embedded_pdf = paths.get('source_output_embedded')
    config.dest_filled_pdf = paths.get('source_output_filled')
    config.dest_semantic_mapping_json = paths.get('source_output_semantic_mapping')
    config.dest_headers_with_fields_json = paths.get('source_output_headers')
    config.dest_final_form_fields_json = paths.get('source_output_final_fields')
    config.dest_header_file_json = paths.get('source_output_header_file')
    config.dest_section_file_json = paths.get('source_output_section_file')
    config.dest_cache_registry = paths.get('source_output_cache_registry')
    config.dest_java_mapping_json = paths.get('source_output_java_mapping')
    config.dest_final_predictions_json = paths.get('source_output_final_predictions')
    config.dest_llm_predictions_json = paths.get('source_output_llm_predictions')
    config.dest_rag_predictions_json = paths.get('source_output_rag_predictions')
    
    return config


async def _call_operation(
    operation: str,
    config: LocalStorageConfig,
    event: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Call the appropriate operation handler.
    
    This is source-agnostic - operations only work with local paths.
    """
    logger.info(f"Calling operation: {operation}")
    
    user_id = event['user_id']
    session_id = event['session_id']
    pdf_doc_id = event['pdf_doc_id']
    
    if operation == "make_embed_file":
        # Build mapping config from config.ini
        from pdf_autofillr_mapper.configs.file_config import get_file_config
        file_config = get_file_config()
        mapping_config = {
            "llm_model": file_config.get('mapping', 'llm_model', fallback='gpt-4o'),
            "llm_temperature": float(file_config.get('mapping', 'llm_temperature', fallback='0.05')),
            "llm_max_tokens": int(file_config.get('mapping', 'llm_max_tokens', fallback='8192')),
            "confidence_threshold": float(file_config.get('mapping', 'confidence_threshold', fallback='0.7')),
            "chunking_strategy": file_config.get('mapping', 'chunking_strategy', fallback='page'),
        }
        
        # Use second mapper: event value overrides config.ini
        use_second_mapper_default = file_config.get('mapping', 'use_second_mapper', fallback='false').lower() == 'true'
        use_second_mapper = event.get('use_second_mapper', use_second_mapper_default)
        
        logger.info(f"🔀 Dual mapper mode: {use_second_mapper} (event={event.get('use_second_mapper')}, config.ini={use_second_mapper_default})")
        
        result = await operations.handle_make_embed_file_operation(
            config=config,
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            investor_type=event.get('investor_type'),
            mapping_config=mapping_config,
            use_second_mapper=use_second_mapper
        )
        
    elif operation == "fill_pdf":
        result = await operations.handle_fill_pdf_operation(
            config=config,
            user_id=user_id,
            session_id=session_id,
            pdf_doc_id=pdf_doc_id
        )
        
    elif operation == "run_all":
        # Build mapping config from config.ini
        from pdf_autofillr_mapper.configs.file_config import get_file_config
        file_config = get_file_config()
        mapping_config = {
            "llm_model": file_config.get('mapping', 'llm_model', fallback='gpt-4o'),
            "llm_temperature": float(file_config.get('mapping', 'llm_temperature', fallback='0.05')),
            "llm_max_tokens": int(file_config.get('mapping', 'llm_max_tokens', fallback='8192')),
            "confidence_threshold": float(file_config.get('mapping', 'confidence_threshold', fallback='0.7')),
            "chunking_strategy": file_config.get('mapping', 'chunking_strategy', fallback='page'),
        }
        
        result = await operations.handle_run_all_operation(
            input_pdf=config.local_input_pdf,
            input_json=config.local_input_json,
            mapping_config=mapping_config,
            user_id=user_id,
            session_id=session_id,
            pdf_doc_id=pdf_doc_id
        )
        
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    logger.info(f"Operation {operation} completed successfully")
    return result


def _save_results(
    result: Dict[str, Any],
    paths: Dict[str, str],
    file_config,
    user_id: int,
    session_id: str,
    pdf_doc_id: int
) -> Dict[str, str]:
    """
    Extract output file paths from operation results.
    
    NOTE: Files are ALREADY saved by operations via OutputFileHandler.
    This function just extracts paths for verification/response.
    
    Returns dictionary of output paths in source storage.
    """
    logger.info("Extracting output paths from operation results...")
    
    output_paths = {}
    
    # Handle make_embed_file operation output
    if 'outputs' in result:
        outputs = result['outputs']
        
        # Map output keys to paths (files already saved by operations)
        if 'extracted_json' in outputs and outputs['extracted_json']:
            output_paths['extracted_json'] = paths['source_output_extracted']
        
        if 'mapping_json' in outputs and outputs['mapping_json']:
            output_paths['mapping_json'] = paths['source_output_mapped']
        
        if 'radio_groups_json' in outputs and outputs['radio_groups_json']:
            output_paths['radio_groups_json'] = paths['source_output_radio']
        
        if 'embedded_pdf' in outputs and outputs['embedded_pdf']:
            output_paths['embedded_pdf'] = paths['source_output_embedded']
        
        if 'semantic_mapping_json' in outputs and outputs['semantic_mapping_json']:
            output_paths['semantic_mapping_json'] = paths['source_output_semantic_mapping']
        
        if 'headers_with_fields' in outputs and outputs['headers_with_fields']:
            output_paths['headers_with_fields'] = paths['source_output_headers']
        
        if 'final_form_fields' in outputs and outputs['final_form_fields']:
            output_paths['final_form_fields'] = paths['source_output_final_fields']
    
    # Legacy support: Handle old-style embedded_pdf_path key
    elif 'embedded_pdf_path' in result:
        output_paths['embedded_pdf'] = paths['source_output_embedded']
    
    # Legacy support: Handle fill operation
    if 'filled_pdf_path' in result:
        output_paths['filled_pdf'] = paths['source_output_filled']
    
    logger.info(f"✅ Extracted {len(output_paths)} output paths (files already saved by operations)")
    return output_paths


def _cleanup_temp_files(processing_dir: str):
    """
    Delete all files in processing directory.
    
    Like Lambda ephemeral /tmp/ storage cleanup.
    """
    logger.info(f"Cleaning up temp files in: {processing_dir}")
    
    try:
        if os.path.exists(processing_dir):
            for item in os.listdir(processing_dir):
                item_path = os.path.join(processing_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    logger.debug(f"Deleted: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.debug(f"Deleted directory: {item_path}")
            
            logger.info("Cleanup completed")
    except Exception as e:
        logger.warning(f"Cleanup warning: {e}")
        # Don't fail the operation if cleanup fails
