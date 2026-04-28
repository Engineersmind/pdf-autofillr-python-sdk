"""

Core operation handlers - source-agnostic business logic.



These handlers work with ANY storage backend (AWS S3, Azure Blob, GCS, local filesystem).

They use the universal storage helpers for download/upload operations.



Platform-specific wrappers (lambda_handler.py, azure_function.py, etc.) call these functions.

"""



import os

import time

import json

import asyncio

import logging

import shutil

from pathlib import Path

from typing import Optional, Dict, Any



from pdf_autofillr_mapper.core.config import get_complete_file_config, get_processing_output_config

from pdf_autofillr_mapper.utils.storage_helper import (

    download_from_source,

    upload_to_source,

    file_exists,

    create_storage_config,

    get_storage_type

)

from pdf_autofillr_mapper.handlers.file_handlers import create_file_handlers

from pdf_autofillr_mapper.extractors.detailed_fitz import DetailedFitzExtractor

from pdf_autofillr_mapper.mappers.semantic_mapper import SemanticMapper

from pdf_autofillr_mapper.embedders.embed_keys import run_embed_java_stage

from pdf_autofillr_mapper.fillers.fill_pdf import fill_with_java

from pdf_autofillr_mapper.utils.map_time_estimator import estimate_map_stage_time



# Import notification system (optional)

try:

    from adapter_src.notifier import (

        PipelineNotifier,

        PipelineStage,

        StageStatus,

        NotificationLevel

    )

    NOTIFICATIONS_AVAILABLE = True

except ImportError:

    NOTIFICATIONS_AVAILABLE = False

    PipelineNotifier = None



logger = logging.getLogger(__name__)





async def safe_notify(notifier, operation_name: str, *args, **kwargs) -> bool:

    """Safely send notification without failing the pipeline."""

    if not notifier or not NOTIFICATIONS_AVAILABLE:

        return False

    

    try:

        if operation_name == "stage_completion":

            return await notifier.notify_stage_completion(*args, **kwargs)

        elif operation_name == "pipeline_completion":

            return await notifier.notify_pipeline_completion(*args, **kwargs)

        else:

            logger.warning(f"Unknown notification operation: {operation_name}")

            return False

    except Exception as e:

        logger.warning(f"Notification failed for {operation_name}: {e}")

        return False





async def handle_extract_operation(

    config,  # Storage config (first parameter)

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    notifier: Optional[Any] = None,

    pdf_doc_id: Optional[int] = None,

    input_json_doc_id: Optional[int] = None,

    input_json_path: Optional[str] = None,

    mapping_config: Optional[dict] = None

) -> Dict[str, Any]:

    """

    Extract form fields from PDF - works with ANY storage backend.

    

    Args:

        config: Storage config with pre-configured paths

        user_id: Optional user ID for tracking

        session_id: Optional session ID for tracking

        notifier: Optional notification system

        pdf_doc_id: Optional PDF document ID

        input_json_doc_id: Optional input JSON document ID

        input_json_path: Optional input JSON path for pre-map estimation

        mapping_config: Optional mapping config for pre-map estimation

        

    Returns:

        Operation result with output file path

    """

    start_time = time.time()

    

    logger.info("=" * 60)

    logger.info("EXTRACT OPERATION")

    logger.info("=" * 60)

    logger.info(f"Storage type: {config.source_type}")

    logger.info(f"User ID: {user_id}, Session ID: {session_id}")

    

    user_input_details = {

        "user_id": user_id,

        "pdf_doc_id": pdf_doc_id,

        "input_json_doc_id": input_json_doc_id,

        "session_id": session_id

    }

    

    try:

        # Create file handlers

        input_handler, output_handler = create_file_handlers(config)

        

        # Get input PDF (already downloaded by entrypoint)

        local_pdf = input_handler.get_input('input_pdf')

        if not local_pdf:

            raise FileNotFoundError("Input PDF not available")

        

        logger.info(f"Input PDF: {local_pdf}")

        

        # Initialize extractor

        extractor_config = {

            "WIDGET_LINE_DISTANCE_THRESHOLD": 10,

            "rounding": 1

        }

        extractor = DetailedFitzExtractor(extractor_config)

        

        # Extract to configured path

        extraction_output_path = config.local_extracted_json

        storage_config = {

            "type": "local",

            "path": extraction_output_path

        }

        

        # Extract from PDF

        result = extractor.extract(

            pdf_path=local_pdf,

            storage_config=storage_config

        )

        

        # Save output immediately to source storage

        saved_path = output_handler.save_output(extraction_output_path, 'extracted_json')

        if saved_path:

            logger.info(f"✅ Saved extraction to: {saved_path}")

        

        # Get PDF hash

        pdf_hash = result.get('pdf_hash')

        if pdf_hash:

            logger.info(f"PDF fingerprint hash: {pdf_hash[:16]}...")

        

        # Optional: pre-compute map stage estimate

        pre_map_time_estimate = None

        if input_json_path:

            try:

                pre_map_time_estimate = estimate_map_stage_time(

                    extracted_json_path=extraction_output_path,

                    input_json_path=input_json_path,

                    mapping_config=mapping_config or {}

                )

                logger.info(f"Pre-map estimate: {pre_map_time_estimate.get('status')}")

            except Exception as estimate_error:

                logger.warning(f"Failed pre-map estimate: {estimate_error}")

                pre_map_time_estimate = {"status": "error", "error": str(estimate_error)}

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        # Send success notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.EXTRACT,

                status=StageStatus.COMPLETED,

                execution_time=duration,

                input_files={"pdf": local_pdf},

                output_files={"extracted_json": extraction_output_path},

                user_input_details=user_input_details,

                metadata={

                    "storage_type": config.source_type,

                    "extractor_config": extractor_config,

                    "fields_extracted": len(result.get("fields", [])) if isinstance(result, dict) else None,

                    "pre_map_time_estimate": pre_map_time_estimate

                }

            )

        

        logger.info(f"✅ Extraction completed in {duration}s")

        logger.info("=" * 60)

        

        response = {

            "operation": "extract",

            "output_file": extraction_output_path,

            "storage_type": config.source_type,

            "status": "success",

            "execution_time_seconds": duration,

            "pdf_hash": pdf_hash

        }

        

        if pre_map_time_estimate:

            response["pre_map_time_estimate"] = pre_map_time_estimate

        

        return response

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        # Send failure notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.EXTRACT,

                status=StageStatus.FAILED,

                execution_time=duration,

                error_message=str(e),

                level=NotificationLevel.CRITICAL,

                user_input_details=user_input_details,

                metadata={"storage_type": config.source_type, "error_type": type(e).__name__}

            )

        

        logger.error(f"❌ Extraction failed after {duration}s: {str(e)}")

        raise





async def handle_map_operation(

    config,  # Storage config (first parameter)

    mapping_config: dict,

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    notifier: Optional[Any] = None,

    pdf_doc_id: Optional[int] = None,

    input_json_doc_id: Optional[int] = None,

    investor_type: Optional[str] = None

) -> Dict[str, Any]:

    """

    Semantic mapping operation - works with ANY storage backend.

    

    Args:

        config: Storage config with pre-configured paths

        mapping_config: Mapping configuration

        user_id: Optional user ID

        session_id: Optional session ID

        notifier: Optional notification system

        pdf_doc_id: Optional PDF document ID

        input_json_doc_id: Optional input JSON document ID

        investor_type: Optional investor type

        

    Returns:

        Operation result with output files

    """

    start_time = time.time()

    

    logger.info("=" * 60)

    logger.info("MAP OPERATION")

    logger.info("=" * 60)

    logger.info(f"Storage type: {config.source_type}")

    logger.info(f"User ID: {user_id}, Session ID: {session_id}")

    logger.info(f"Investor Type: {investor_type}")

    

    user_input_details = {

        "user_id": user_id,

        "pdf_doc_id": pdf_doc_id,

        "input_json_doc_id": input_json_doc_id,

        "session_id": session_id,

        "investor_type": investor_type

    }

    

    try:

        # Create file handlers

        input_handler, output_handler = create_file_handlers(config)

        

        # Get input files (already downloaded by entrypoint)

        local_extracted = input_handler.get_input('extracted_json')

        local_input = input_handler.get_input('input_json')

        

        if not local_extracted or not local_input:

            raise FileNotFoundError("Required input files not available")

        

        logger.info(f"Extracted JSON: {local_extracted}")

        logger.info(f"Input JSON: {local_input}")

        

        # Initialize mapper - use llm_model from settings (LiteLLM format)

        from pdf_autofillr_mapper.core.config import settings

        mapper = SemanticMapper(

            llm_provider=mapping_config.get("llm_model", settings.llm_model),

            confidence_threshold=mapping_config.get("confidence_threshold", 0.7),

            chunking_strategy=mapping_config.get("chunking_strategy", "page")

        )

        

        # Use configured output paths

        local_mapping = config.local_mapped_json

        local_radio = config.local_radio_json

        

        # Debug: Check if paths are set

        if not local_mapping or not local_radio:

            logger.error(f"❌ Config paths not set!")

            logger.error(f"   local_mapped_json: {local_mapping}")

            logger.error(f"   local_radio_json: {local_radio}")

            raise ValueError(f"Config missing paths: local_mapped_json={local_mapping}, local_radio_json={local_radio}")

        

        logger.info(f"Output paths configured:")

        logger.info(f"   Mapping: {local_mapping}")

        logger.info(f"   Radio groups: {local_radio}")

        

        storage_config = {

            "output_path": local_mapping,

            "radio_groups": local_radio

        }

        

        # Perform mapping

        mapping_result = await mapper.process_and_save(

            extracted_path=local_extracted,

            input_json_path=local_input,

            original_pdf_path="",

            storage_config=storage_config,

            investor_type=investor_type

        )

        

        # The semantic mapper outputs dictionary format with wrapper: {"user_id": ..., "predictions": {...}}

        # Save this as semantic_mapping.json for reference/debugging/caching

        semantic_path = local_mapping.replace("_mapped_fields.json", "_semantic_mapping.json")

        logger.info(f"💾 Saving semantic mapper output (for cache): {semantic_path}")

        shutil.copy2(local_mapping, semantic_path)

        

        # Now convert to Java-compatible format for the embedder

        # Java embedder needs array format without wrapper: {"field_id": ["field_name", "", confidence]}

        logger.info("🔄 Converting semantic mapping to Java-compatible format...")

        with open(local_mapping, 'r') as f:

            semantic_data = json.load(f)

        

        # Strip wrapper if present

        if isinstance(semantic_data, dict) and "predictions" in semantic_data:

            semantic_mappings = semantic_data["predictions"]

        else:

            semantic_mappings = semantic_data

        

        # Convert to Java array format

        java_mapping = {}

        for field_id, mapping_data in semantic_mappings.items():

            if isinstance(mapping_data, dict):

                field_name = mapping_data.get("predicted_field_name")

                confidence = mapping_data.get("confidence", 0.0)

                java_mapping[field_id] = [field_name, "", confidence] if field_name else [None, None, 0]

            elif isinstance(mapping_data, list) and len(mapping_data) >= 3:

                field_name = mapping_data[0]

                confidence = mapping_data[2]

                java_mapping[field_id] = [field_name, "", confidence] if field_name else [None, None, 0]

            elif mapping_data is None:

                java_mapping[field_id] = [None, None, 0]

            else:

                logger.warning(f"Field {field_id} has unexpected format: {mapping_data}")

                java_mapping[field_id] = [None, None, 0]

        

        # Save Java format to mapped_fields.json (for embedder)

        with open(local_mapping, 'w') as f:

            json.dump(java_mapping, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Converted {len(java_mapping)} fields to Java format -> {local_mapping}")

        

        # Save outputs immediately to source storage

        # IMPORTANT: Save semantic mapping first (for cache), then Java format (for embedder)

        saved_semantic = output_handler.save_output(semantic_path, 'semantic_mapping_json')

        saved_mapping = output_handler.save_output(local_mapping, 'mapped_json')

        saved_radio = output_handler.save_output(local_radio, 'radio_json')

        

        if saved_semantic:

            logger.info(f"✅ Saved semantic mapping (for cache): {saved_semantic}")

        if saved_mapping:

            logger.info(f"✅ Saved Java mapping (for embedder): {saved_mapping}")

        if saved_radio:

            logger.info(f"✅ Saved radio groups to: {saved_radio}")

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        # Extract statistics

        field_stats = mapping_result.get("field_statistics", {})

        

        # Send success notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.MAP,

                status=StageStatus.COMPLETED,

                execution_time=duration,

                input_files={

                    "extracted_json": local_extracted,

                    "input_keys": local_input

                },

                output_files={

                    "mapping": local_mapping,

                    "radio_groups": local_radio

                },

                user_input_details=user_input_details,

                performance_metrics={

                    "total_fields_mapped": field_stats.get("total_fields_mapped", 0),

                    "high_confidence_count": field_stats.get("high_confidence_count", 0),

                    "storage_type": config.source_type

                }

            )

        

        logger.info(f"✅ Mapping completed in {duration}s")

        logger.info("=" * 60)

        

        return {

            "operation": "map",

            "mapping_result": {

                "mapping_path": local_mapping,  # Local processing path

                "radio_groups_path": local_radio,  # Local processing path

                "field_statistics": field_stats,

                # ADD: Destination paths for cache registration

                "dest_mapping_path": saved_mapping,  # Where file was saved (persistent)

                "dest_radio_groups_path": saved_radio  # Where file was saved (persistent)

            },

            "storage_type": config.source_type,

            "status": "success",

            "execution_time_seconds": duration

        }

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.MAP,

                status=StageStatus.FAILED,

                execution_time=duration,

                error_message=str(e),

                level=NotificationLevel.CRITICAL,

                user_input_details=user_input_details,

                metadata={"storage_type": config.source_type, "error_type": type(e).__name__}

            )

        

        logger.error(f"❌ Mapping failed after {duration}s: {str(e)}")

        raise





