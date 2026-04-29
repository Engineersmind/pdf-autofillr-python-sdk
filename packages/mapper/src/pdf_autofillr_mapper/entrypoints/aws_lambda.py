"""
AWS Lambda wrapper - handles AWS-specific concerns only.

This is a THIN wrapper that:
1. Parses AWS Lambda events
2. Validates authentication
3. Calls source-agnostic handlers from pdf_autofillr_mapper.handlers
4. Returns AWS Lambda response format

The actual business logic is in src/handlers/operations.py
"""

import json
import logging
import asyncio
import time
from typing import Optional

from pdf_autofillr_mapper.core.logger import setup_logging
from pdf_autofillr_mapper.core.config import settings
from pdf_autofillr_mapper.clients.api_client import APIClient
from pdf_autofillr_mapper.utils.data_combiner import combine_user_and_session_data

# Import source-agnostic handlers
from pdf_autofillr_mapper.handlers.operations import (
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

# Import notification system
try:
    from adapter_src.notifier import create_pipeline_notifier
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    create_pipeline_notifier = None

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def get_pipeline_notifier():
    """Create pipeline notifier if available."""
    if not NOTIFICATIONS_AVAILABLE:
        return None
    
    try:
        notifier = create_pipeline_notifier()
        if notifier:
            logger.info("Pipeline notifications ENABLED")
        else:
            logger.info("Pipeline notifications DISABLED")
        return notifier
    except Exception as e:
        logger.error(f"Failed to create notifier: {e}")
        return None


async def async_lambda_handler(event, context):
    """
    AWS Lambda async handler - parses AWS events and calls source-agnostic handlers.
    
    This handler is AWS-specific. It handles:
    - AWS Lambda event parsing
    - Authentication
    - API calls to fetch document URLs
    - Response formatting for AWS Lambda
    
    The actual processing logic is in src/handlers/operations.py (source-agnostic).
    """
    request_start_time = time.time()
    notifier = None
    
    try:
        logger.info(f"Raw AWS Lambda event received: {event}")
        
        # Parse AWS Lambda Function URL format
        original_headers = {}
        if 'body' in event and isinstance(event.get('body'), str):
            try:
                original_headers = event.get('headers', {})
                parsed_body = json.loads(event['body'])
                logger.info(f"Parsed Function URL body: {parsed_body}")
                event = parsed_body
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON body: {event.get('body')}")
                raise ValueError(f"Invalid JSON in request body: {str(e)}")
        else:
            original_headers = event.get('headers', {})
        
        # Validate API token (AWS-specific security)
        expected_token = getattr(settings, 'mapper_lambda_api_token', None)
        if expected_token:
            auth_header = None
            for key, value in original_headers.items():
                if key.lower() == 'x-api-key':
                    auth_header = value
                    break
            
            if not auth_header:
                logger.warning("Missing X-API-Key header")
                return {
                    'statusCode': 401,
                    'body': json.dumps({
                        'error': 'Unauthorized',
                        'message': 'Missing X-API-Key header'
                    })
                }
            
            if auth_header != expected_token:
                logger.warning(f"Invalid API token")
                return {
                    'statusCode': 403,
                    'body': json.dumps({
                        'error': 'Forbidden',
                        'message': 'Invalid API token'
                    })
                }
            
            logger.info("API token validated")
        
        # Create notification system
        notifier = get_pipeline_notifier()

        # Parse operation
        operation = event.get('operation')
        if not operation:
            raise ValueError("Missing required parameter: operation")

        logger.info(f"Operation: {operation}")

        # Initialize pipeline tracking for notifications
        if notifier:
            notifier.start_pipeline(
                pipeline_id=f"{operation}_{int(time.time())}",
                metadata={
                    "user_id": event.get('user_id'),
                    "session_id": event.get('session_id'),
                    "pdf_doc_id": event.get('pdf_doc_id')
                }
            )
            logger.info(f"Pipeline tracking initialized for {operation}")

        # Route to appropriate handler
        result = await route_operation(event, operation, notifier)
        
        # Calculate total time
        request_end_time = time.time()
        total_time = round(request_end_time - request_start_time, 2)
        
        # Return AWS Lambda response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing completed successfully',
                'operation': operation,
                'result': result,
                'request_processing_time_seconds': total_time
            }, indent=2)
        }
    
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': 'Validation Error',
                'message': str(e),
                'operation': event.get('operation', 'unknown')
            })
        }
    
    except NotImplementedError as e:
        logger.warning(f"Operation not yet refactored: {str(e)}")
        return {
            'statusCode': 501,
            'body': json.dumps({
                'error': 'Not Implemented',
                'message': str(e),
                'operation': event.get('operation', 'unknown')
            })
        }
    
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Processing failed'
            })
        }
    
    finally:
        if notifier:
            try:
                await notifier.close()
                logger.debug("Notifier closed")
            except Exception as e:
                logger.warning(f"Error closing notifier: {e}")


