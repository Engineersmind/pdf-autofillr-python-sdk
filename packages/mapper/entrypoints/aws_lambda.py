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
        # Validate parameters - uses user_id + pdf_doc_id (fetches S3 URL internally)
        user_id = event.get('user_id')
        pdf_doc_id = event.get('pdf_doc_id')
        session_id = event.get('session_id')
        
        if user_id is None:
            raise ValueError("Missing required parameter: user_id for make_embed_file operation")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id for make_embed_file operation")
        
        # Create config object
        from pdf_autofillr_mapper.configs.aws import AWSStorageConfig
        from pdf_autofillr_mapper.utils.storage_helper import download_from_source
        import os
        
        config = AWSStorageConfig()
        
        # Fetch S3 URLs from backend API
        async with APIClient() as api_client:
            pdf_s3_url = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
            logger.info(f"PDF S3 URL: {pdf_s3_url}")
            
            if not pdf_s3_url.lower().endswith('.pdf'):
                raise ValueError(f"pdf_doc_id must be a PDF file, got: {pdf_s3_url}")
        
        # Store S3 paths in config (for operations to use)
        config.s3_input_pdf = pdf_s3_url
        if config.global_input_json_s3_uri:
            config.s3_global_json = config.global_input_json_s3_uri
        
        # Download PDF to /tmp/ and set local path on config
        local_pdf_path = f"/tmp/form_{pdf_doc_id}.pdf"
        download_from_source(pdf_s3_url, local_pdf_path)
        config.local_input_pdf = local_pdf_path
        logger.info(f"Downloaded PDF to: {local_pdf_path}")
        
        # Download global input JSON if available
        if config.global_input_json_s3_uri:
            local_global_json = f"/tmp/global_input_keys.json"
            try:
                download_from_source(config.global_input_json_s3_uri, local_global_json)
                config.local_global_json = local_global_json
                logger.info(f"Downloaded global JSON to: {local_global_json}")
            except Exception as e:
                logger.warning(f"Failed to download global JSON: {e}")
        
        # ========== CACHE SETUP: Download hash_registry.json from S3 ==========
        from pdf_autofillr_mapper.core.config import settings
        from pdf_autofillr_mapper.utils.hash_cache import populate_cached_files_to_config
        from pdf_autofillr_mapper.utils.storage_helper import upload_to_source
        
        local_cache_registry = None
        s3_cache_registry_path = None
        
        if settings.pdf_cache_enabled:
            try:
                # Get S3 path for hash_registry.json from settings
                s3_cache_registry_path = settings.cache_registry_path
                
                if s3_cache_registry_path and s3_cache_registry_path.startswith('s3://'):
                    local_cache_registry = "/tmp/hash_registry.json"
                    
                    try:
                        download_from_source(s3_cache_registry_path, local_cache_registry)
                        logger.info(f"[Cache] ✓ Downloaded hash_registry.json from S3 to /tmp")
                    except Exception as e:
                        logger.info(f"[Cache] hash_registry.json doesn't exist in S3 yet (first run): {e}")
                        # Will be created after operation completes
                    
                    # Quick extraction to get PDF hash (needed for cache lookup)
                    logger.info("[Cache] Running quick extraction to get PDF hash...")
                    from pdf_autofillr_mapper.extractors.detailed_fitz import DetailedFitzExtractor
                    extractor = DetailedFitzExtractor(config={})  # Pass empty config for quick extraction
                    quick_extract = await extractor.extract_to_json(local_pdf_path, output_file=None)
                    pdf_hash = quick_extract.get('pdf_hash')
                    
                    if pdf_hash:
                        logger.info(f"[Cache] PDF hash: {pdf_hash[:32]}...")
                        
                        # Store extraction result on config to avoid re-extracting
                        config.cached_extraction = quick_extract
                        
                        # Check cache and populate config.cached_* fields
                        cache_hit = await populate_cached_files_to_config(
                            pdf_hash=pdf_hash,
                            cache_registry_path=local_cache_registry,
                            config=config
                        )
                        
                        if cache_hit:
                            logger.info("[Cache] ✅ Config populated with cached files from /tmp")
                        else:
                            logger.info("[Cache] Cache miss - will run full pipeline")
                    else:
                        logger.warning("[Cache] Could not generate PDF hash from extraction")
                else:
                    logger.info("[Cache] cache_registry_path is not an S3 path, skipping cache download")
            except Exception as cache_err:
                logger.warning(f"[Cache] Error setting up cache: {cache_err}")
        
        # ========== RUN OPERATION ==========
        result = await handle_make_embed_file_operation(
            config=config,
            user_id=user_id,
            pdf_doc_id=pdf_doc_id,
            session_id=session_id,
            investor_type=event.get('investor_type', 'individual'),
            mapping_config=event.get('mapping_config', {}),
            use_second_mapper=event.get('use_second_mapper', False),
            notifier=notifier
        )
        
        # ========== CACHE CLEANUP: Upload hash_registry.json back to S3 ==========
        if settings.pdf_cache_enabled and local_cache_registry and s3_cache_registry_path:
            try:
                if os.path.exists(local_cache_registry):
                    upload_to_source(local_cache_registry, s3_cache_registry_path)
                    logger.info(f"[Cache] ✓ Uploaded hash_registry.json back to S3")
                else:
                    logger.warning(f"[Cache] Local cache registry not found at {local_cache_registry}")
            except Exception as upload_err:
                logger.error(f"[Cache] Failed to upload hash_registry.json to S3: {upload_err}")
        
        return result
    
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
        # Validate parameters - uses user_id + pdf_doc_id + session_id
        user_id = event.get('user_id')
        pdf_doc_id = event.get('pdf_doc_id')
        session_id = event.get('session_id')
        input_json_doc_id = event.get('input_json_doc_id')
        
        if user_id is None:
            raise ValueError("Missing required parameter: user_id for fill_pdf operation")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id for fill_pdf operation")
        if session_id is None:
            raise ValueError("Missing required parameter: session_id for fill_pdf operation")
        
        # Create config object
        from pdf_autofillr_mapper.configs.aws import AWSStorageConfig
        from pdf_autofillr_mapper.utils.storage_helper import download_from_source
        
        config = AWSStorageConfig()
        
        # Fetch embedded PDF S3 URL from backend API
        async with APIClient() as api_client:
            # Get embedded PDF (this should already exist from make_embed_file operation)
            embedded_pdf_s3_url = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
            # Modify to get embedded version (assuming naming convention)
            embedded_pdf_s3_url = embedded_pdf_s3_url.replace('.pdf', '_embedded.pdf')
            logger.info(f"Embedded PDF S3 URL: {embedded_pdf_s3_url}")
            
            if not embedded_pdf_s3_url.lower().endswith('.pdf'):
                raise ValueError(f"embedded_pdf_path must be a PDF file, got: {embedded_pdf_s3_url}")
        
        # Store S3 path in config (for operations to use)
        config.s3_embedded_pdf = embedded_pdf_s3_url
        
        # Download embedded PDF to /tmp/
        local_embedded_pdf = f"/tmp/form_{pdf_doc_id}_embedded.pdf"
        download_from_source(embedded_pdf_s3_url, local_embedded_pdf)
        config.local_embedded_pdf = local_embedded_pdf
        logger.info(f"Downloaded embedded PDF to: {local_embedded_pdf}")
        
        # Get input JSON (combined user + session data)
        logger.info("Combining user profile and session data...")
        input_json_s3_path = await combine_user_and_session_data(
            user_id=user_id,
            session_id=session_id,
            use_profile_info=event.get('use_profile_info', True)
        )
        logger.info(f"Combined JSON S3 path: {input_json_s3_path}")
        
        # Store S3 path in config (for operations to use)
        config.s3_input_json = input_json_s3_path
        
        # Download input JSON to /tmp/
        local_input_json = f"/tmp/data_{user_id}_{session_id}.json"
        download_from_source(input_json_s3_path, local_input_json)
        config.local_input_json = local_input_json
        logger.info(f"Downloaded input JSON to: {local_input_json}")
        
        return await handle_fill_pdf_operation(
            config=config,
            user_id=user_id,
            session_id=session_id,
            pdf_doc_id=pdf_doc_id,
            input_json_doc_id=input_json_doc_id,
            notifier=notifier
        )
    
    elif operation == 'check_embed_file':
        # Validate parameters - uses user_id + pdf_doc_id
        user_id = event.get('user_id')
        pdf_doc_id = event.get('pdf_doc_id')
        
        if user_id is None:
            raise ValueError("Missing required parameter: user_id for check_embed_file operation")
        if pdf_doc_id is None:
            raise ValueError("Missing required parameter: pdf_doc_id for check_embed_file operation")
        
        # Create config object
        from pdf_autofillr_mapper.configs.aws import AWSStorageConfig
        from pdf_autofillr_mapper.utils.storage_helper import download_from_source
        
        config = AWSStorageConfig()
        
        # Fetch embedded PDF S3 URL from backend API
        async with APIClient() as api_client:
            pdf_s3_url = await api_client.get_document_s3_url(doc_id=pdf_doc_id)
            # Modify to get embedded version (assuming naming convention)
            embedded_pdf_s3_url = pdf_s3_url.replace('.pdf', '_embedded.pdf')
            logger.info(f"Embedded PDF S3 URL: {embedded_pdf_s3_url}")
        
        # Download embedded PDF to /tmp/ (if it exists)
        local_embedded_pdf = f"/tmp/form_{pdf_doc_id}_embedded.pdf"
        try:
            download_from_source(embedded_pdf_s3_url, local_embedded_pdf)
            config.local_embedded_pdf = local_embedded_pdf
            logger.info(f"Downloaded embedded PDF to: {local_embedded_pdf}")
        except Exception as e:
            # File might not exist - that's ok, check operation will handle it
            logger.info(f"Embedded PDF not found in S3: {e}")
            config.local_embedded_pdf = local_embedded_pdf  # Set path anyway for check
        
        return await handle_check_embed_file_operation(
            config=config,
            user_id=user_id,
            session_id=event.get('session_id')
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