async def handle_embed_operation(

    config,  # Storage config (first parameter)

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    notifier: Optional[Any] = None,

    pdf_doc_id: Optional[int] = None

) -> Dict[str, Any]:

    """

    Embed operation - embeds form data into PDF using Java rebuilder.

    Works with ANY storage backend.

    

    Args:

        config: Storage config with pre-configured paths

        user_id: Optional user ID

        session_id: Optional session ID

        notifier: Optional notification system

        pdf_doc_id: Optional PDF document ID

        

    Returns:

        Operation result with embedded PDF path

    """

    start_time = time.time()

    

    logger.info("=" * 60)

    logger.info("EMBED OPERATION")

    logger.info("=" * 60)

    logger.info(f"Storage type: {config.source_type}")

    logger.info(f"User ID: {user_id}, Session ID: {session_id}")

    

    user_input_details = {

        "user_id": user_id,

        "pdf_doc_id": pdf_doc_id,

        "session_id": session_id

    }

    

    try:

        # Create file handlers

        input_handler, output_handler = create_file_handlers(config)

        

        # Get input files

        # PDF and extracted JSON can be downloaded if needed

        local_pdf = input_handler.get_input('input_pdf')

        local_extracted = input_handler.get_input('extracted_json')

        

        # Mapped JSON and radio groups were created in THIS pipeline run,

        # so they're already at the config paths (not downloaded)

        local_mapping = config.local_mapped_json

        local_radio = config.local_radio_json

        

        if not all([local_pdf, local_extracted, local_mapping, local_radio]):

            missing = []

            if not local_pdf: missing.append("PDF")

            if not local_extracted: missing.append("extracted JSON")

            if not local_mapping: missing.append("mapping JSON")

            if not local_radio: missing.append("radio groups")

            raise FileNotFoundError(f"Required input files not available: {', '.join(missing)}")

        

        logger.info(f"Input PDF: {local_pdf}")

        logger.info(f"Extracted JSON: {local_extracted}")

        logger.info(f"Mapping JSON: {local_mapping}")

        logger.info(f"Radio groups: {local_radio}")

        

        # Use configured output path

        local_embedded = config.local_embedded_pdf

        storage_config = {

            "type": "local",

            "path": local_embedded

        }

        

        # Run Java embedder

        embedded_pdf = await run_embed_java_stage(

            original_pdf=local_pdf,

            extracted_json=local_extracted,

            mapping_json=local_mapping,

            radio_json=local_radio,

            storage_config=storage_config

        )

        

        # Save output immediately to source storage

        # Use the ACTUAL output path from Java embedder, not the config path

        logger.info(f"🔍 DEBUG: About to save embedded PDF:")

        logger.info(f"   embedded_pdf (actual output): {embedded_pdf}")

        logger.info(f"   config.dest_embedded_pdf: {config.dest_embedded_pdf}")

        

        saved_path = output_handler.save_output(embedded_pdf, 'embedded_pdf')

        

        logger.info(f"🔍 DEBUG: Save result:")

        logger.info(f"   saved_path: {saved_path}")

        

        if saved_path:

            logger.info(f"✅ Saved embedded PDF to: {saved_path}")

        else:

            logger.error(f"❌ Failed to save embedded PDF!")

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        # Send success notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.EMBED,

                status=StageStatus.COMPLETED,

                execution_time=duration,

                input_files={

                    "pdf": local_pdf,

                    "extracted": local_extracted,

                    "mapping": local_mapping,

                    "radio_groups": local_radio

                },

                output_files={"embedded_pdf": local_embedded},

                user_input_details=user_input_details,

                metadata={"storage_type": config.source_type}

            )

        

        logger.info(f"✅ Embedding completed in {duration}s")

        logger.info("=" * 60)

        

        return {

            "operation": "embed",

            "output_file": embedded_pdf,  # Actual output path from Java embedder

            "dest_output_file": saved_path,  # Destination path for cache registration

            "storage_type": config.source_type,

            "status": "success",

            "execution_time_seconds": duration

        }

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.EMBED,

                status=StageStatus.FAILED,

                execution_time=duration,

                error_message=str(e),

                level=NotificationLevel.CRITICAL,

                user_input_details=user_input_details,

                metadata={"storage_type": config.source_type, "error_type": type(e).__name__}

            )

        

        logger.error(f"❌ Embedding failed after {duration}s: {str(e)}")

        raise





async def handle_fill_operation(

    config,  # Storage config (first parameter)

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    notifier: Optional[Any] = None,

    pdf_doc_id: Optional[int] = None,

    input_json_doc_id: Optional[int] = None

) -> Dict[str, Any]:

    """

    Fill operation - fills embedded PDF with user data using Java filler.

    Works with ANY storage backend.

    

    Args:

        config: Storage config with pre-configured paths

        user_id: Optional user ID

        session_id: Optional session ID

        notifier: Optional notification system

        pdf_doc_id: Optional PDF document ID

        input_json_doc_id: Optional input JSON document ID

        

    Returns:

        Operation result with filled PDF path

    """

    start_time = time.time()

    

    logger.info("=" * 60)

    logger.info("FILL OPERATION")

    logger.info("=" * 60)

    logger.info(f"Storage type: {config.source_type}")

    logger.info(f"User ID: {user_id}, Session ID: {session_id}")

    

    user_input_details = {

        "user_id": user_id,

        "pdf_doc_id": pdf_doc_id,

        "input_json_doc_id": input_json_doc_id,

        "session_id": session_id

    }

    

    try:

        # Create file handlers

        input_handler, output_handler = create_file_handlers(config)

        

        # Get input files (already downloaded by entrypoint)

        local_embedded = input_handler.get_input('embedded_pdf')

        local_input = input_handler.get_input('input_json')

        

        if not local_embedded or not local_input:

            raise FileNotFoundError("Required input files not available")

        

        logger.info(f"Embedded PDF: {local_embedded}")

        logger.info(f"Input JSON: {local_input}")

        

        # Use configured output path

        local_filled = config.local_filled_pdf

        storage_config = {

            "type": "local",

            "path": local_filled

        }

        

        # Run Java filler

        filled_pdf = await fill_with_java(

            embedded_pdf=local_embedded,

            input_json=local_input,

            storage_config=storage_config

        )

        

        # Save output immediately to source storage

        saved_path = output_handler.save_output(local_filled, 'filled_pdf')

        if saved_path:

            logger.info(f"✅ Saved filled PDF to: {saved_path}")

        

        # Generate presigned URL for S3 files

        filled_presigned_url = None

        if config.source_type == "aws" and hasattr(config, 's3_filled_pdf'):

            try:

                from pdf_autofillr_mapper.clients.s3_client import S3Client

                s3_client = S3Client()

                filled_presigned_url = s3_client.generate_presigned_url(saved_path, expires_in=3600)

                logger.info("✅ Generated presigned URL for filled PDF (expires in 1 hour)")

            except Exception as presign_error:

                logger.warning(f"Failed to generate presigned URL for filled PDF: {presign_error}")

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        # Send success notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.FILL,

                status=StageStatus.COMPLETED,

                execution_time=duration,

                input_files={

                    "embedded_pdf": local_embedded,

                    "input_json": local_input

                },

                output_files={"filled_pdf": local_filled},

                user_input_details=user_input_details,

                metadata={"storage_type": config.source_type}

            )

        

        logger.info(f"✅ Filling completed in {duration}s")

        logger.info("=" * 60)

        

        result = {

            "operation": "fill",

            "output_file": local_filled,

            "storage_type": config.source_type,

            "status": "success",

            "execution_time_seconds": duration

        }

        

        # Add presigned URL if available

        if filled_presigned_url:

            result["filled_presigned_url"] = filled_presigned_url

            logger.info(f"Presigned URL included in response")

        

        return result

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.FILL,

                status=StageStatus.FAILED,

                execution_time=duration,

                error_message=str(e),

                level=NotificationLevel.CRITICAL,

                user_input_details=user_input_details,

                metadata={"storage_type": config.source_type, "error_type": type(e).__name__}

            )

        

        logger.error(f"❌ Filling failed after {duration}s: {str(e)}")

        raise





async def handle_run_all_operation(

    input_pdf: str,

    input_json: str,

    mapping_config: dict,

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    notifier: Optional[Any] = None,

    pdf_doc_id: Optional[int] = None,

    input_json_doc_id: Optional[int] = None

) -> Dict[str, Any]:

    """

    Run all operation - executes complete pipeline (extract -> map -> embed -> fill).

    Works with ANY storage backend.

    

    Args:

        input_pdf: Input PDF path (s3://, gs://, azure://, or local)

        input_json: Input JSON with user data

        mapping_config: Mapping configuration

        user_id: Optional user ID

        session_id: Optional session ID

        notifier: Optional notification system

        pdf_doc_id: Optional PDF document ID

        input_json_doc_id: Optional input JSON document ID

        

    Returns:

        Complete pipeline result with all output files

    """

    start_time = time.time()

    storage_type = get_storage_type(input_pdf)

    

    logger.info("=" * 80)

    logger.info("RUN ALL OPERATION - COMPLETE PIPELINE")

    logger.info("=" * 80)

    logger.info(f"Input PDF: {input_pdf}")

    logger.info(f"Input JSON: {input_json}")

    logger.info(f"Storage type: {storage_type}")

    

    pipeline_results = {}

    

    try:

        # Stage 1: Extract

        logger.info("\n[1/4] Starting EXTRACT stage...")

        extract_result = await handle_extract_operation(

            input_file=input_pdf,

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id,

            input_json_doc_id=input_json_doc_id,

            input_json_path=input_json,

            mapping_config=mapping_config

        )

        pipeline_results["extract"] = extract_result

        extracted_json = extract_result["output_file"]

        logger.info(f"✅ EXTRACT completed: {extracted_json}")

        

        # Stage 2: Map

        logger.info("\n[2/4] Starting MAP stage...")

        map_result = await handle_map_operation(

            config=config,  # Pass config instead of file paths

            mapping_config=mapping_config,

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id,

            input_json_doc_id=input_json_doc_id

        )

        pipeline_results["map"] = map_result

        mapping_json = map_result["mapping_result"]["mapping_path"]

        radio_groups = map_result["mapping_result"]["radio_groups_path"]

        logger.info(f"✅ MAP completed: {mapping_json}")

        

        # Stage 3: Embed

        logger.info("\n[3/4] Starting EMBED stage...")

        embed_result = await handle_embed_operation(

            config=config,  # Pass config instead of file paths

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id

        )

        pipeline_results["embed"] = embed_result

        embedded_pdf = embed_result["output_file"]

        logger.info(f"✅ EMBED completed: {embedded_pdf}")

        

        # Stage 4: Fill

        logger.info("\n[4/4] Starting FILL stage...")

        fill_result = await handle_fill_operation(

            embedded_pdf_path=embedded_pdf,

            input_json_path=input_json,

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id,

            input_json_doc_id=input_json_doc_id

        )

        pipeline_results["fill"] = fill_result

        filled_pdf = fill_result["output_file"]

        logger.info(f"✅ FILL completed: {filled_pdf}")

        

        # Pipeline complete

        end_time = time.time()

        total_duration = round(end_time - start_time, 2)

        

        # Send pipeline completion notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "pipeline_completion",

                status="completed",

                total_duration=total_duration,

                final_output=filled_pdf,

                stage_results=pipeline_results

            )

        

        logger.info("\n" + "=" * 80)

        logger.info(f"✅ COMPLETE PIPELINE SUCCESS in {total_duration}s")

        logger.info("=" * 80)

        

        return {

            "operation": "run_all",

            "status": "success",

            "storage_type": storage_type,

            "total_execution_time_seconds": total_duration,

            "final_output": filled_pdf,

            "pipeline_results": pipeline_results

        }

        

    except Exception as e:

        end_time = time.time()

        total_duration = round(end_time - start_time, 2)

        

        # Send pipeline failure notification

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "pipeline_completion",

                status="failed",

                total_duration=total_duration,

                error_message=str(e),

                stage_results=pipeline_results

            )

        

        logger.error("\n" + "=" * 80)

        logger.error(f"❌ PIPELINE FAILED after {total_duration}s: {str(e)}")

        logger.error("=" * 80)

        raise





async def handle_refresh_operation(

    input_pdf: str,

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    notifier: Optional[Any] = None

) -> Dict[str, Any]:

    """

    Refresh operation - re-extracts data from PDF and updates config.

    Works with ANY storage backend.

    

    This is similar to extract but specifically for refreshing existing configs.

    

    Args:

        input_pdf: Input PDF path (s3://, gs://, azure://, or local)

        user_id: Optional user ID

        session_id: Optional session ID

        notifier: Optional notification system

        

    Returns:

        Operation result with refreshed extraction

    """

    start_time = time.time()

    storage_type = get_storage_type(input_pdf)

    

    logger.info("=" * 60)

    logger.info("REFRESH OPERATION")

    logger.info("=" * 60)

    logger.info(f"Input PDF: {input_pdf}")

    logger.info(f"Storage type: {storage_type}")

    logger.info("Re-extracting PDF data to refresh configuration...")

    

    try:

        # Call extract operation (refresh is essentially a re-extract)

        result = await handle_extract_operation(

            input_file=input_pdf,

            user_id=user_id,

            session_id=session_id,

            notifier=notifier

        )

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        logger.info(f"✅ Refresh completed in {duration}s")

        logger.info("=" * 60)

        

        return {

            "operation": "refresh",

            "status": "success",

            "storage_type": storage_type,

            "execution_time_seconds": duration,

            "refreshed_file": result["output_file"],

            "extraction_result": result

        }

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        logger.error(f"❌ Refresh failed after {duration}s: {str(e)}")

        raise





# ==============================================================================

# PHASE 1: SEMANTIC MAPPER (with cache support)

# ==============================================================================