def _build_aws_config(env: str, developer_id, user_id, session_id, pdf_doc_id,
                      pdf_s3_url: str = None):
    """
    Build AWSStorageConfig with all S3 paths and local temp paths pre-set.
    Mirrors local.py's _create_storage_config() pattern so operations never
    need to fall back to config.ini.

    pdf_s3_url: actual S3 URL of the input PDF, fetched from the backend API
                via APIClient.get_document_s3_url(pdf_doc_id).  When provided
                this is used as the download source; the mapper stores its own
                copy at mapper/{pid}/{pid}_input.pdf in the pipeline bucket.
    """
    import os
    from pdf_autofillr_mapper.configs.aws import AWSStorageConfig
    from pdf_autofillr_mapper.storage.paths.resolver import PathResolver

    config = AWSStorageConfig(env=env, developer_id=developer_id)
    s3_paths = config.get_complete_file_config(
        user_id=user_id,
        session_id=session_id,
        pdf_doc_id=pdf_doc_id,
    )

    # Per-job processing directory inside Lambda ephemeral storage
    proc_base = os.environ.get('MAPPER_PROCESSING_PATH', '/tmp/processing')
    proc_dir = os.path.join(proc_base, f"{user_id}_{session_id}_{pdf_doc_id}")
    os.makedirs(proc_dir, exist_ok=True)

    # Local temp paths — use PathResolver so filenames match the prod naming convention
    # e.g. {pid}_input.pdf, {pid}_extracted.json, {pid}_mapping.json, {pid}_embedded.pdf, etc.
    pr = PathResolver(config._sc)
    local = pr.local_paths(str(user_id), str(session_id), str(pdf_doc_id), proc_dir)

    # S3 source paths (InputFileHandler reads config.s3_{file_type})
    # pdf_s3_url is the actual URL from the backend DB (fetched via APIClient).
    # s3_paths['input_pdf'] is the mapper-folder copy: mapper/{pid}/{pid}_input.pdf
    config.s3_input_pdf   = pdf_s3_url if pdf_s3_url else s3_paths['input_pdf']
    config.s3_input_json  = s3_paths['input_json']

    # Download form_keys_flat.json once per job — semantic_mapper expects a local path
    global_json_s3 = s3_paths['global_json']
    local_global_json = os.path.join(proc_dir, 'form_keys_flat.json')
    if not os.path.exists(local_global_json):
        from pdf_autofillr_mapper.clients.s3_client import S3Client
        S3Client().download_file_from_s3(global_json_s3, local_global_json)
        logger.info(f"Downloaded global JSON: {global_json_s3} → {local_global_json}")
    config.s3_global_json  = global_json_s3
    config.local_global_json = local_global_json

    # Local temp paths (written/read by operations in /tmp/processing/)
    config.local_input_pdf           = local['processing_input_pdf']
    config.local_input_json          = local['processing_input_json']
    config.local_extracted_json      = local['extracted_json']
    config.local_mapped_json         = local['mapped_json']
    config.local_radio_json          = local['radio_groups_json']
    config.local_embedded_pdf        = local['embedded_pdf']
    config.local_filled_pdf          = local['filled_pdf']
    config.local_headers_with_fields = local['headers_with_fields']
    config.local_final_form_fields   = local['final_form_fields']
    config.local_header_file         = local['header_file']
    config.local_section_file        = local['section_file']
    config.local_java_mapping        = local['java_mapping']
    config.local_llm_predictions     = local['llm_predictions']
    config.local_rag_predictions     = local['rag_predictions']
    config.local_final_predictions   = local['final_predictions']

    # S3 destination paths (OutputFileHandler reads config.dest_{file_type})
    config.dest_extracted_json           = s3_paths['extracted_json']
    config.dest_mapped_json              = s3_paths['mapped_json']
    config.dest_radio_json               = s3_paths['radio_groups_json']
    config.dest_embedded_pdf             = s3_paths['embedded_pdf']
    # s3_ mirrors so InputFileHandler can find download source for each file
    config.s3_extracted_json  = s3_paths['extracted_json']
    config.s3_mapped_json     = s3_paths['mapped_json']
    config.s3_radio_json      = s3_paths['radio_groups_json']
    config.s3_embedded_pdf    = s3_paths['embedded_pdf']
    config.dest_filled_pdf               = s3_paths['filled_pdf']
    config.dest_headers_with_fields_json = s3_paths['headers_with_fields']
    config.dest_final_form_fields_json   = s3_paths['final_form_fields']
    config.dest_header_file_json         = s3_paths['header_file']
    config.dest_section_file_json        = s3_paths['section_file']
    config.dest_java_mapping_json        = s3_paths['java_mapping']
    config.dest_rag_predictions_json     = s3_paths['rag_predictions']
    config.dest_llm_predictions_json     = s3_paths['llm_predictions']
    config.dest_final_predictions_json   = s3_paths['final_predictions']
    # Cache registry — local path for hash_cache.py (local reads/writes), S3 for persistence.
    # OutputFileHandler looks for config.dest_cache_registry_json (dest_{file_type}).
    cache_registry_s3    = s3_paths['cache_registry']
    local_cache_registry = os.path.join('/tmp/processing', 'hash_registry.json')
    # Download existing registry from S3 so check_hash_cache can find previous entries
    try:
        from pdf_autofillr_mapper.clients.s3_client import S3Client
        _s3 = S3Client()
        if _s3.object_exists(cache_registry_s3):
            os.makedirs(os.path.dirname(local_cache_registry), exist_ok=True)
            _s3.download_file_from_s3(cache_registry_s3, local_cache_registry)
            logger.info(f"Downloaded cache registry: {cache_registry_s3} → {local_cache_registry}")
        else:
            logger.info("Cache registry not in S3 yet — will be created on first save")
    except Exception as _e:
        logger.warning(f"Could not download cache registry (will start fresh): {_e}")

    config.dest_cache_registry           = cache_registry_s3
    config.dest_cache_registry_json      = cache_registry_s3   # name OutputFileHandler expects
    config.local_cache_registry          = local_cache_registry

    # Clean stale /tmp paths from registry before operations reads it.
    # In Lambda, any /tmp paths from a previous container invocation are always stale.
    if os.path.exists(local_cache_registry):
        try:
            _stale_cleaned = False
            with open(local_cache_registry, 'r') as _rf:
                _registry = json.load(_rf)
            for _entry in _registry.get('entries', {}).values():
                _refs = _entry.get('reference_files', {})
                for _key in list(_refs.keys()):
                    if isinstance(_refs[_key], str) and _refs[_key].startswith('/tmp'):
                        logger.info(f"Removing stale /tmp path from registry: {_key}={_refs[_key]}")
                        _refs[_key] = None
                        _stale_cleaned = True
            if _stale_cleaned:
                with open(local_cache_registry, 'w') as _wf:
                    json.dump(_registry, _wf, indent=2)
                logger.info("Cleaned stale /tmp paths from cache registry")
        except Exception as _ce:
            logger.warning(f"Could not clean stale registry paths: {_ce}")

    return config