async def run_semantic_api_mapper(

    extracted_json_path: str,

    input_json_path: str,

    storage_config: Any,

    user_id: int,

    pdf_doc_id: int,

    session_id: Optional[int],

    pdf_hash: Optional[str],

    cache_registry_path: str,

    investor_type: str = 'individual',

    mapping_config: Optional[dict] = None,

    notifier: Optional[Any] = None

) -> Dict[str, Any]:

    """

    Run semantic mapper (Phase 1) with cache check.

    

    Returns semantic_mapping.json path (raw LLM output format - this is cached).

    Also returns radio_groups.json path.

    

    Cache strategy:

    - Check cache FIRST using pdf_hash

    - If HIT: Download cached semantic_mapping.json + radio_groups.json -> return paths

    - If MISS: Run semantic mapper -> save outputs -> register in cache -> return paths

    

    Output format (semantic_mapping.json):

        - If wrapped: {"user_id": "...", "predictions": {"field_2": {...}}}

        - If unwrapped: {"field_2": {...}}

    

    Args:

        extracted_json_path: Path to extracted JSON from extract stage

        input_json_path: Path to input/global JSON template

        storage_config: Storage configuration object

        user_id, pdf_doc_id, session_id: IDs for path generation

        pdf_hash: PDF content hash for cache lookup

        cache_registry_path: Path to cache registry file

        investor_type: Investor type for mapping

        mapping_config: Optional mapping configuration

        notifier: Optional notification system

    

    Returns:

        {

            "semantic_mapping_path": str,  # Path to semantic_mapping.json

            "radio_groups_path": str,       # Path to radio_groups.json

            "dest_semantic_mapping": str,   # Destination path (for cache registration)

            "dest_radio_groups": str,       # Destination path (for cache registration)

            "cache_hit": bool                # Whether this was a cache hit

        }

    """

    from pdf_autofillr_mapper.core.config import settings

    from pdf_autofillr_mapper.utils.hash_cache import check_hash_cache, copy_cached_files

    import os

    import json

    

    logger.info("=" * 80)

    logger.info("PHASE 1: SEMANTIC API MAPPER (with cache check)")

    logger.info("=" * 80)

    

    # Check cache first

    cache_hit = False

    cache_result = None

    

    if pdf_hash:

        try:

            logger.info(f"🔍 Checking cache for pdf_hash: {pdf_hash[:16]}...")

            os.makedirs(os.path.dirname(cache_registry_path), exist_ok=True)

            cache_result = await check_hash_cache(pdf_hash, cache_registry_path)

            

            # IMPORTANT: Persist updated cache registry after check (usage stats were updated)

            if cache_result and os.path.exists(cache_registry_path):

                from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                cache_output_handler = OutputFileHandler(storage_config)

                cache_dest = cache_output_handler.save_output(

                    cache_registry_path, 

                    'cache_registry_json'

                )

                if cache_dest:

                    logger.info(f"📤 Cache registry updated and persisted to: {cache_dest}")

                else:

                    logger.debug("Cache registry persisted (local mode)")

            

            if cache_result and "reference_files" in cache_result:

                logger.info("🎯 CACHE HIT! Using cached semantic mapping")

                cache_hit = True

                

                # Check if files already downloaded by entrypoint

                if (hasattr(storage_config, 'cached_mapping_json') and 

                    storage_config.cached_mapping_json and

                    hasattr(storage_config, 'cached_radio_groups') and

                    storage_config.cached_radio_groups):

                    

                    logger.info("✅ Using cached files from entrypoint")

                    semantic_mapping_path = storage_config.cached_mapping_json

                    radio_groups_path = storage_config.cached_radio_groups

                    

                    # Destination paths are same as source (already in persistent storage)

                    dest_semantic_mapping = cache_result["reference_files"].get("mapping_json")

                    dest_radio_groups = cache_result["reference_files"].get("radio_groups")

                    

                    return {

                        "semantic_mapping_path": semantic_mapping_path,

                        "radio_groups_path": radio_groups_path,

                        "dest_semantic_mapping": dest_semantic_mapping,

                        "dest_radio_groups": dest_radio_groups,

                        "cache_hit": True

                    }

                else:

                    # Copy cached files to processing directory

                    logger.info("📥 Copying cached files to processing directory")

                    target_dir = os.path.dirname(extracted_json_path)

                    

                    copied_files = await copy_cached_files(

                        source_files=cache_result["reference_files"],

                        target_dir=target_dir

                    )

                    

                    semantic_mapping_path = copied_files.get("mapping_json")

                    radio_groups_path = copied_files.get("radio_groups")

                    

                    if semantic_mapping_path and radio_groups_path:

                        logger.info(f"✅ Cached semantic mapping: {semantic_mapping_path}")

                        logger.info(f"✅ Cached radio groups: {radio_groups_path}")

                        

                        # Destination paths from cache

                        dest_semantic_mapping = cache_result["reference_files"].get("mapping_json")

                        dest_radio_groups = cache_result["reference_files"].get("radio_groups")

                        

                        return {

                            "semantic_mapping_path": semantic_mapping_path,

                            "radio_groups_path": radio_groups_path,

                            "dest_semantic_mapping": dest_semantic_mapping,

                            "dest_radio_groups": dest_radio_groups,

                            "cache_hit": True

                        }

                    else:

                        logger.warning("❌ Cache hit but files missing, will re-run mapper")

                        cache_hit = False

        except Exception as cache_error:

            logger.warning(f"Cache check failed: {cache_error}, will run mapper")

            cache_hit = False

    else:

        logger.info("⚠️  No pdf_hash available, skipping cache check")

    

    # Cache miss - run semantic mapper

    logger.info("🚀 Running semantic mapper (Phase 1)...")

    

    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

    from pdf_autofillr_mapper.mappers.semantic_mapper import SemanticMapper

    from pdf_autofillr_mapper.core.config import settings

    

    # Initialize handlers

    output_handler = OutputFileHandler(storage_config)

    

    # Initialize mapper with proper configuration

    mapper = SemanticMapper(

        llm_provider=mapping_config.get("llm_model", settings.llm_model) if mapping_config else settings.llm_model,

        confidence_threshold=mapping_config.get("confidence_threshold", 0.7) if mapping_config else 0.7,

        chunking_strategy=mapping_config.get("chunking_strategy", "page") if mapping_config else "page"

    )

    

    # Run semantic mapper

    logger.info(f"Input extracted JSON: {extracted_json_path}")

    logger.info(f"Input template JSON: {input_json_path}")

    

    # Use output paths from config (already set by entrypoint from config.ini)

    local_mapping = storage_config.local_mapped_json

    local_radio = storage_config.local_radio_json

    

    if not local_mapping or not local_radio:

        raise ValueError(f"Config missing output paths: local_mapped_json={local_mapping}, local_radio_json={local_radio}")

    

    logger.info(f"Output semantic mapping: {local_mapping}")

    logger.info(f"Output radio groups: {local_radio}")

    

    # Create storage config dict for semantic mapper

    mapper_storage_config = {

        "output_path": local_mapping,

        "radio_groups": local_radio

    }

    

    mapping_result = await mapper.process_and_save(

        extracted_path=extracted_json_path,

        input_json_path=input_json_path,

        original_pdf_path="",  # Not needed for semantic mapping

        storage_config=mapper_storage_config,

        investor_type=investor_type

    )

    

    # Verify output paths from mapper match config paths

    mapper_output = mapping_result.get("mapping_path")

    mapper_radio = mapping_result.get("radio_groups_path")

    

    if not mapper_output or not mapper_radio:

        raise ValueError("Semantic mapper did not return required output paths")

    

    logger.info(f"✅ Semantic mapper completed")

    logger.info(f"   Semantic mapping (raw): {mapper_output}")

    logger.info(f"   Radio groups: {mapper_radio}")

    logger.info(f"   Radio groups: {local_radio}")

    

    # Save to destination storage (returns destination path or None)

    dest_semantic_mapping = output_handler.save_output(local_mapping, 'semantic_mapping_json')

    dest_radio_groups = output_handler.save_output(local_radio, 'radio_json')

    

    if dest_semantic_mapping:

        logger.info(f"📤 Uploaded semantic mapping to: {dest_semantic_mapping}")

    if dest_radio_groups:

        logger.info(f"📤 Uploaded radio groups to: {dest_radio_groups}")

    

    # NOTE: Phase 1 cache (semantic + radio + embedded_pdf) will be saved AFTER embed stage

    # because embedded PDF doesn't exist yet at this point

    

    return {

        "semantic_mapping_path": local_mapping,

        "radio_groups_path": local_radio,

        "dest_semantic_mapping": dest_semantic_mapping,

        "dest_radio_groups": dest_radio_groups,

        "cache_hit": False

    }





# ==============================================================================

# PHASE 2: RAG MAPPER (with cache support)

# ==============================================================================



async def run_rag_api_mapper(

    extracted_json_path: str,

    headers_file_path: str,

    storage_config: Any,

    user_id: int,

    pdf_doc_id: int,

    session_id: Optional[int],

    pdf_hash: Optional[str],

    cache_registry_path: str,

    notifier: Optional[Any] = None

) -> Dict[str, Any]:

    """

    Run RAG mapper (Phase 2) - always calls RAG API (NOT cached).

    

    Returns rag_predictions.json path (RAG API output format).

    

    Cache strategy:

    - RAG predictions are NOT cached (always fresh API call)

    - Only semantic mapping + headers are cached in Phase 1

    - This ensures RAG predictions reflect latest embeddings/models

    

    Output format (rag_predictions.json):

        {

            "user_id": "553",

            "session_id": "...",

            "model": "rag",

            "predictions": {

                "field_8": {

                    "predicted_field_name": "investormailingaddressline1_ID",

                    "confidence": 0.858,

                    "vector_id": "vec_023",

                    "top_k": [...]

                }

            }

        }

    

    Args:

        extracted_json_path: Path to extracted JSON

        headers_file_path: Path to final_form_fields.json (required by RAG API)

        storage_config: Storage configuration object

        user_id, pdf_doc_id, session_id: IDs for tracking

        pdf_hash: PDF content hash (not used for RAG cache)

        cache_registry_path: Path to cache registry (not used for RAG)

        notifier: Optional notification system

    

    Returns:

        {

            "rag_predictions_path": str,    # Path to rag_predictions.json

            "dest_rag_predictions": str,    # Destination path (for optional cache registration)

            "success": bool,                # Whether RAG API call succeeded

            "error": str                    # Error message if failed

        }

    """

    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

    import os

    

    logger.info("=" * 80)

    logger.info("PHASE 2: RAG API MAPPER (always calls RAG API - not cached)")

    logger.info("=" * 80)

    

    # RAG predictions are NOT cached - always call RAG API fresh

    # (Only semantic mapping + headers are cached in Phase 1)

    logger.info("📞 Calling RAG API (predictions not cached, always fresh)...")

    

    try:

        # Convert session_id to string if needed (RAG API expects string)

        session_id_str = str(session_id) if session_id else None

        

        # Call RAG API (existing function - requires headers_file_path)

        rag_predictions_path = await call_rag_api(

            user_id=user_id,

            pdf_doc_id=pdf_doc_id,

            headers_file_path=headers_file_path,  # Path to final_form_fields.json

            extracted_json_path=extracted_json_path,

            pdf_hash=pdf_hash,

            storage_config=storage_config,  # FIXED: Added missing parameter

            session_id=session_id_str

        )



        print(f"RAG API returned predictions path: {rag_predictions_path}")

        

        if not rag_predictions_path or not os.path.exists(rag_predictions_path):

            logger.warning("❌ RAG API did not return valid predictions file")

            return {

                "rag_predictions_path": None,

                "dest_rag_predictions": None,

                "success": False,

                "error": "RAG API returned no file"

            }

        

        logger.info(f"✅ RAG API completed: {rag_predictions_path}")

        

        # Save to destination storage

        output_handler = OutputFileHandler(storage_config)

        dest_rag_predictions = output_handler.save_output(rag_predictions_path, 'rag_predictions_json')

        

        if dest_rag_predictions:

            logger.info(f"📤 Uploaded RAG predictions to: {dest_rag_predictions}")

        

        return {

            "rag_predictions_path": rag_predictions_path,

            "dest_rag_predictions": dest_rag_predictions,

            "success": True,

            "error": None

        }

        

    except Exception as rag_error:

        logger.error(f"❌ RAG API failed: {rag_error}")

        return {

            "rag_predictions_path": None,

            "dest_rag_predictions": None,

            "success": False,

            "error": str(rag_error)

        }





async def handle_make_embed_file_operation(

    config: Any,

    user_id: int,

    pdf_doc_id: int,

    session_id: Optional[int] = None,

    investor_type: str = 'individual',

    mapping_config: Optional[dict] = None,

    use_second_mapper: bool = False,

    notifier: Optional[Any] = None

) -> Dict[str, Any]:

    """

    Make embed file operation - runs extract -> map -> embed pipeline (without fill).

    Uses local file paths from config object (downloaded by AWS handler).

    

    This creates an embedded PDF ready to be filled later.

    

    Args:

        config: Storage config with local file paths already set

        user_id: User ID (required)

        pdf_doc_id: PDF document ID (required)

        session_id: Optional session ID for tracking

        investor_type: Investor type for mapping (default: 'individual')

        mapping_config: Optional mapping configuration

        use_second_mapper: Whether to use second mapper (default: False)

        notifier: Optional notification system

    """

    start_time = time.time()

    

    logger.info("=" * 80)

    logger.info("MAKE EMBED FILE OPERATION - Partial Pipeline (Extract -> Map -> Embed)")

    logger.info("=" * 80)

    logger.info(f"User ID: {user_id}, PDF Doc ID: {pdf_doc_id}")

    logger.info(f"Session ID: {session_id}, Investor Type: {investor_type}")

    logger.info(f"🔀 Use Second Mapper (RAG): {use_second_mapper}")

    

    try:

        import json

        import os

        import tempfile

        

        # Store pdf_doc_id on config for structured output paths (if output_base_path is set)

        if hasattr(config, 'output_base_path') and config.output_base_path:

            config.pdf_doc_id = pdf_doc_id

        

        # Get S3 source paths for operations (NOT local paths)

        # Operations will download/upload using these S3 paths

        input_pdf_s3 = config.s3_input_pdf if hasattr(config, 's3_input_pdf') and config.s3_input_pdf else config.local_input_pdf

        input_json_s3 = (config.s3_global_json if hasattr(config, 's3_global_json') and config.s3_global_json 

                        else config.s3_input_json if hasattr(config, 's3_input_json') and config.s3_input_json

                        else getattr(config, 'local_global_json', None) or config.local_input_json)

        

        if not input_pdf_s3:

            raise ValueError("config.s3_input_pdf or local_input_pdf not set")

        if not input_json_s3:

            raise ValueError("config.s3_global_json/s3_input_json or local_input_json not set")

        

        # Debug: Check if we're using S3 paths or local paths

        if not input_pdf_s3.startswith('s3://'):

            logger.info(f"ℹ️  Using LOCAL path for testing: {input_pdf_s3}")

            logger.debug("(Set config.s3_input_pdf when deploying to Lambda)")

        if not input_json_s3.startswith('s3://'):

            logger.info(f"ℹ️  Using LOCAL path for testing: {input_json_s3}")

            logger.debug("(Set config.s3_input_json when deploying to Lambda)")

        

        logger.info(f"Input PDF: {input_pdf_s3}")

        logger.info(f"Input JSON: {input_json_s3}")

        

        storage_type = config.source_type

        logger.info(f"Storage type: {storage_type}")

        

        # For local storage, use pre-configured paths from LocalStorageConfig

        # For cloud storage, we still need file_config for path generation

        if storage_type == 'local':

            # Local deployment: entrypoint already set all paths in config.local_*

            logger.info("Using pre-configured local paths from LocalStorageConfig")

            file_config = None

        elif hasattr(config, 'output_base_path') and config.output_base_path:

            # Cloud deployment: generate structured output paths

            logger.info(f"Using structured output directory: {config.output_base_path}")

            file_config = config.get_complete_file_config(input_pdf_s3, user_id=user_id, session_id=session_id)

        else:

            file_config = None

        

        pipeline_results = {}

        

        # Stage 1: Extract

        logger.info("\n" + "=" * 80)

        logger.info("[1/3] EXTRACTION STAGE")

        logger.info("=" * 80)

        

        # Check if entry point already extracted (for hash check)

        if hasattr(config, 'cached_extraction') and config.cached_extraction:

            logger.info("[Cache] ✅ Using cached extraction from entry point (saves ~5s)")

            extract_result = config.cached_extraction

            

            # Save to file using configured path

            if storage_type == 'local' and hasattr(config, 'local_extracted_json'):

                # Local: use pre-configured path

                extracted_json = config.local_extracted_json

                os.makedirs(os.path.dirname(extracted_json), exist_ok=True)

                with open(extracted_json, 'w') as f:

                    json.dump(extract_result.get('extracted_data', {}), f, indent=2)

                extract_result["output_file"] = extracted_json

                logger.info(f"Saved cached extraction to: {extracted_json}")

            elif file_config:

                # Cloud: use generated structured output path

                extracted_json = file_config["extraction_output_path"]

                os.makedirs(os.path.dirname(extracted_json), exist_ok=True)

                with open(extracted_json, 'w') as f:

                    json.dump(extract_result.get('extracted_data', {}), f, indent=2)

                extract_result["output_file"] = extracted_json

                logger.info(f"Saved cached extraction to: {extracted_json}")

            else:

                # Fallback: Create temp file for extraction

                temp_extract = tempfile.NamedTemporaryFile(mode='w', suffix='_extracted.json', delete=False)

                json.dump(extract_result.get('extracted_data', {}), temp_extract, indent=2)

                temp_extract.close()

                extracted_json = temp_extract.name

                extract_result["output_file"] = extracted_json

                logger.info(f"Saved cached extraction to temp: {extracted_json}")

        else:

            # Run full extraction

            extract_result = await handle_extract_operation(

                config=config,  # Pass config instead of file paths

                user_id=user_id,

                session_id=session_id,

                notifier=notifier,

                pdf_doc_id=pdf_doc_id,

                input_json_doc_id=None,

                input_json_path=input_json_s3,  # Still pass for pre-map estimation

                mapping_config=mapping_config

            )

            extracted_json = extract_result["output_file"]

        

        pipeline_results["extract"] = extract_result

        

        # Track original path BEFORE any moving (for caching)

        original_extracted_json = extracted_json

        

        # If using structured output, move file to proper directory (cloud only)

        if file_config and storage_type != 'local':

            expected_path = file_config["extraction"]["extracted_path"]

            if extracted_json != expected_path:

                logger.info(f"Moving extracted file to structured output: {expected_path}")

                os.makedirs(os.path.dirname(expected_path), exist_ok=True)

                shutil.move(extracted_json, expected_path)

                extracted_json = expected_path

                extract_result["output_file"] = expected_path

        

        # Store both S3 and local paths

        if hasattr(config, 's3_extracted_json'):

            config.s3_extracted_json = extracted_json

        logger.info(f"✅ EXTRACT completed: {extracted_json}")

        

        # Get PDF hash from extraction result

        pdf_hash = extract_result.get('pdf_hash')

        if pdf_hash:

            logger.info(f"PDF fingerprint hash for pdf_doc_id={pdf_doc_id}: {pdf_hash[:16]}...")

        else:

            logger.warning(f"PDF hash not available for caching (pdf_doc_id={pdf_doc_id})")

        

        # CHECK HASH CACHE - Skip MAP if we've processed this PDF structure before

        from pdf_autofillr_mapper.core.config import settings

        from pdf_autofillr_mapper.utils.hash_cache import check_hash_cache, save_hash_cache, copy_cached_files

        

        pdf_cache_enabled = getattr(settings, 'pdf_cache_enabled', True)

        cache_result = None

        cache_hit = False

        

        # Get cache registry path directly from config.ini

        cache_registry_path = settings.cache_registry_path

        if not cache_registry_path:

            # Fallback to default local path if not configured

            cache_registry_path = os.path.join(settings.data_output_dir, 'cache', 'hash_registry.json')

            logger.debug(f"No cache_registry_path in config, using default: {cache_registry_path}")

        

        # Initialize variables for dual mapper (needed in all code paths)

        semantic_mapping_path = None

        pdf_category = None

        headers_with_fields_path = None

        final_form_fields_path = None

        combined_mapping_path = None

        llm_predictions_path = None

        rag_predictions_path = None

        rag_api_failed = False

        rag_failure_reason = None

        

        # Initialize destination path variables for cache registration

        dest_semantic_mapping = None

        dest_radio_groups = None

        dest_embedded_pdf = None

        dest_headers_with_fields = None

        dest_final_form_fields = None

        

        # Stage 2: Mapping (with cache check)

        logger.info("\n" + "=" * 80)

        logger.info("[2/3] MAPPING STAGE")

        logger.info("=" * 80)

        logger.info(f"🔀 Use second mapper (RAG): {use_second_mapper}")

        

        if pdf_cache_enabled and pdf_hash:

            try:

                logger.info(f"🔍 Checking hash cache at: {cache_registry_path}")

                # Ensure cache directory exists (for local paths)

                if not cache_registry_path.startswith(('s3://', 'gs://', 'azure://')):

                    os.makedirs(os.path.dirname(cache_registry_path), exist_ok=True)

                cache_result = await check_hash_cache(pdf_hash, cache_registry_path)

                

                # IMPORTANT: Persist updated cache registry after check (usage stats were updated)

                if cache_result and os.path.exists(cache_registry_path):

                    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                    cache_output_handler = OutputFileHandler(config)

                    cache_dest = cache_output_handler.save_output(

                        cache_registry_path, 

                        'cache_registry_json'

                    )

                    if cache_dest:

                        logger.info(f"📤 Cache registry updated and persisted to: {cache_dest}")

                    else:

                        logger.debug("Cache registry persisted (local mode)")

            except Exception as cache_error:

                logger.warning(f"Cache check failed: {cache_error}. Proceeding with normal MAP operation.")

        

        # If CACHE HIT: Use cached semantic mapping

        if cache_result:

            logger.info(f"🎯 CACHE HIT! Using cached semantic mapping (saves ~45s + LLM costs)")

            cache_hit = True

            

            try:

                # Get cached files from entrypoint or copy them

                if config.cached_mapping_json and config.cached_radio_groups:

                    semantic_mapping_path = config.cached_mapping_json

                    radio_groups = config.cached_radio_groups

                    logger.info(f"✅ Using cached files from entrypoint")

                else:

                    target_dir = os.path.dirname(extracted_json)

                    copied_files = await copy_cached_files(

                        source_files=cache_result["reference_files"],

                        target_dir=target_dir

                    )

                    semantic_mapping_path = copied_files.get("mapping_json")

                    radio_groups = copied_files.get("radio_groups")

                    logger.info(f"✅ Copied cached files to: {target_dir}")

                

                logger.info(f"   Semantic mapping: {semantic_mapping_path}")

                logger.info(f"   Radio groups: {radio_groups}")

                

                # Get embedded_pdf path from cache (needed for Phase 2 caching)

                embedded_pdf = cache_result["reference_files"].get("embedded_pdf")

                

                # Also get dest paths from cache_result for Phase 2 caching

                dest_embedded_pdf = cache_result["reference_files"].get("embedded_pdf")

                dest_semantic_mapping = cache_result["reference_files"].get("mapping_json")

                dest_radio_groups = cache_result["reference_files"].get("radio_groups")

                

                # Get cached headers if available (for dual mapper)

                # Check cache_result first (from hash registry), then config (from entrypoint)

                cached_headers_from_registry = cache_result["reference_files"].get("headers_with_fields")

                cached_final_fields_from_registry = cache_result["reference_files"].get("final_form_fields")

                

                logger.info(f"🔍 DEBUG: Checking Phase 2 cache:")

                logger.info(f"   cached_headers_from_registry: {cached_headers_from_registry}")

                logger.info(f"   cached_final_fields_from_registry: {cached_final_fields_from_registry}")

                logger.info(f"   config.cached_headers_with_fields: {getattr(config, 'cached_headers_with_fields', None)}")

                logger.info(f"   config.cached_final_form_fields: {getattr(config, 'cached_final_form_fields', None)}")

                

                headers_with_fields_path = (

                    config.cached_headers_with_fields if hasattr(config, 'cached_headers_with_fields') and config.cached_headers_with_fields

                    else cached_headers_from_registry

                )

                final_form_fields_path = (

                    config.cached_final_form_fields if hasattr(config, 'cached_final_form_fields') and config.cached_final_form_fields

                    else cached_final_fields_from_registry

                )

                

                logger.info(f"   Final headers_with_fields_path: {headers_with_fields_path}")

                logger.info(f"   Final final_form_fields_path: {final_form_fields_path}")

                

                # Track if we need to cache Phase 2 (headers just created)

                phase2_needs_caching = False

                

                # Phase 2: RAG Mapper (if enabled)

                if use_second_mapper:

                    # If headers not cached, extract them now

                    if not headers_with_fields_path or not final_form_fields_path:

                        phase2_needs_caching = True  # Mark that headers will be freshly created

                        logger.info("\n" + "-" * 80)

                        logger.info("MAPPER PHASE 2: RAG API Mapper - Extracting Headers")

                        logger.info("-" * 80)

                        logger.info("📝 Headers not cached, extracting headers for RAG API...")

                        

                        # from pdf_autofillr_mapper.headers import get_form_fields_points
                        from pdf_autofillr_mapper.headers.get_form_fields_points import get_form_fields_points

                        

                        # Get header file paths from config

                        if storage_type == 'local' and hasattr(config, 'local_headers_with_fields'):

                            headers_output_path = config.local_headers_with_fields

                            final_fields_output_path = config.local_final_form_fields

                        elif file_config and "headers" in file_config:

                            headers_output_path = file_config["headers"]["headers_with_fields_path"]

                            final_fields_output_path = file_config["headers"]["final_form_fields_path"]

                        else:

                            raise ValueError("Missing header paths configuration")

                        

                        headers_result = await get_form_fields_points(

                            extracted_json_path=extracted_json,

                            headers_output_path=headers_output_path,

                            final_fields_output_path=final_fields_output_path

                        )

                        

                        headers_with_fields_path = headers_output_path

                        final_form_fields_path = final_fields_output_path

                        pdf_category = headers_result.get("pdf_category")

                        

                        # Upload header files to source storage

                        from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                        output_handler = OutputFileHandler(config)

                        dest_headers_with_fields = output_handler.save_output(headers_with_fields_path, 'headers_with_fields_json')

                        dest_final_form_fields = output_handler.save_output(final_form_fields_path, 'final_form_fields_json')

                        

                        if dest_headers_with_fields:

                            logger.info(f"📤 Uploaded headers_with_fields to: {dest_headers_with_fields}")

                        if dest_final_form_fields:

                            logger.info(f"📤 Uploaded final_form_fields to: {dest_final_form_fields}")

                        

                        logger.info(f"✅ Headers extracted: {final_form_fields_path}")

                        if pdf_category:

                            logger.info(f"� PDF Category: {pdf_category}")

                        

                        # CACHE PHASE 2 RESULTS immediately after headers extraction completes

                        # This updates the existing cache entry with headers_with_fields and final_form_fields

                        if pdf_hash and phase2_needs_caching:

                            try:

                                from pdf_autofillr_mapper.utils.hash_cache import save_hash_cache

                                from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                                

                                logger.info("💾 Updating cache with Phase 2 results (headers_with_fields + final_form_fields)...")

                                

                                # Use destination paths for cache (persistent storage)

                                cache_headers = dest_headers_with_fields if dest_headers_with_fields else headers_with_fields_path

                                cache_final_fields = dest_final_form_fields if dest_final_form_fields else final_form_fields_path

                                

                                # Get cached Phase 1 paths (embedded_pdf, mapping, radio were already cached)

                                cache_mapping = dest_semantic_mapping if dest_semantic_mapping else semantic_mapping_path

                                cache_radio = dest_radio_groups if dest_radio_groups else radio_groups

                                cache_embedded = dest_embedded_pdf if dest_embedded_pdf else embedded_pdf

                                

                                await save_hash_cache(

                                    pdf_hash=pdf_hash,

                                    cache_registry_path=cache_registry_path,

                                    embedded_pdf=cache_embedded,

                                    mapping_json=cache_mapping,

                                    radio_groups=cache_radio,

                                    user_id=user_id,

                                    pdf_doc_id=pdf_doc_id,

                                    headers_with_fields=cache_headers,

                                    final_form_fields=cache_final_fields,

                                    pdf_category=pdf_category

                                )

                                logger.info("✅ Phase 2 cached locally")

                                

                                # IMPORTANT: Upload cache registry to source storage so it persists

                                if os.path.exists(cache_registry_path):

                                    cache_output_handler = OutputFileHandler(config)

                                    cache_dest = cache_output_handler.save_output(

                                        cache_registry_path, 

                                        'cache_registry_json'

                                    )

                                    if cache_dest:

                                        logger.info(f"📤 Cache registry persisted to: {cache_dest}")

                                    else:

                                        logger.warning("⚠️  Cache registry not uploaded (local storage mode)")

                                

                                logger.info("✅ Phase 2 cached: headers_with_fields, final_form_fields")

                            except Exception as cache_error:

                                logger.warning(f"Failed to cache Phase 2 results: {cache_error}. Continuing anyway.")

                        elif not phase2_needs_caching:

                            logger.info("⏭️  Phase 2 already cached - skipping cache update")

                        else:

                            logger.info("⚠️  No pdf_hash available, skipping Phase 2 cache")

                    else:

                        logger.info("\n" + "-" * 80)

                        logger.info("MAPPER PHASE 2: RAG API Mapper - Using Cached Headers")

                        logger.info("-" * 80)

                        logger.info("🔀 Using cached headers from cache registry")

                        

                        # Copy cached header files to processing directory if needed

                        if headers_with_fields_path and final_form_fields_path:

                            # If paths point to source storage, download to processing

                            if not headers_with_fields_path.startswith('/tmp/processing'):

                                from pdf_autofillr_mapper.handlers.input_handler import InputFileHandler

                                input_handler = InputFileHandler(config)

                                

                                # Get processing paths from config

                                if storage_type == 'local' and hasattr(config, 'local_headers_with_fields'):

                                    processing_headers_path = config.local_headers_with_fields

                                    processing_final_fields_path = config.local_final_form_fields

                                elif file_config and "headers" in file_config:

                                    processing_headers_path = file_config["headers"]["headers_with_fields_path"]

                                    processing_final_fields_path = file_config["headers"]["final_form_fields_path"]

                                else:

                                    raise ValueError("Missing header paths configuration")

                                

                                # Download files from source to processing using InputFileHandler

                                downloaded_headers = input_handler.download_input(headers_with_fields_path, processing_headers_path)

                                logger.info(f"📥 Downloaded cached headers to: {downloaded_headers}")

                                

                                downloaded_final_fields = input_handler.download_input(final_form_fields_path, processing_final_fields_path)

                                logger.info(f"📥 Downloaded cached final_form_fields to: {downloaded_final_fields}")

                                

                                # Update paths to processing directory

                                headers_with_fields_path = downloaded_headers

                                final_form_fields_path = downloaded_final_fields

                            

                            logger.info(f"   Headers: {headers_with_fields_path}")

                            logger.info(f"   Final fields: {final_form_fields_path}")

                        

                        pdf_category = cache_result.get("pdf_category")

                    

                    # Call RAG mapper (with its own cache check)

                    rag_result = await run_rag_api_mapper(

                        extracted_json_path=extracted_json,

                        headers_file_path=final_form_fields_path,

                        storage_config=config,

                        user_id=user_id,

                        pdf_doc_id=pdf_doc_id,

                        session_id=session_id,

                        pdf_hash=pdf_hash,

                        cache_registry_path=cache_registry_path,

                        notifier=notifier

                    )

                    

                    if rag_result["success"]:

                        logger.info(f"✅ RAG predictions: {rag_result['rag_predictions_path']}")

                        rag_predictions_path = rag_result["rag_predictions_path"]

                        

                        # Save LLM predictions (from semantic mapping) for comparison

                        logger.info("📋 Saving LLM predictions for comparison...")

                        llm_predictions_path = await save_llm_predictions_to_rag_bucket(

                            semantic_mapping_path=semantic_mapping_path,

                            user_id=user_id,

                            pdf_doc_id=pdf_doc_id,

                            storage_config=config,

                            session_id=session_id

                        )

                        

                        # Upload LLM predictions to source storage

                        from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                        output_handler = OutputFileHandler(config)

                        dest_llm_predictions = output_handler.save_output(llm_predictions_path, 'llm_predictions_json')

                        logger.info(f"✅ LLM predictions saved and uploaded")

                        logger.info(f"   Local: {llm_predictions_path}")

                        logger.info(f"   Uploaded: {dest_llm_predictions}")

                        

                        # Combine semantic + RAG

                        logger.info("🔄 Combining semantic + RAG predictions...")

                        mapping_json, combined_mapping_path = await combine_mappings(

                            semantic_mapping_path=semantic_mapping_path,

                            rag_predictions_path=rag_predictions_path,

                            user_id=user_id,

                            pdf_doc_id=pdf_doc_id,

                            storage_config=config,

                            session_id=session_id

                        )

                        logger.info(f"✅ Combined mapping created")

                        

                        # Upload java mapping and final predictions to source storage

                        output_handler = OutputFileHandler(config)

                        saved_java_mapping = output_handler.save_output(mapping_json, 'java_mapping_json')

                        saved_final_predictions = output_handler.save_output(combined_mapping_path, 'final_predictions_json')

                        logger.info(f"📤 Uploaded Java mapping to: {saved_java_mapping}")

                        logger.info(f"📤 Uploaded final predictions to: {saved_final_predictions}")

                        

                        rag_api_failed = False

                    else:

                        logger.warning(f"RAG failed: {rag_result['error']}, using semantic only")

                        mapping_json = await convert_semantic_to_java_format(

                            semantic_mapping_path=semantic_mapping_path,

                            user_id=user_id,

                            pdf_doc_id=pdf_doc_id,

                            storage_config=config

                        )

                        

                        # Upload java mapping to source storage

                        from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                        output_handler = OutputFileHandler(config)

                        saved_java_mapping = output_handler.save_output(mapping_json, 'java_mapping_json')

                        logger.info(f"📤 Uploaded Java mapping to: {saved_java_mapping}")

                        

                        rag_api_failed = True

                        rag_failure_reason = rag_result['error']

                        rag_predictions_path = None

                else:

                    # Semantic mapper only - convert cached semantic to Java format

                    logger.info("🔄 Converting cached semantic mapping to Java format...")

                    mapping_json = await convert_semantic_to_java_format(

                        semantic_mapping_path=semantic_mapping_path,

                        user_id=user_id,

                        pdf_doc_id=pdf_doc_id,

                        storage_config=config

                    )

                    

                    # Upload java mapping to source storage

                    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                    output_handler = OutputFileHandler(config)

                    saved_java_mapping = output_handler.save_output(mapping_json, 'java_mapping_json')

                    logger.info(f"📤 Uploaded Java mapping to: {saved_java_mapping}")

                

                # Update config paths for embed operation

                config.local_mapped_json = mapping_json

                config.local_radio_json = radio_groups

                

                logger.info(f"✅ Cache processed. MAP stage skipped.")

                

            except Exception as cache_error:

                logger.error(f"Failed to process cached files: {cache_error}. Running MAP stage.")

                cache_hit = False

        

        # Stage 2: Map (only if cache miss)

        if not cache_hit:

            # CACHE MISS: Run MAP stage

            if pdf_hash:

                logger.info(f"📭 CACHE MISS. Running semantic mapper...")

            else:

                logger.info("📭 No PDF hash available. Running semantic mapper...")

            

            # Phase 1: Semantic Mapper (with cache check)

            logger.info("\n" + "-" * 80)

            logger.info("MAPPER PHASE 1: Semantic API Mapper")

            logger.info("-" * 80)

            

            semantic_result = await run_semantic_api_mapper(

                extracted_json_path=extracted_json,

                input_json_path=input_json_s3,

                storage_config=config,

                user_id=user_id,

                pdf_doc_id=pdf_doc_id,

                session_id=session_id,

                pdf_hash=pdf_hash,

                cache_registry_path=cache_registry_path,

                investor_type=investor_type,

                mapping_config=mapping_config,

                notifier=notifier

            )

            

            semantic_mapping_path = semantic_result["semantic_mapping_path"]

            radio_groups = semantic_result["radio_groups_path"]

            dest_semantic_mapping = semantic_result["dest_semantic_mapping"]

            dest_radio_groups = semantic_result["dest_radio_groups"]

            

            logger.info(f"✅ Semantic mapper completed")

            logger.info(f"   Semantic mapping: {semantic_mapping_path}")

            logger.info(f"   Radio groups: {radio_groups}")

            

            # Phase 2: RAG Mapper (optional - if use_second_mapper is True)

            if use_second_mapper:

                logger.info("\n" + "-" * 80)

                logger.info("MAPPER PHASE 2: RAG API Mapper")

                logger.info("-" * 80)

                

                # First, extract headers (required by RAG API)

                # from pdf_autofillr_mapper.headers import get_form_fields_points
                from pdf_autofillr_mapper.headers.get_form_fields_points import get_form_fields_points

                

                # Get header file paths from config (use existing config.ini patterns)

                if storage_type == 'local' and hasattr(config, 'local_headers_with_fields'):

                    headers_output_path = config.local_headers_with_fields

                    final_fields_output_path = config.local_final_form_fields

                elif file_config and "headers" in file_config:

                    headers_output_path = file_config["headers"]["headers_with_fields_path"]

                    final_fields_output_path = file_config["headers"]["final_form_fields_path"]

                else:

                    raise ValueError("Missing header paths configuration")

                

                logger.info("📝 Extracting headers for RAG API...")

                headers_result = await get_form_fields_points(

                    extracted_json_path=extracted_json,

                    headers_output_path=headers_output_path,

                    final_fields_output_path=final_fields_output_path

                )

                

                headers_with_fields_path = headers_output_path

                final_form_fields_path = final_fields_output_path

                pdf_category = headers_result.get("pdf_category")

                

                logger.info(f"✅ Headers extracted: {final_form_fields_path}")

                if pdf_category:

                    logger.info(f"📋 PDF Category: {pdf_category}")

                

                # Upload header files to source storage

                from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                output_handler = OutputFileHandler(config)

                dest_headers_with_fields = output_handler.save_output(headers_with_fields_path, 'headers_with_fields_json')

                dest_final_form_fields = output_handler.save_output(final_form_fields_path, 'final_form_fields_json')

                

                if dest_headers_with_fields:

                    logger.info(f"📤 Uploaded headers to: {dest_headers_with_fields}")

                if dest_final_form_fields:

                    logger.info(f"📤 Uploaded final fields to: {dest_final_form_fields}")

                

                # CACHE PHASE 2 RESULTS immediately after headers extraction completes

                # This updates the existing cache entry with headers_with_fields and final_form_fields

                if pdf_hash and not cache_hit:

                    try:

                        from pdf_autofillr_mapper.utils.hash_cache import save_hash_cache

                        from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                        

                        logger.info("💾 Updating cache with Phase 2 results (headers_with_fields + final_form_fields)...")

                        

                        # Use destination paths for cache (persistent storage)

                        cache_headers = dest_headers_with_fields if dest_headers_with_fields else headers_with_fields_path

                        cache_final_fields = dest_final_form_fields if dest_final_form_fields else final_form_fields_path

                        

                        # Get cached Phase 1 paths (embedded_pdf, mapping, radio were already cached)

                        cache_mapping = dest_semantic_mapping if dest_semantic_mapping else semantic_mapping_path

                        cache_radio = dest_radio_groups if dest_radio_groups else radio_groups

                        cache_embedded = dest_embedded_pdf if dest_embedded_pdf else embedded_pdf

                        

                        await save_hash_cache(

                            pdf_hash=pdf_hash,

                            cache_registry_path=cache_registry_path,

                            embedded_pdf=cache_embedded,

                            mapping_json=cache_mapping,

                            radio_groups=cache_radio,

                            user_id=user_id,

                            pdf_doc_id=pdf_doc_id,

                            headers_with_fields=cache_headers,

                            final_form_fields=cache_final_fields,

                            pdf_category=pdf_category

                        )

                        logger.info("✅ Phase 2 cached locally")

                        

                        # IMPORTANT: Upload cache registry to source storage so it persists

                        if os.path.exists(cache_registry_path):

                            cache_output_handler = OutputFileHandler(config)

                            cache_dest = cache_output_handler.save_output(

                                cache_registry_path, 

                                'cache_registry_json'

                            )

                            if cache_dest:

                                logger.info(f"📤 Cache registry persisted to: {cache_dest}")

                            else:

                                logger.warning("⚠️  Cache registry not uploaded (local storage mode)")

                        

                        logger.info("✅ Phase 2 cached: headers_with_fields, final_form_fields")

                    except Exception as cache_error:

                        logger.warning(f"Failed to cache Phase 2 results: {cache_error}. Continuing anyway.")

                elif cache_hit:

                    logger.info("⏭️  Cache hit - skipping Phase 2 cache update")

                else:

                    logger.info("⚠️  No pdf_hash available, skipping Phase 2 cache")

                

                # Now call RAG mapper with cache check

                rag_result = await run_rag_api_mapper(

                    extracted_json_path=extracted_json,

                    headers_file_path=final_form_fields_path,

                    storage_config=config,

                    user_id=user_id,

                    pdf_doc_id=pdf_doc_id,

                    session_id=session_id,

                    pdf_hash=pdf_hash,

                    cache_registry_path=cache_registry_path,

                    notifier=notifier

                )

                

                if rag_result["success"]:

                    logger.info(f"✅ RAG mapper completed: {rag_result['rag_predictions_path']}")

                    rag_predictions_path = rag_result["rag_predictions_path"]

                    dest_rag_predictions = rag_result["dest_rag_predictions"]

                    

                    # Save LLM predictions (from semantic mapping) for comparison

                    logger.info("📋 Saving LLM predictions for comparison...")

                    llm_predictions_path = await save_llm_predictions_to_rag_bucket(

                        semantic_mapping_path=semantic_mapping_path,

                        user_id=user_id,

                        pdf_doc_id=pdf_doc_id,

                        storage_config=config,

                        session_id=session_id

                    )

                    

                    # Upload LLM predictions to source storage

                    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                    output_handler = OutputFileHandler(config)

                    dest_llm_predictions = output_handler.save_output(llm_predictions_path, 'llm_predictions_json')

                    logger.info(f"✅ LLM predictions saved and uploaded")

                    logger.info(f"   Local: {llm_predictions_path}")

                    logger.info(f"   Uploaded: {dest_llm_predictions}")

                    

                    # Combine semantic + RAG predictions

                    logger.info("🔄 Combining semantic + RAG predictions...")

                    mapping_json, combined_mapping_path = await combine_mappings(

                        semantic_mapping_path=semantic_mapping_path,

                        rag_predictions_path=rag_predictions_path,

                        user_id=user_id,

                        pdf_doc_id=pdf_doc_id,

                        storage_config=config,

                        session_id=session_id

                    )

                    

                    # Upload java mapping and final predictions to source storage

                    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                    output_handler = OutputFileHandler(config)

                    saved_java_mapping = output_handler.save_output(mapping_json, 'java_mapping_json')

                    saved_final_predictions = output_handler.save_output(combined_mapping_path, 'final_predictions_json')

                    logger.info(f"📤 Uploaded Java mapping to: {saved_java_mapping}")

                    logger.info(f"📤 Uploaded final predictions to: {saved_final_predictions}")

                    

                    logger.info(f"✅ Combined mapping created (Java format): {mapping_json}")

                    rag_api_failed = False

                else:

                    logger.warning(f"❌ RAG mapper failed: {rag_result['error']}")

                    logger.info("� Falling back to semantic mapping only")

                    

                    rag_api_failed = True

                    rag_failure_reason = rag_result['error']

                    rag_predictions_path = None

                    dest_rag_predictions = None

                    

                    # Convert semantic to Java format

                    mapping_json = await convert_semantic_to_java_format(

                        semantic_mapping_path=semantic_mapping_path,

                        user_id=user_id,

                        pdf_doc_id=pdf_doc_id,

                        storage_config=config

                    )

                    

                    # Upload java mapping to source storage

                    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                    output_handler = OutputFileHandler(config)

                    saved_java_mapping = output_handler.save_output(mapping_json, 'java_mapping_json')

                    logger.info(f"📤 Uploaded Java mapping to: {saved_java_mapping}")

            else:

                # Semantic mapper only - convert to Java format

                logger.info("🔄 Converting semantic mapping to Java format...")

                mapping_json = await convert_semantic_to_java_format(

                    semantic_mapping_path=semantic_mapping_path,

                    user_id=user_id,

                    pdf_doc_id=pdf_doc_id,

                    storage_config=config

                )

                

                # Upload java mapping to source storage

                from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                output_handler = OutputFileHandler(config)

                saved_java_mapping = output_handler.save_output(mapping_json, 'java_mapping_json')

                logger.info(f"📤 Uploaded Java mapping to: {saved_java_mapping}")

                

                rag_api_failed = False

                rag_predictions_path = None

                dest_rag_predictions = None

        

        # Store map result for pipeline tracking

        pipeline_results["map"] = {

            "mapping_path": mapping_json,

            "radio_groups_path": radio_groups,

            "semantic_mapping_path": semantic_mapping_path,

            "combined_mapping_path": combined_mapping_path if use_second_mapper and not rag_api_failed else None,

            "pdf_category": pdf_category if use_second_mapper else None,

            "use_second_mapper": use_second_mapper,

            "rag_api_failed": rag_api_failed if use_second_mapper else None,

            "rag_failure_reason": rag_failure_reason if use_second_mapper and rag_api_failed else None

        }

        

        # Store S3 paths

        if hasattr(config, 's3_mapped_json'):

            config.s3_mapped_json = mapping_json

            config.s3_radio_json = radio_groups

        

        # Track original paths BEFORE any moving (for caching)

        original_mapping_json = mapping_json

        original_radio_groups = radio_groups

        

        # If using structured output, move files to proper directory (cloud only, local paths already correct)

        if file_config and storage_type != 'local':

            expected_mapping_path = file_config["mapping"]["mapping_path"]

            expected_radio_path = file_config["mapping"]["radio_groups_path"]

            

            if mapping_json != expected_mapping_path:

                logger.info(f"Moving mapping file to structured output: {expected_mapping_path}")

                os.makedirs(os.path.dirname(expected_mapping_path), exist_ok=True)

                shutil.move(mapping_json, expected_mapping_path)

                mapping_json = expected_mapping_path

                pipeline_results["map"]["mapping_path"] = expected_mapping_path

            

            if radio_groups != expected_radio_path:

                logger.info(f"Moving radio groups to structured output: {expected_radio_path}")

                os.makedirs(os.path.dirname(expected_radio_path), exist_ok=True)

                shutil.move(radio_groups, expected_radio_path)

                radio_groups = expected_radio_path

                pipeline_results["map"]["radio_groups_path"] = expected_radio_path

        

        logger.info(f"✅ MAP completed: {mapping_json}")

        

        # Stage 3: Embed

        logger.info("\n" + "=" * 80)

        logger.info("[3/3] EMBEDDING STAGE")

        logger.info("=" * 80)

        

        embed_result = await handle_embed_operation(

            config=config,  # Pass config instead of file paths

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id

        )

        pipeline_results["embed"] = embed_result

        embedded_pdf = embed_result["output_file"]

        

        # Extract DESTINATION path for cache registration (where file was saved)

        dest_embedded_pdf = embed_result.get("dest_output_file")

        

        logger.info(f"🔍 DEBUG: Extracted destination paths for cache:")

        logger.info(f"   dest_embedded_pdf: {dest_embedded_pdf}")

        logger.info(f"   dest_semantic_mapping: {dest_semantic_mapping}")

        logger.info(f"   dest_radio_groups: {dest_radio_groups}")

        

        # Track original path BEFORE any moving (for caching)

        original_embedded_pdf = embedded_pdf

        

        # If using structured output, move file to proper directory (cloud only, local paths already correct)

        if file_config and storage_type != 'local':

            expected_embedded_path = file_config["embedding"]["embedded_pdf_path"]

            if embedded_pdf != expected_embedded_path:

                logger.info(f"Moving embedded PDF to structured output: {expected_embedded_path}")

                os.makedirs(os.path.dirname(expected_embedded_path), exist_ok=True)

                shutil.move(embedded_pdf, expected_embedded_path)

                embedded_pdf = expected_embedded_path

                embed_result["output_file"] = expected_embedded_path

        

        # Store S3 path

        if hasattr(config, 's3_embedded_pdf'):

            config.s3_embedded_pdf = embedded_pdf

        logger.info(f"✅ EMBED completed: {embedded_pdf}")

        

        # CACHE PHASE 1 RESULTS immediately after embed stage completes

        # This saves: embedded_pdf, mapping_json, radio_groups

        if pdf_cache_enabled and pdf_hash and not cache_hit:

            try:

                from pdf_autofillr_mapper.utils.hash_cache import save_hash_cache

                from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

                

                logger.info("💾 Saving Phase 1 to cache (embedded_pdf + semantic_mapping + radio_groups)...")

                

                # Use DESTINATION paths (where files were actually saved) for cache

                cache_embedded = dest_embedded_pdf if dest_embedded_pdf else embedded_pdf

                cache_mapping = dest_semantic_mapping if dest_semantic_mapping else semantic_mapping_path

                cache_radio = dest_radio_groups if dest_radio_groups else radio_groups

                

                logger.info(f"   Cache will reference persistent paths:")

                logger.info(f"      embedded_pdf: {cache_embedded}")

                logger.info(f"      mapping_json: {cache_mapping}")

                logger.info(f"      radio_groups: {cache_radio}")

                

                await save_hash_cache(

                    pdf_hash=pdf_hash,

                    cache_registry_path=cache_registry_path,

                    embedded_pdf=cache_embedded,

                    mapping_json=cache_mapping,

                    radio_groups=cache_radio,

                    user_id=user_id,

                    pdf_doc_id=pdf_doc_id

                )

                logger.info(f"✅ Phase 1 cached locally to: {cache_registry_path}")

                

                # IMPORTANT: Upload cache registry to source storage so it persists

                if os.path.exists(cache_registry_path):

                    output_handler = OutputFileHandler(config)

                    

                    # Construct proper destination path for cache file

                    # cache_registry_path is like: /tmp/processing/cache/hash_registry.json

                    # or: ../../data/modules/mapper_sample/cache/hash_registry.json (local)

                    

                    from pdf_autofillr_mapper.core.config import settings

                    if storage_type == 'local':

                        # For local, use the data_output_dir + cache/hash_registry.json

                        cache_dest_path = os.path.join(settings.data_output_dir, 'cache', 'hash_registry.json')

                    logger.info(f"📤 Persisting cache registry: {cache_registry_path} -> source storage")

                    

                    cache_dest = output_handler.save_output(

                        cache_registry_path, 

                        'cache_registry_json'

                    )

                    if cache_dest:

                        logger.info(f"✅ Cache registry persisted to: {cache_dest}")

                    else:

                        logger.warning("⚠️  Cache registry save returned None")

                

                logger.info("✅ Phase 1 cached: embedded_pdf, mapping_json, radio_groups")

            except Exception as cache_error:

                logger.warning(f"Failed to cache Phase 1 results: {cache_error}. Continuing anyway.")

        elif cache_hit:

            logger.info("⏭️  Cache hit - Phase 1 already cached")

        elif not pdf_hash:

            logger.info("⚠️  No pdf_hash available, skipping Phase 1 cache")

        

        # NOTE: Cache is now saved incrementally after each phase completes:

        # - Phase 1 (After Embed): embedded_pdf, mapping_json, radio_groups  ← JUST SAVED ABOVE

        # - Phase 2 (After Headers): headers_with_fields, final_form_fields   ← Saved in dual mapper path

        # - Phase 3 (RAG API): Not cached (always fresh)

        # This ensures we don't lose work if later phases fail.

        

        end_time = time.time()

        total_duration = round(end_time - start_time, 2)

        

        # Get PDF hash from extract result

        pdf_hash = extract_result.get('pdf_hash')

        

        logger.info("\n" + "=" * 80)

        logger.info(f"✅ MAKE EMBED FILE SUCCESS in {total_duration}s")

        logger.info(f"Embedded PDF ready for filling: {embedded_pdf}")

        if pdf_hash:

            logger.info(f"PDF fingerprint hash: {pdf_hash[:16]}...")

        logger.info("=" * 80)

        

        return {

            "operation": "make_embed_file",

            "investor_type": investor_type,

            "inputs": {

                "pdf_doc_id": pdf_doc_id,

                "pdf_s3_path": input_pdf_s3,

                "global_input_json": input_json_s3

            },

            "outputs": {

                "refreshed_pdf": input_pdf_s3,  # Same as input in this flow

                "extracted_json": extracted_json,

                "mapping_json": mapping_json,

                "radio_groups_json": radio_groups,

                "embedded_pdf": embedded_pdf,

                "semantic_mapping_json": semantic_mapping_path,

                "llm_predictions": llm_predictions_path,

                "headers_with_fields": headers_with_fields_path,

                "final_form_fields": final_form_fields_path,

                "rag_predictions": rag_predictions_path,

                "combined_mapping": combined_mapping_path

            },

            "pdf_category": pdf_category,

            "pdf_hash": pdf_hash,

            "cache_hit": cache_hit,

            "dual_mapper_info": {

                "enabled": use_second_mapper,

                "rag_api_failed": rag_api_failed,

                "rag_failure_reason": rag_failure_reason if rag_api_failed else None,

                "mapper_used": "Semantic + RAG" if use_second_mapper and not rag_api_failed else "Semantic only"

            },

            "status": "success",

            "pipeline_results": pipeline_results,

            "timing": {

                "total_pipeline_seconds": total_duration,

                "stage_breakdown": pipeline_results

            },

            "storage_type": storage_type,

            "execution_time_seconds": total_duration

        }

        

    except Exception as e:

        end_time = time.time()

        total_duration = round(end_time - start_time, 2)

        

        logger.error("\n" + "=" * 80)

        logger.error(f"❌ MAKE EMBED FILE FAILED after {total_duration}s: {str(e)}")

        logger.error("=" * 80)

        raise