async def route_operation(event: dict, operation: str, notifier):
    """
    Route operation to appropriate handler.
    
    This function handles AWS-specific logic like fetching S3 URLs from backend API,
    then calls the source-agnostic handlers.
    """
    
    if operation == 'extract':
        # Validate and parse
        input_file = event.get('input_file')
        if not input_file:
            raise ValueError("Missing required parameter: input_file")
        
        # Call source-agnostic handler
        return await handle_extract_operation(
            input_file=input_file,
            user_id=event.get('user_id'),
            session_id=event.get('session_id'),
            notifier=notifier,
            pdf_doc_id=event.get('pdf_doc_id'),
            input_json_path=event.get('input_json_path'),
            mapping_config=event.get('mapping_config')
        )
    
    elif operation == 'map':
        # Validate and parse
        extracted_json = event.get('extracted_json')
        input_json = event.get('input_json')
        if not extracted_json:
            raise ValueError("Missing required parameter: extracted_json")
        if not input_json:
            raise ValueError("Missing required parameter: input_json")
        
        # Call source-agnostic handler
        return await handle_map_operation(
            extracted_json_path=extracted_json,
            input_json_path=input_json,
            mapping_config=event.get('mapping_config', {}),
            user_id=event.get('user_id'),
            session_id=event.get('session_id'),
            notifier=notifier,
            pdf_doc_id=event.get('pdf_doc_id'),
            investor_type=event.get('investor_type')
        )
    
    elif operation == 'run_all':
        # Get parameters from event
        input_pdf = event.get('input_pdf')
        input_json = event.get('input_json')
        user_id = event.get('user_id')
        pdf_doc_id = event.get('pdf_doc_id')
        input_json_doc_id = event.get('input_json_doc_id')
        session_id = event.get('session_id')
        use_profile_info = event.get('use_profile_info', True)
        
        # AWS-specific: Fetch S3 URLs from backend API if session_id or doc_ids provided
        if session_id is not None:
            # Session workflow
            if not user_id:
                raise ValueError("Missing required parameter: user_id (required with session_id)")
            if not pdf_doc_id:
                raise ValueError("Missing required parameter: pdf_doc_id")
            
            logger.info(f"Session-based workflow - user_id: {user_id}, session_id: {session_id}, pdf_doc_id: {pdf_doc_id}")
            logger.info(f"use_profile_info: {use_profile_info}")
            
            async with APIClient() as api_client:
                input_pdf = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
                logger.info(f"PDF S3 URL: {input_pdf}")
                
                if not input_pdf.lower().endswith('.pdf'):
                    raise ValueError(f"pdf_doc_id must be a PDF file, got: {input_pdf}")
            
            # Combine user profile and session data
            logger.info("Combining user profile and session data...")
            input_json = await combine_user_and_session_data(
                user_id=user_id,
                session_id=session_id,
                use_profile_info=use_profile_info
            )
            logger.info(f"Combined JSON created: {input_json}")
        
        elif pdf_doc_id or input_json_doc_id:
            # Doc ID workflow
            if not pdf_doc_id:
                raise ValueError("Missing required parameter: pdf_doc_id")
            if not input_json_doc_id:
                raise ValueError("Missing required parameter: input_json_doc_id")
            
            logger.info(f"Doc-based workflow - PDF doc_id: {pdf_doc_id}, JSON doc_id: {input_json_doc_id}")
            
            async with APIClient() as api_client:
                input_pdf = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
                logger.info(f"PDF S3 URL: {input_pdf}")
                
                input_json = await api_client.get_document_s3_url(doc_id=input_json_doc_id)
                logger.info(f"JSON S3 URL: {input_json}")
                
                if not input_pdf.lower().endswith('.pdf'):
                    raise ValueError(f"pdf_doc_id must be a PDF file, got: {input_pdf}")
                if not input_json.lower().endswith('.json'):
                    raise ValueError(f"input_json_doc_id must be a JSON file, got: {input_json}")
        
        else:
            # Legacy: direct S3 paths provided
            if not input_pdf:
                raise ValueError("Missing required parameter: input_pdf")
            if not input_json:
                raise ValueError("Missing required parameter: input_json")
        
        # Call source-agnostic handler
        return await handle_run_all_operation(
            input_pdf=input_pdf,
            input_json=input_json,
            mapping_config=event.get('mapping_config', {}),
            user_id=user_id,
            session_id=session_id,
            notifier=notifier,
            pdf_doc_id=pdf_doc_id,
            input_json_doc_id=input_json_doc_id
        )
    
    # Other operations - now fully implemented
    elif operation == 'embed':
        # Validate parameters
        original_pdf = event.get('original_pdf')
        extracted_json = event.get('extracted_json')
        mapping_json = event.get('mapping_json')
        radio_groups = event.get('radio_groups')
        
        if not all([original_pdf, extracted_json, mapping_json, radio_groups]):
            raise ValueError("Missing required parameters for embed operation")
        
        return await handle_embed_operation(
            original_pdf_path=original_pdf,
            extracted_json_path=extracted_json,
            mapping_json_path=mapping_json,
            radio_groups_path=radio_groups,
            user_id=event.get('user_id'),
            session_id=event.get('session_id'),
            notifier=notifier,
            pdf_doc_id=event.get('pdf_doc_id')
        )
    
    elif operation == 'fill':
        # Validate parameters
        embedded_pdf = event.get('embedded_pdf')
        input_json = event.get('input_json')
        
        if not embedded_pdf or not input_json:
            raise ValueError("Missing required parameters for fill operation")
        
        return await handle_fill_operation(
            embedded_pdf_path=embedded_pdf,
            input_json_path=input_json,
            user_id=event.get('user_id'),
            session_id=event.get('session_id'),
            notifier=notifier,
            pdf_doc_id=event.get('pdf_doc_id'),
            input_json_doc_id=event.get('input_json_doc_id')
        )
    
    elif operation == 'refresh':
        # Validate parameters
        input_pdf = event.get('input_pdf')
        if not input_pdf:
            raise ValueError("Missing required parameter: input_pdf")
        
        return await handle_refresh_operation(
            input_pdf=input_pdf,
            user_id=event.get('user_id'),
            session_id=event.get('session_id'),
            notifier=notifier
        )
    
    elif operation == 'make_embed_file':
        user_id      = event.get('user_id')
        pdf_doc_id   = event.get('pdf_doc_id')
        session_id   = event.get('session_id')
        env          = event.get('env')
        developer_id = event.get('developer_id')

        if user_id is None:
            raise ValueError("Missing required parameter: user_id")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id")
        if session_id is None:
            raise ValueError("Missing required parameter: session_id")
        if env is None:
            raise ValueError("Missing required parameter: env")

        # Fetch the actual S3 URL of the PDF from the backend API (same as run_all)
        async with APIClient() as api_client:
            pdf_s3_url = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
            logger.info(f"PDF S3 URL from API: {pdf_s3_url}")
            if not pdf_s3_url.lower().endswith('.pdf'):
                raise ValueError(f"pdf_doc_id must reference a PDF file, got: {pdf_s3_url}")

        config = _build_aws_config(env, developer_id, user_id, session_id, pdf_doc_id,
                                   pdf_s3_url=pdf_s3_url)
        logger.info(f"AWS config built for make_embed_file: s3_input_pdf={config.s3_input_pdf}")

        return await handle_make_embed_file_operation(
            config=config,
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            env=env,
            developer_id=developer_id,
            investor_type=event.get('investor_type', 'individual'),
            use_second_mapper=event.get('use_second_mapper', False),
            notifier=notifier,
        )
    
    elif operation == 'make_form_fields_data_points':
        # Validate parameters - uses user_id + pdf_doc_id (fetches S3 URL internally)
        user_id = event.get('user_id')
        pdf_doc_id = event.get('pdf_doc_id')
        session_id = event.get('session_id')
        
        if user_id is None:
            raise ValueError("Missing required parameter: user_id for make_form_fields_data_points operation")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id for make_form_fields_data_points operation")
        
        # Create config object
        from pdf_autofillr_mapper.configs.aws import AWSStorageConfig
        from pdf_autofillr_mapper.utils.storage_helper import download_from_source
        
        config = AWSStorageConfig()
        
        # Fetch S3 URL from backend API
        async with APIClient() as api_client:
            pdf_s3_url = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
            logger.info(f"PDF S3 URL: {pdf_s3_url}")
            
            if not pdf_s3_url.lower().endswith('.pdf'):
                raise ValueError(f"pdf_doc_id must be a PDF file, got: {pdf_s3_url}")
        
        # Download PDF to /tmp/ and set on config
        local_pdf_path = f"/tmp/form_{pdf_doc_id}.pdf"
        download_from_source(pdf_s3_url, local_pdf_path)
        config.local_input_pdf = local_pdf_path
        logger.info(f"Downloaded PDF to: {local_pdf_path}")
        
        return await handle_make_form_fields_data_points(
            config=config,
            user_id=user_id,
            session_id=session_id,
            pdf_doc_id=pdf_doc_id,
            notifier=notifier
        )
    
    elif operation == 'fill_pdf':
        user_id      = event.get('user_id')
        pdf_doc_id   = event.get('pdf_doc_id')
        session_id   = event.get('session_id')
        env          = event.get('env')
        developer_id = event.get('developer_id')

        if user_id is None:
            raise ValueError("Missing required parameter: user_id")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id")
        if session_id is None:
            raise ValueError("Missing required parameter: session_id")
        if env is None:
            raise ValueError("Missing required parameter: env")

        config = _build_aws_config(env, developer_id, user_id, session_id, pdf_doc_id)
        logger.info(f"AWS config built for fill_pdf: proc_dir={config.local_embedded_pdf}")

        return await handle_fill_pdf_operation(
            config=config,
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            env=env,
            developer_id=developer_id,
            notifier=notifier,
        )
    
    elif operation == 'check_embed_file':
        user_id      = event.get('user_id')
        pdf_doc_id   = event.get('pdf_doc_id')
        session_id   = event.get('session_id')
        env          = event.get('env')
        developer_id = event.get('developer_id')

        if user_id is None:
            raise ValueError("Missing required parameter: user_id")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id")
        if session_id is None:
            raise ValueError("Missing required parameter: session_id")
        if env is None:
            raise ValueError("Missing required parameter: env")

        config = _build_aws_config(env, developer_id, user_id, session_id, pdf_doc_id)

        return await handle_check_embed_file_operation(
            config=config,
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            env=env,
            developer_id=developer_id,
        )
    
    else:
        raise ValueError(f"Invalid operation: {operation}")


def lambda_handler(event, context):
    """
    AWS Lambda entry point - synchronous wrapper for async handler.
    
    This is the function that AWS Lambda calls.
    """
    logger.info("AWS Lambda invocation")
    
    # Create event loop for this invocation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(async_lambda_handler(event, context))
    finally:
        loop.close()