async def handle_make_form_fields_data_points(

    config: Any,

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    pdf_doc_id: Optional[int] = None,

    notifier: Optional[Any] = None

) -> Dict[str, Any]:

    """

    Make form fields data points - extracts form fields and processes headers.

    Uses local file paths from config object.

    

    This is typically used for initial PDF analysis to understand form structure.

    

    Args:

        config: Storage config with local file paths already set

        user_id: Optional user ID

        session_id: Optional session ID

        pdf_doc_id: Optional PDF document ID

        notifier: Optional notification system

        

    Returns:

        Operation result with form fields data

    """

    start_time = time.time()

    

    # Get local PDF from config

    input_pdf = config.local_input_pdf

    if not input_pdf:

        raise ValueError("config.local_input_pdf not set - AWS handler must download PDF first")

    

    storage_type = config.source_type

    

    logger.info("=" * 60)

    logger.info("MAKE FORM FIELDS DATA POINTS OPERATION")

    logger.info("=" * 60)

    logger.info(f"Input PDF: {input_pdf}")

    logger.info(f"Storage type: {storage_type}")

    logger.info("Extracting form fields and analyzing structure...")

    

    try:

        import tempfile

        

        # Extract PDF data (includes form fields and headers)

        extract_result = await handle_extract_operation(

            input_file=input_pdf,

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id

        )

        

        extracted_json_path = extract_result["output_file"]

        

        # Load and process the extracted data directly

        import json

        with open(extracted_json_path, 'r') as f:

            extracted_data = json.load(f)

        

        # Extract form fields data points

        form_fields = extracted_data.get("fields", [])

        headers = extracted_data.get("headers", [])

        pages = extracted_data.get("pages", [])

        

        # Create analysis

        analysis = {

            "total_fields": len(form_fields),

            "total_headers": len(headers),

            "total_pages": len(pages),

            "field_types": {},

            "field_names": [f.get("name", "") for f in form_fields if isinstance(f, dict)]

        }

        

        # Count field types

        for field in form_fields:

            if isinstance(field, dict):

                field_type = field.get("type", "unknown")

                analysis["field_types"][field_type] = analysis["field_types"].get(field_type, 0) + 1

        

        # Save analysis result

        file_config = get_complete_file_config(input_pdf, user_id, session_id)

        analysis_output_path = file_config["extraction"]["extracted_path"].replace(".json", "_analysis.json")

        

        # Save directly to output path

        with open(analysis_output_path, 'w') as f:

            json.dump(analysis, f, indent=2)

        

        logger.info(f"Analysis saved to: {analysis_output_path}")

        

        # Get PDF hash from extract result

        pdf_hash = extract_result.get('pdf_hash')

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        logger.info(f"✅ Form fields analysis completed in {duration}s")

        logger.info(f"   Total fields: {analysis['total_fields']}")

        logger.info(f"   Total headers: {analysis['total_headers']}")

        logger.info(f"   Total pages: {analysis['total_pages']}")

        if pdf_hash:

            logger.info(f"   PDF hash: {pdf_hash[:16]}...")

        logger.info("=" * 60)

        

        return {

            "operation": "make_form_fields_data_points",

            "status": "success",

            "storage_type": storage_type,

            "execution_time_seconds": duration,

            "extracted_json": extracted_json_path,

            "analysis_json": analysis_output_path,

            "analysis": analysis,

            "pdf_hash": pdf_hash  # Include PDF hash

        }

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        logger.error(f"❌ Form fields analysis failed after {duration}s: {str(e)}")

        raise





async def handle_fill_pdf_operation(

    config: Any,

    user_id: Optional[int] = None,

    session_id: Optional[int] = None,

    pdf_doc_id: Optional[int] = None,

    input_json_doc_id: Optional[int] = None,

    notifier: Optional[Any] = None,

    safe_mode: bool = True

) -> Dict[str, Any]:

    """

    Fill PDF operation - fills embedded PDF with data (with optional safety checks).

    Uses local file paths from config object.

    

    This is similar to handle_fill_operation but with additional safety checks.

    

    Args:

        config: Storage config with local file paths already set

        user_id: Optional user ID

        session_id: Optional session ID

        pdf_doc_id: Optional PDF document ID

        input_json_doc_id: Optional input JSON document ID

        notifier: Optional notification system

        safe_mode: If True, checks if embedded PDF exists before filling

        

    Returns:

        Operation result with filled PDF path or error status

    """

    start_time = time.time()

    

    # Get S3 paths from config (for operations to use)

    # Operations will download from S3, process, and upload back to S3

    embedded_pdf_path = config.s3_embedded_pdf if hasattr(config, 's3_embedded_pdf') and config.s3_embedded_pdf else config.local_embedded_pdf

    input_json_path = config.s3_input_json if hasattr(config, 's3_input_json') and config.s3_input_json else config.local_input_json

    

    if not embedded_pdf_path:

        raise ValueError("config.s3_embedded_pdf or local_embedded_pdf not set - must run embed operation first or set manually")

    if not input_json_path:

        raise ValueError("config.s3_input_json or local_input_json not set - AWS handler must download JSON first")

    

    storage_type = config.source_type

    

    logger.info("=" * 60)

    logger.info("FILL PDF OPERATION" + (" (SAFE MODE)" if safe_mode else ""))

    logger.info("=" * 60)

    logger.info(f"Embedded PDF (S3): {embedded_pdf_path}")

    logger.info(f"Input JSON (S3): {input_json_path}")

    logger.info(f"Storage type: {storage_type}")

    

    user_input_details = {

        "user_id": user_id,

        "pdf_doc_id": pdf_doc_id,

        "input_json_doc_id": input_json_doc_id,

        "session_id": session_id

    }

    

    try:

        # Check if embedded PDF exists locally (if in safe mode)

        if safe_mode and hasattr(config, 'local_embedded_pdf'):

            local_embedded = config.local_embedded_pdf

            if local_embedded and not os.path.exists(local_embedded):

                logger.error(f"❌ Embedded PDF not found locally: {local_embedded}")

                return {

                    "operation": "fill_pdf",

                    "status": "error",

                    "error": f"Embedded PDF file not found: {local_embedded}",

                    "pdf_file_path": None,

                    "storage_type": storage_type

                }

        

        # Call the standard fill operation with S3 paths

        fill_result = await handle_fill_operation(

            embedded_pdf_path=embedded_pdf_path,  # Use S3 path

            input_json_path=input_json_path,      # Use S3 path

            user_id=user_id,

            session_id=session_id,

            notifier=notifier,

            pdf_doc_id=pdf_doc_id,

            input_json_doc_id=input_json_doc_id

        )

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        filled_pdf_path = fill_result["output_file"]

        filled_presigned_url = fill_result.get("filled_presigned_url")

        

        logger.info(f"✅ Fill PDF completed in {duration}s")

        logger.info("=" * 60)

        

        # Match original lambda_handler.py return structure

        return {

            "operation": "fill_pdf",

            "inputs": {

                "pdf_doc_id": pdf_doc_id,

                "embedded_pdf": embedded_pdf_path,

                "combined_input_json": input_json_path,

                "user_id": user_id,

                "session_id": session_id,

                "use_profile_info": True  # Default behavior

            },

            "outputs": {

                "filled_pdf": filled_pdf_path,

                "filled_presigned_url": filled_presigned_url

            },

            "status": "success",

            "timing": {

                "total_pipeline_seconds": duration,

                "stage_breakdown": {"fill": duration}

            },

            "storage_type": storage_type,

            "execution_time_seconds": duration

        }

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        if notifier and NOTIFICATIONS_AVAILABLE:

            await safe_notify(

                notifier, "stage_completion",

                stage=PipelineStage.FILL,

                status=StageStatus.FAILED,

                execution_time=duration,

                error_message=str(e),

                level=NotificationLevel.CRITICAL,

                user_input_details=user_input_details

            )

        

        logger.error(f"❌ Fill PDF failed after {duration}s: {str(e)}")

        

        if safe_mode:

            # In safe mode, return error dict instead of raising

            return {

                "operation": "fill_pdf",

                "status": "error",

                "error": str(e),

                "pdf_file_path": None,

                "storage_type": storage_type,

                "execution_time_seconds": duration

            }

        else:

            raise





async def handle_check_embed_file_operation(

    config: Any,

    user_id: Optional[int] = None,

    session_id: Optional[int] = None

) -> Dict[str, Any]:

    """

    Check embed file operation - verifies if embedded PDF exists.

    Uses local file paths from config object.

    

    This is a lightweight check operation used to verify if an embedded PDF

    is available before attempting to fill it.

    

    Args:

        config: Storage config with local file paths already set

        user_id: Optional user ID

        session_id: Optional session ID

        

    Returns:

        Operation result with existence status and metadata

    """

    start_time = time.time()

    

    # Get local embedded PDF path from config

    embedded_pdf_path = config.local_embedded_pdf

    if not embedded_pdf_path:

        raise ValueError("config.local_embedded_pdf not set - must run embed operation first or set manually")

    

    storage_type = config.source_type

    

    logger.info("=" * 60)

    logger.info("CHECK EMBED FILE OPERATION")

    logger.info("=" * 60)

    logger.info(f"Checking: {embedded_pdf_path}")

    logger.info(f"Storage type: {storage_type}")

    

    try:

        # Check if file exists (local file system check)

        exists = os.path.exists(embedded_pdf_path)

        

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        if exists:

            logger.info(f"✅ Embedded PDF exists: {embedded_pdf_path}")

            logger.info(f"   Check completed in {duration}s")

            logger.info("=" * 60)

            

            return {

                "operation": "check_embed_file",

                "status": "success",

                "exists": True,

                "embedded_pdf_path": embedded_pdf_path,

                "storage_type": storage_type,

                "message": "Embedded PDF file found and ready for filling",

                "execution_time_seconds": duration

            }

        else:

            logger.warning(f"⚠️  Embedded PDF not found: {embedded_pdf_path}")

            logger.info(f"   Check completed in {duration}s")

            logger.info("=" * 60)

            

            return {

                "operation": "check_embed_file",

                "status": "not_found",

                "exists": False,

                "embedded_pdf_path": embedded_pdf_path,

                "storage_type": storage_type,

                "message": "Embedded PDF file not found. You may need to run make_embed_file operation first.",

                "execution_time_seconds": duration

            }

        

    except Exception as e:

        end_time = time.time()

        duration = round(end_time - start_time, 2)

        

        logger.error(f"❌ Check embed file failed after {duration}s: {str(e)}")

        logger.info("=" * 60)

        

        return {

            "operation": "check_embed_file",

            "status": "error",

            "exists": False,

            "embedded_pdf_path": embedded_pdf_path,

            "storage_type": storage_type,

            "error": str(e),

            "message": f"Failed to check embedded PDF: {str(e)}",

            "execution_time_seconds": duration

        }





# ============================================================================

# DUAL MAPPER HELPER FUNCTIONS (RAG Integration)

# ============================================================================





async def call_rag_api(

    user_id: int,

    pdf_doc_id: int,

    headers_file_path: str,

    extracted_json_path: str,

    pdf_hash: str,

    storage_config: Any,

    session_id: Optional[str] = None

) -> str:

    """

    Call RAG pipeline — either inprocess (ragpdf SDK) or http (remote Lambda/API).



    Controlled by RAG_MODE env var / mapper_config.ini [rag] mode.



    Steps:

      1. Create header_file.json from final_form_fields.json

      2a. inprocess: call RAGPDFClient.get_predictions() directly

      2b. http: POST to remote RAG API, download rag_predictions.json



    Args:

        user_id:             User ID (int)

        pdf_doc_id:          PDF document ID (int)

        headers_file_path:   Local path to final_form_fields.json

        extracted_json_path: Local path to extracted JSON (not used directly)

        pdf_hash:            PDF content hash

        storage_config:      Storage config with local_header_file, local_rag_predictions, etc.

        session_id:          Optional session ID string



    Returns:

        Local path to rag_predictions.json

    """

    import json as _json

    import os

    import uuid

    from pdf_autofillr_mapper.headers.create_rag_files import create_rag_api_files

    from pdf_autofillr_mapper.core.config import settings



    if not session_id:

        session_id = f"session_{int(time.time())}_{uuid.uuid4().hex[:8]}"



    rag_mode = getattr(settings, 'rag_mode', None) or os.getenv('RAG_MODE', 'inprocess')



    logger.info("=" * 80)

    logger.info(f"RAG PIPELINE — mode={rag_mode}, session={session_id}")

    logger.info("=" * 80)



    # ── Step 1: Build header_file.json from final_form_fields ────────────────

    header_file_output_path  = getattr(storage_config, 'local_header_file', None)

    section_file_output_path = getattr(storage_config, 'local_section_file', None)



    if not header_file_output_path:

        raise ValueError(

            "storage_config.local_header_file is not set. "

            "Make sure the storage config is initialised with RAG paths before calling call_rag_api()."

        )



    logger.info(f"Step 1: Creating header_file.json from: {headers_file_path}")

    rag_files = await create_rag_api_files(

        final_form_fields_path=headers_file_path,

        header_file_output_path=header_file_output_path,

        section_file_output_path=section_file_output_path or header_file_output_path.replace(

            "header_file.json", "section_file.json"

        ),

        user_id=user_id,

        session_id=session_id,

        pdf_doc_id=pdf_doc_id,

        pdf_hash=pdf_hash

    )

    header_file_local = rag_files["header_file"]

    logger.info(f"✅ header_file.json created: {header_file_local}")



    # ── Step 2A: inprocess — call ragpdf SDK directly ─────────────────────────

    if rag_mode == "inprocess":

        logger.info("Step 2: inprocess — calling ragpdf SDK directly")

        try:

            from ragpdf import RAGPDFClient

        except ImportError:

            raise ImportError(

                "RAG_MODE=inprocess requires the ragpdf SDK. "

                "Install it: pip install pdf-autofillr-rag[transformers]\n"

                "Or switch to RAG_MODE=http and point RAG_API_URL at a running RAG server."

            )



        with open(header_file_local, "r", encoding="utf-8") as f:

            header_data = _json.load(f)



        fields       = header_data.get("fields", [])

        pdf_category = header_data.get("pdf_category", {

            "category": "unknown",

            "sub_category": "unknown",

            "document_type": "unknown"

        })



        logger.info(f"Calling RAGPDFClient.get_predictions() — {len(fields)} fields")

        client = RAGPDFClient.from_env()

        client.get_predictions(

            user_id=str(user_id),

            session_id=session_id,

            pdf_id=str(pdf_doc_id),

            fields=fields,

            pdf_hash=pdf_hash,

            pdf_category=pdf_category,

        )



        # ragpdf saves rag_predictions.json under RAGPDF_DATA_PATH

        # Copy it to the path the mapper expects (storage_config.local_rag_predictions)

        ragpdf_data    = os.getenv("RAGPDF_DATA_PATH", "./data/rag")

        rag_preds_src  = os.path.join(

            ragpdf_data,

            f"predictions/{user_id}/{session_id}/{pdf_doc_id}/predictions/rag_predictions.json"

        )

        local_rag_path = getattr(storage_config, 'local_rag_predictions', None)

        if not local_rag_path:

            raise ValueError(

                "storage_config.local_rag_predictions is not set. "

                "Cannot copy rag_predictions.json to mapper output."

            )



        if not os.path.exists(rag_preds_src):

            raise FileNotFoundError(

                f"ragpdf SDK ran but rag_predictions.json not found at {rag_preds_src}. "

                f"Check RAGPDF_DATA_PATH={ragpdf_data} is correct."

            )



        import shutil

        os.makedirs(os.path.dirname(local_rag_path), exist_ok=True)

        shutil.copy2(rag_preds_src, local_rag_path)

        logger.info(f"✅ RAG predictions (inprocess) copied to: {local_rag_path}")

        logger.info("=" * 80)

        return local_rag_path



    # ── Step 2B: http — call remote RAG API ───────────────────────────────────

    import aiohttp

    from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler



    rag_api_url = (

        getattr(settings, 'rag_api_url', '') or

        os.getenv('RAG_API_URL', '')

    )

    rag_api_key = (

        getattr(settings, 'rag_api_key', '') or

        os.getenv('RAG_API_KEY', '')

    )



    if not rag_api_url:

        raise RuntimeError(

            "RAG_MODE=http requires RAG_API_URL to be set. "

            "Either set it in mapper_config.ini [rag] api_url, or switch to RAG_MODE=inprocess."

        )



    logger.info(f"Step 2: http — uploading header file and calling: {rag_api_url}")



    # Upload header_file to storage so remote API can read it

    output_handler = OutputFileHandler(storage_config)

    dest_header    = output_handler.save_output(header_file_local, 'header_file_json')

    header_for_api = dest_header if dest_header else header_file_local



    payload = {

        "api_name":            "get_rag_predictions",

        "user_id":             str(user_id),

        "session_id":          session_id,

        "pdf_id":              str(pdf_doc_id),

        "pdf_hash":            pdf_hash,

        "header_file_location": header_for_api,

    }



    req_headers = {"Content-Type": "application/json"}

    if rag_api_key:

        req_headers["X-API-Key"] = rag_api_key



    async with aiohttp.ClientSession() as sess:

        async with sess.post(

            rag_api_url,

            json=payload,

            headers=req_headers,

            timeout=aiohttp.ClientTimeout(total=300)

        ) as resp:

            if resp.status != 200:

                err = await resp.text()

                raise RuntimeError(f"RAG API returned HTTP {resp.status}: {err}")

            result = await resp.json()



    if result.get("status") != "success":

        raise RuntimeError(f"RAG API returned failure: {result}")



    rag_source_path = (

        result.get("rag_predictions_path") or

        result.get("data", {}).get("rag_predictions") or

        result.get("data", {}).get("s3_paths", {}).get("rag_predictions")

    )

    if not rag_source_path:

        raise RuntimeError(

            f"RAG API returned success but no predictions path found in response: {result}"

        )



    logger.info(f"✅ RAG API response — predictions at: {rag_source_path}")



    # Download from RAG storage to mapper local path

    local_rag_path = getattr(storage_config, 'local_rag_predictions', None)

    if not local_rag_path:

        raise ValueError("storage_config.local_rag_predictions is not set.")



    from pdf_autofillr_mapper.handlers.input_handler import InputFileHandler

    input_handler = InputFileHandler(storage_config)

    downloaded    = input_handler.download_input(rag_source_path, local_rag_path)



    if not downloaded or not os.path.exists(downloaded):

        raise RuntimeError(

            f"Failed to download RAG predictions from {rag_source_path} to {local_rag_path}"

        )



    logger.info(f"✅ RAG predictions (http) downloaded to: {downloaded}")

    logger.info("=" * 80)

    return downloaded





async def convert_semantic_to_java_format(

    semantic_mapping_path: str,

    user_id: int,

    pdf_doc_id: int,

    storage_config: Any

) -> str:

    """

    Convert semantic mapping format to Java-compatible format.

    Source-agnostic - works with s3://, gs://, azure://, or local paths.

    

    CRITICAL: The semantic mapper outputs format: {field_id: [field_name, actual_value, confidence]}

    where actual_value is the data from input JSON (e.g., "553", "John Doe", etc.)

    

    But the Java embedder expects format: {field_id: [field_name, "", confidence]}

    where the middle element MUST be an empty string.

    

    If we pass semantic mapping directly to Java, it tries to parse the actual_value

    as an array and fails with errors like "Not a JSON Array: \"553\"".

    

    This function strips out the actual values and replaces them with empty strings.

    

    Args:

        semantic_mapping_path: Path to semantic mapping file (any storage type)

        user_id: User ID

        pdf_doc_id: PDF document ID

        storage_config: Storage configuration with paths from config.ini

        

    Returns:

        Path to Java-compatible mapping file (same storage type as input)

    """

    logger.info("🔄 Converting semantic mapping to Java-compatible format...")

    logger.info(f"   Input: {semantic_mapping_path}")

    

    # Load semantic mapping directly (download_from_source handles local/cloud paths)

    with open(semantic_mapping_path, 'r') as f:

        semantic_data = json.load(f)

    

    # Handle both formats:

    # 1. New format (with predictions wrapper): {"user_id": ..., "predictions": {...}}

    # 2. Old format (direct mappings): {"field_id": [...], ...}

    if isinstance(semantic_data, dict) and "predictions" in semantic_data:

        logger.info("📦 Detected wrapped format with 'predictions' key")

        semantic_mappings = semantic_data["predictions"]

    else:

        logger.info("📋 Detected direct format (no wrapper)")

        semantic_mappings = semantic_data

    

    logger.info(f"📊 Loaded semantic mapping with {len(semantic_mappings)} fields")

    

    # Convert to Java format: replace middle element (actual value) with empty string

    java_mapping = {}

    for field_id, mapping_data in semantic_mappings.items():

        # Handle three possible formats:

        # 1. Array format (old): ["field_name", "actual_value", confidence]

        # 2. Dict format (new): {"predicted_field_name": "...", "confidence": 0.95}

        # 3. Dict format (with value): {"predicted_field_name": "...", "value": "...", "confidence": 0.95}

        

        if isinstance(mapping_data, dict):

            # New dictionary format

            field_name = mapping_data.get("predicted_field_name")

            confidence = mapping_data.get("confidence", 0.0)

            

            if field_name:

                java_mapping[field_id] = [field_name, "", confidence]

            else:

                java_mapping[field_id] = [None, None, 0]

                

        elif isinstance(mapping_data, list) and len(mapping_data) >= 3:

            # Old array format: [field_name, actual_value, confidence]

            # Convert to: [field_name, "", confidence]

            field_name = mapping_data[0]

            confidence = mapping_data[2]

            

            if field_name:

                java_mapping[field_id] = [field_name, "", confidence]

            else:

                java_mapping[field_id] = [None, None, 0]

        else:

            # Fallback for unexpected format

            logger.warning(f"Field {field_id} has unexpected format: {mapping_data}")

            java_mapping[field_id] = [None, None, 0]

    

    logger.info(f"✅ Converted to Java format with {len(java_mapping)} fields")

    

    # Get output path from config (set from config.ini pattern)

    java_mapping_path = storage_config.local_java_mapping

    

    if not java_mapping_path:

        raise ValueError(

            "Java mapping path not configured. "

            "Check config.local_java_mapping"

        )

    

    # Save Java-compatible mapping

    with open(java_mapping_path, 'w') as f:

        json.dump(java_mapping, f, indent=2, ensure_ascii=False)

    logger.info(f"📤 Java-compatible mapping saved to: {java_mapping_path}")

    logger.info(f"   ✅ Format: {{'field_id': [field_name, '', confidence]}}")

    logger.info(f"   ✅ Middle element is EMPTY STRING (not actual value from input)")

    

    # Verify format

    with open(java_mapping_path, 'r') as f:

        verify_data = json.load(f)

        sample_keys = list(verify_data.keys())[:3]

        logger.info(f"   ✅ Sample keys: {sample_keys}")

        if "user_id" in verify_data or "final_predictions" in verify_data:

            logger.error(f"   ❌ ERROR: File has wrong structure! Keys: {list(verify_data.keys())[:10]}")

            raise ValueError("Java mapping conversion failed - wrong structure")

        else:

            # Show sample entries

            for key in sample_keys:

                logger.info(f"   ✅ Field {key}: {verify_data[key]}")

    

    return java_mapping_path





async def save_llm_predictions_to_rag_bucket(

    semantic_mapping_path: str,

    user_id: int,

    pdf_doc_id: int,

    storage_config: Any,

    session_id: Optional[str] = None

) -> str:

    """

    Save a copy of the semantic mapping (LLM predictions) to the RAG bucket predictions folder.

    Source-agnostic - works with s3://, gs://, azure://, or local paths.

    This allows comparison between LLM and RAG predictions.

    

    Args:

        semantic_mapping_path: Path to semantic mapping JSON (any storage type)

        user_id: User ID

        pdf_doc_id: PDF document ID

        storage_config: Storage configuration with paths from config.ini

        session_id: Session ID for path construction

        

    Returns:

        Path to saved LLM predictions JSON (same storage type as input)

    """

    from datetime import datetime

    from pdf_autofillr_mapper.core.config import settings

    

    logger.info("📋 Saving LLM predictions to RAG bucket...")

    

    # Load semantic mapping directly

    with open(semantic_mapping_path, 'r') as f:

        semantic_data = json.load(f)

    

    # Create LLM predictions structure (similar to RAG format for easy comparison)

    llm_predictions = {

        "user_id": str(user_id),

        "session_id": session_id or f"session_{int(time.time())}",

        "pdf_id": str(pdf_doc_id),

        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),

        "source": "llm_semantic_mapper",

        "predictions": {}

    }

    

    # Convert semantic mapping format to predictions format

    for field_id, field_data in semantic_data.items():

        field_key = f"field_{int(field_id)}"

        field_name = field_data[0] if field_data and field_data[0] else None

        confidence = field_data[2] if field_data and len(field_data) > 2 else 0.0

        

        if field_name:

            llm_predictions["predictions"][field_key] = {

                "predicted_field_name": field_name,

                "confidence": confidence

            }

        else:

            llm_predictions["predictions"][field_key] = None

    

    # Get output path from config (set from config.ini pattern)

    llm_predictions_path = storage_config.local_llm_predictions

    

    if not llm_predictions_path:

        raise ValueError(

            "LLM predictions path not configured. "

            "Check config.local_llm_predictions"

        )

    

    # Save to output path

    with open(llm_predictions_path, 'w') as f:

        json.dump(llm_predictions, f, indent=2, ensure_ascii=False)

    

    logger.info(f"✅ LLM predictions saved to local: {llm_predictions_path}")

    logger.info(f"   📊 Total predictions: {len(llm_predictions['predictions'])}")

    

    # Try to upload to RAG source storage (optional, non-blocking)

    try:

        from pdf_autofillr_mapper.handlers.output_handler import OutputFileHandler

        rag_output_handler = OutputFileHandler(storage_config)

        rag_dest_path = rag_output_handler.save_output(llm_predictions_path, 'llm_predictions_json')

        

        if rag_dest_path:

            logger.info(f"✅ LLM predictions uploaded to RAG storage: {rag_dest_path}")

        else:

            logger.warning("⚠️  LLM predictions not uploaded to RAG storage (upload returned None)")

    except Exception as upload_error:

        logger.warning(f"⚠️  Failed to upload LLM predictions to RAG storage: {upload_error}")

        logger.warning("   Continuing anyway - file is saved locally")

    

    return llm_predictions_path





async def combine_mappings(

    semantic_mapping_path: str,

    rag_predictions_path: str,

    user_id: int,

    pdf_doc_id: int,

    storage_config: Any,

    session_id: Optional[str] = None

) -> tuple:

    """

    Combine semantic mapper output (first phase) with RAG predictions to create final mapping.

    Source-agnostic - works with s3://, gs://, azure://, or local paths.

    

    Strategy:

    - Compare semantic mapping [field_name, null, confidence] with RAG predictions

    - RAG prediction selected if both agree OR RAG has higher confidence

    - Format output as final_predictions with detailed reasoning

    - Save alongside input files with appropriate naming

    

    Args:

        semantic_mapping_path: Path to first phase mapping JSON (any storage type)

        rag_predictions_path: Path to RAG predictions JSON (any storage type)

        user_id: User ID

        pdf_doc_id: PDF document ID

        storage_config: Storage configuration with paths from config.ini

        session_id: Session ID for path construction

        

    Returns:

        Tuple of (java_mapping_path, final_predictions_path):

        - java_mapping_path: Path to Java-compatible mapping for embedder

        - final_predictions_path: Path to detailed predictions with reasoning

    """

    from datetime import datetime

    from pdf_autofillr_mapper.core.config import settings

    

    logger.info("🔄 Combining semantic mapping with RAG predictions...")

    

    # Load semantic mapping (first phase format: {field_id: [field_name, null, confidence]})

    with open(semantic_mapping_path, 'r') as f:

        semantic_data = json.load(f)

    

    # Load RAG predictions (format: {predictions: {field_1: {...}, field_2: null, ...}})

    with open(rag_predictions_path, 'r') as f:

        rag_data = json.load(f)

    

    rag_predictions = rag_data.get('predictions', {})

    

    logger.info(f"📊 Semantic mapping has {len(semantic_data)} fields")

    logger.info(f"📊 RAG predictions has {len(rag_predictions)} predictions")

    

    # Create final predictions with reasoning

    final_predictions = {}

    stats = {

        "both_agreed_rag_selected": 0,

        "both_agreed_llm_selected": 0,

        "disagreed_rag_selected": 0,

        "disagreed_llm_selected": 0,

        "neither_predicted": 0,

        "only_rag": 0,

        "only_llm": 0

    }

    

    # Get all unique field IDs from both sources

    all_field_ids = set()

    

    # Add semantic field IDs (keys are integers like "1", "2", etc.)

    for fid in semantic_data.keys():

        all_field_ids.add(int(fid))

    

    # Add RAG field IDs (keys are like "field_1", "field_2", etc.)

    for field_key in rag_predictions.keys():

        if field_key.startswith("field_"):

            fid = field_key.replace("field_", "")

            if fid.isdigit():

                all_field_ids.add(int(fid))

    

    logger.info(f"🔍 Processing {len(all_field_ids)} unique fields...")

    

    # Process each field

    for fid in sorted(all_field_ids):

        field_key = f"field_{fid:03d}"  # Format as field_001, field_002, etc.

        

        # Get semantic prediction (format: [field_name, null, confidence])

        semantic_pred = semantic_data.get(str(fid))

        llm_field_name = semantic_pred[0] if semantic_pred and semantic_pred[0] else None

        llm_confidence = semantic_pred[2] if semantic_pred and len(semantic_pred) > 2 else 0.0

        

        # Get RAG prediction

        rag_field_key = f"field_{fid}"

        rag_pred = rag_predictions.get(rag_field_key)

        rag_field_name = None

        rag_confidence = None

        

        if rag_pred and isinstance(rag_pred, dict):

            rag_field_name = rag_pred.get('predicted_field_name')

            rag_confidence = rag_pred.get('confidence')

        

        # Decision logic

        selected_name = None

        selected_from = None

        reason = None

        

        if rag_field_name and llm_field_name:

            # Both predicted

            if rag_field_name == llm_field_name:

                # Both agree

                selected_name = rag_field_name

                selected_from = "rag"

                reason = "Both agreed, RAG selected as primary"

                stats["both_agreed_rag_selected"] += 1

            else:

                # Disagreement - select higher confidence

                if rag_confidence >= llm_confidence:

                    selected_name = rag_field_name

                    selected_from = "rag"

                    reason = f"RAG and LLM disagreed, RAG selected due to higher confidence"

                    stats["disagreed_rag_selected"] += 1

                else:

                    selected_name = llm_field_name

                    selected_from = "llm"

                    reason = f"RAG and LLM disagreed, LLM selected due to higher confidence"

                    stats["disagreed_llm_selected"] += 1

        

        elif rag_field_name:

            # Only RAG predicted

            selected_name = rag_field_name

            selected_from = "rag"

            reason = "Only RAG predicted"

            stats["only_rag"] += 1

        

        elif llm_field_name:

            # Only LLM predicted

            selected_name = llm_field_name

            selected_from = "llm"

            reason = "Only LLM predicted"

            stats["only_llm"] += 1

        

        else:

            # Neither predicted

            reason = "Neither RAG nor LLM predicted"

            stats["neither_predicted"] += 1

        

        # Add to final predictions

        final_predictions[field_key] = {

            "selected_field_name": selected_name,

            "selected_from": selected_from,

            "rag_confidence": rag_confidence,

            "llm_confidence": llm_confidence,

            "reason": reason

        }

    

    # Create final output structure

    final_output = {

        "user_id": str(user_id),

        "session_id": session_id or rag_data.get('session_id', 'unknown'),

        "pdf_id": str(pdf_doc_id),

        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),

        "pdf_hash": rag_data.get('pdf_hash', ''),

        "final_predictions": final_predictions,

        "summary": {

            "total_fields": len(all_field_ids),

            "predicted_fields": len(all_field_ids) - stats["neither_predicted"],

            "unpredicted_fields": stats["neither_predicted"],

            "both_agreed": stats["both_agreed_rag_selected"],

            "disagreed_rag_won": stats["disagreed_rag_selected"],

            "disagreed_llm_won": stats["disagreed_llm_selected"],

            "only_rag": stats["only_rag"],

            "only_llm": stats["only_llm"]

        }

    }

    

    logger.info(f"✅ Final predictions created:")

    logger.info(f"   Total fields: {final_output['summary']['total_fields']}")

    logger.info(f"   Predicted: {final_output['summary']['predicted_fields']}")

    logger.info(f"   Both agreed: {stats['both_agreed_rag_selected']}")

    logger.info(f"   RAG won disagreement: {stats['disagreed_rag_selected']}")

    logger.info(f"   LLM won disagreement: {stats['disagreed_llm_selected']}")

    

    # Create Java-compatible mapping format [field_name, "", confidence]

    logger.info("📋 Creating Java-compatible mapping format...")

    java_mapping = {}

    

    for fid in sorted(all_field_ids):

        field_key = f"field_{fid:03d}"

        prediction = final_predictions[field_key]

        

        field_name = prediction["selected_field_name"]

        

        # Determine confidence (use the selected source's confidence)

        if prediction["selected_from"] == "rag" and prediction["rag_confidence"]:

            confidence = prediction["rag_confidence"]

        elif prediction["selected_from"] == "llm" and prediction["llm_confidence"]:

            confidence = prediction["llm_confidence"]

        else:

            confidence = 0.0

        

        # Format as [field_name, "", confidence] or [null, null, 0] if not predicted

        if field_name:

            java_mapping[str(fid)] = [field_name, "", round(confidence, 2)]

        else:

            java_mapping[str(fid)] = [None, None, 0]

    

    logger.info(f"✅ Java-compatible mapping created with {len(java_mapping)} fields")

    

    # Get output paths from config (set from config.ini patterns)

    final_predictions_path = storage_config.local_final_predictions

    java_mapping_path = storage_config.local_java_mapping

    

    if not final_predictions_path:

        raise ValueError(

            "Final predictions path not configured. "

            "Check config.local_final_predictions"

        )

    

    if not java_mapping_path:

        raise ValueError(

            "Java mapping path not configured. "

            "Check config.local_java_mapping"

        )

    

    # Save detailed predictions

    with open(final_predictions_path, 'w') as f:

        json.dump(final_output, f, indent=2, ensure_ascii=False)

    

    logger.info(f"📤 Final predictions saved to: {final_predictions_path}")

    

    # Save Java-compatible mapping for Java embedder

    # CRITICAL: Java embedder expects simple format {field_id: [name, "", conf]}

    with open(java_mapping_path, 'w') as f:

        json.dump(java_mapping, f, indent=2, ensure_ascii=False)

    

    logger.info(f"📤 Java-compatible mapping saved to: {java_mapping_path}")

    logger.info(f"   ✅ Format: {{'field_id': [field_name, '', confidence]}}")

    logger.info(f"   ✅ This is the EXACT file Java embedder will receive")

    

    # Verify the file was saved correctly (debug)

    with open(java_mapping_path, 'r') as f:

        saved_data = json.load(f)

        logger.info(f"   ✅ Verified: File contains {len(saved_data)} field mappings")

        if "user_id" in saved_data or "final_predictions" in saved_data:

            logger.error(f"   ❌ ERROR: Java mapping file contains wrong structure!")

            logger.error(f"   Keys found: {list(saved_data.keys())[:10]}")

            raise ValueError("Java mapping file has wrong structure - contains detailed predictions instead of simple array format")

        else:

            logger.info(f"   ✅ Correct format: Keys are field IDs like '1', '2', '3'...")

            # Show first few entries for verification

            sample_items = list(saved_data.items())[:3]

            for fid, mapping in sample_items:

                logger.info(f"   ✅ Field {fid}: {mapping}")

    

    # Return both the Java mapping (for embedder) and detailed predictions (for output notification)

    logger.info(f"✅ Returning both paths:")

    logger.info(f"   📋 Java mapping: {java_mapping_path}")

    logger.info(f"   📊 Detailed predictions: {final_predictions_path}")

    

    return java_mapping_path, final_predictions_path