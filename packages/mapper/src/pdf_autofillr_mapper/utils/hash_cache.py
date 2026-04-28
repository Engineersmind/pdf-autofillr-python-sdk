"""
PDF Hash Cache Utility - Platform Independent

Manages caching of PDF hash -> embedded file mappings.
Enables skipping expensive MAP operation when same PDF structure is encountered.

Works with local file paths - platform-agnostic (no AWS/Azure/GCP dependencies).
The entrypoint/adapter layer is responsible for downloading cache from cloud storage.
"""

import json
import time
import os
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


async def check_hash_cache(
    pdf_hash: str,
    cache_registry_path: str
) -> Optional[Dict]:
    """
    Check if this PDF hash has been processed before.
    
    Args:
        pdf_hash: SHA-256 hash of PDF structure fingerprint
        cache_registry_path: Local path to hash_registry.json file
        
    Returns:
        Cache entry dict if found, None otherwise.
        Cache entry contains:
        - reference_files: Dict with embedded_pdf, mapping_json, radio_groups paths
        - usage_count: Number of times this hash has been used
        - created_at: Timestamp when first cached
        - last_used_at: Timestamp when last used
    """
    cache_key = pdf_hash
    
    logger.info(f"Checking hash cache for key: {cache_key[:32]}... at {cache_registry_path}")
    
    try:
        # Check if cache registry file exists
        if not os.path.exists(cache_registry_path):
            logger.info("Cache registry does not exist yet. This is the first hash.")
            return None
        
        # Load cache data (handle empty file case)
        try:
            with open(cache_registry_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    logger.info("Cache file is empty. Treating as cache miss.")
                    return None
                cache_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Cache file is corrupted or empty: {e}. Treating as cache miss.")
            return None
        
        entries = cache_data.get('entries', {})
        
        if cache_key not in entries:
            logger.info(f"Cache MISS for key: {cache_key[:32]}...")
            return None
        
        entry = entries[cache_key]
        logger.info(f"Cache HIT for key: {cache_key[:32]}... (usage_count={entry.get('usage_count', 0)})")
        
        # Update usage statistics
        entry['usage_count'] = entry.get('usage_count', 0) + 1
        entry['last_used_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Save updated cache back to file
        try:
            cache_data['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            with open(cache_registry_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.debug("Updated cache usage statistics")
        except Exception as update_error:
            logger.warning(f"Failed to update cache statistics: {update_error}")
        
        return entry
        
    except Exception as e:
        logger.warning(f"Error checking hash cache: {e}. Proceeding without cache.")
        return None


async def save_hash_cache(
    pdf_hash: str,
    cache_registry_path: str,
    embedded_pdf: str,
    mapping_json: str,
    radio_groups: str,
    user_id: int,
    pdf_doc_id: int,
    pdf_category: Optional[Dict] = None,
    rag_predictions: Optional[str] = None,
    combined_mapping: Optional[str] = None,
    headers_with_fields: Optional[str] = None,
    final_form_fields: Optional[str] = None
):
    """
    Save new cache entry after successful MAP + EMBED operations.
    
    Args:
        pdf_hash: SHA-256 hash of PDF structure fingerprint
        cache_registry_path: Local path to hash_registry.json file
        embedded_pdf: Path to embedded PDF file
        mapping_json: Path to semantic mapping JSON file
        radio_groups: Path to radio groups JSON file
        user_id: User ID who first processed this PDF
        pdf_doc_id: PDF document ID
        pdf_category: Optional PDF category classification dict
        rag_predictions: Optional path to RAG predictions JSON file (dual mapper)
        combined_mapping: Optional path to combined mapping JSON file (dual mapper)
        headers_with_fields: Optional path to headers_with_fields.json (dual mapper)
        final_form_fields: Optional path to final_form_fields.json (dual mapper)
    """
    cache_key = pdf_hash
    
    logger.info(f"Saving hash cache entry for key: {cache_key[:32]}...")
    
    try:
        # Load existing cache or create new one
        if os.path.exists(cache_registry_path):
            try:
                with open(cache_registry_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        cache_data = json.loads(content)
                    else:
                        # Empty file - create new cache structure
                        logger.info("Cache file exists but is empty. Creating new cache structure.")
                        cache_data = {
                            "version": "1.0",
                            "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                            "total_entries": 0,
                            "entries": {}
                        }
            except (json.JSONDecodeError, Exception) as e:
                # Corrupted cache file - start fresh
                logger.warning(f"Cache file is corrupted ({e}). Creating new cache structure.")
                cache_data = {
                    "version": "1.0",
                    "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    "total_entries": 0,
                    "entries": {}
                }
        else:
            # Create new cache structure
            logger.info("Cache file does not exist. Creating new cache structure.")
            cache_data = {
                "version": "1.0",
                "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "total_entries": 0,
                "entries": {}
            }
        
        entries = cache_data.get('entries', {})
        
        # Check if entry already exists
        if cache_key in entries:
            logger.info(f"Cache entry already exists for key: {cache_key[:32]}... Updating with new mappers if provided.")
            existing_entry = entries[cache_key]
            
            # Update RAG predictions if provided (dual mapper was run later)
            if rag_predictions:
                existing_entry["reference_files"]["rag_predictions"] = rag_predictions
                logger.info("Updated cache entry with RAG predictions")
            
            if combined_mapping:
                existing_entry["reference_files"]["combined_mapping"] = combined_mapping
                logger.info("Updated cache entry with combined mapping")
            
            if headers_with_fields:
                existing_entry["reference_files"]["headers_with_fields"] = headers_with_fields
                logger.info("Updated cache entry with headers_with_fields")
            
            if final_form_fields:
                existing_entry["reference_files"]["final_form_fields"] = final_form_fields
                logger.info("Updated cache entry with final_form_fields")
            
            if pdf_category:
                existing_entry["pdf_category"] = pdf_category
                logger.info("Updated cache entry with pdf_category")
            
            existing_entry["last_used_at"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        else:
            # Add new entry with human-readable timestamps
            current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            
            reference_files = {
                "embedded_pdf": embedded_pdf,
                "mapping_json": mapping_json,
                "radio_groups": radio_groups
            }
            
            # Add optional RAG files if provided
            if rag_predictions:
                reference_files["rag_predictions"] = rag_predictions
            
            if combined_mapping:
                reference_files["combined_mapping"] = combined_mapping
            
            # Add optional header files if provided
            if headers_with_fields:
                reference_files["headers_with_fields"] = headers_with_fields
            
            if final_form_fields:
                reference_files["final_form_fields"] = final_form_fields
            
            entries[cache_key] = {
                "pdf_hash": pdf_hash,
                "created_at": current_time,
                "last_used_at": current_time,
                "usage_count": 1,
                "reference_files": reference_files,
                "original_context": {
                    "user_id": user_id,
                    "pdf_doc_id": pdf_doc_id
                }
            }
            
            # Add pdf_category if available
            if pdf_category:
                entries[cache_key]["pdf_category"] = pdf_category
                logger.info(f"Added pdf_category to cache: {pdf_category}")
        
        # Update metadata
        cache_data['entries'] = entries
        cache_data['total_entries'] = len(entries)
        cache_data['last_updated'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(cache_registry_path), exist_ok=True)
        
        # Save back to file
        with open(cache_registry_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        logger.info(f"Successfully saved cache entry. Total entries: {cache_data['total_entries']}")
        
    except Exception as e:
        logger.error(f"Failed to save hash cache: {e}. Pipeline will continue.")


async def copy_cached_files(
    source_files: Dict[str, str],
    target_dir: str
) -> Dict[str, str]:
    """
    Copy cached files to new location - Platform Independent.
    
    Args:
        source_files: Dict with keys: embedded_pdf, mapping_json, radio_groups (local paths)
        target_dir: Target directory where files should be copied
        
    Returns:
        Dict with new paths for copied files
    """
    import shutil
    
    logger.info(f"Copying cached files to {target_dir}")
    
    # Ensure target directory exists
    os.makedirs(target_dir, exist_ok=True)
    
    target_paths = {}
    
    try:
        for file_key, source_path in source_files.items():
            if not source_path or not os.path.exists(source_path):
                logger.warning(f"Source file not found for {file_key}: {source_path}")
                continue
            
            # Get filename and copy to target directory
            filename = os.path.basename(source_path)
            target_path = os.path.join(target_dir, filename)
            
            # Skip copy if source and target are the same
            if os.path.abspath(source_path) == os.path.abspath(target_path):
                logger.info(f"Skipped {file_key}: already at target location {target_path}")
                target_paths[file_key] = target_path
                continue
            
            shutil.copy2(source_path, target_path)
            target_paths[file_key] = target_path
            logger.info(f"Copied {file_key}: {source_path} -> {target_path}")
        
        return target_paths
        
    except Exception as e:
        logger.error(f"Failed to copy cached files: {e}")
        raise


async def get_cache_stats(cache_registry_path: str) -> Dict:
    """
    Get statistics about the hash cache.
    
    Args:
        cache_registry_path: Local path to hash_registry.json file
        
    Returns:
        Dict with cache statistics
    """
    try:
        if not os.path.exists(cache_registry_path):
            return {
                "total_entries": 0,
                "cache_file_exists": False
            }
        
        with open(cache_registry_path, 'r') as f:
            content = f.read().strip()
            if not content:
                return {
                    "total_entries": 0,
                    "cache_file_exists": True,
                    "cache_file_empty": True
                }
            cache_data = json.loads(content)
        
        entries = cache_data.get('entries', {})
        
        # Calculate additional stats
        total_usage = sum(entry.get('usage_count', 0) for entry in entries.values())
        avg_usage = total_usage / len(entries) if entries else 0
        
        return {
            "total_entries": len(entries),
            "total_cache_hits": total_usage,
            "avg_cache_hits_per_entry": round(avg_usage, 2),
            "last_updated": cache_data.get('last_updated', 'N/A'),
            "cache_file_exists": True
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {
            "error": str(e)
        }


async def populate_cached_files_to_config(
    pdf_hash: str,
    cache_registry_path: str,
    config,
    download_to_tmp: bool = True
) -> bool:
    """
    Check cache and populate config with cached file paths.
    
    This function is called by entry points (Lambda/Local handlers) BEFORE
    running the main operation. It:
    1. Checks if PDF hash exists in cache
    2. If found, downloads cached files to /tmp
    3. Populates config.cached_* placeholders with /tmp paths
    
    Args:
        pdf_hash: SHA-256 hash of PDF structure fingerprint
        cache_registry_path: Path to hash_registry.json
        config: Storage config object (AWS/Azure/GCP/Local)
        download_to_tmp: If True, download to /tmp; else use original paths
        
    Returns:
        True if cache hit and files populated, False otherwise
    """
    logger.info(f"[Cache] Checking cache for PDF hash: {pdf_hash[:32]}...")
    
    # Check cache
    cache_result = await check_hash_cache(pdf_hash, cache_registry_path)
    
    if not cache_result:
        logger.info("[Cache] No cache hit - will run full pipeline")
        return False
    
    logger.info(f"[Cache] Cache HIT! Usage count: {cache_result.get('usage_count', 0)}")
    
    # Get reference files from cache
    ref_files = cache_result.get('reference_files', {})
    
    if not ref_files:
        logger.warning("[Cache] Cache entry exists but has no reference_files")
        return False
    
    try:
        # Download files to /tmp and populate config
        import tempfile
        import uuid
        from .storage_helper import download_from_source
        
        tmp_dir = os.path.join(tempfile.gettempdir(), f"pdf_cache_{uuid.uuid4().hex[:8]}")
        os.makedirs(tmp_dir, exist_ok=True)
        
        logger.info(f"[Cache] Downloading cached files to: {tmp_dir}")
        
        # Download embedded PDF
        if ref_files.get('embedded_pdf'):
            tmp_path = os.path.join(tmp_dir, "cached_embedded.pdf")
            try:
                downloaded_path = download_from_source(ref_files['embedded_pdf'], tmp_path)
                if downloaded_path and os.path.exists(downloaded_path):
                    config.cached_embedded_pdf = downloaded_path
                    logger.info(f"[Cache] ✓ Downloaded embedded_pdf to {downloaded_path}")
                else:
                    logger.warning(f"[Cache] Failed to download embedded_pdf")
            except Exception as e:
                logger.warning(f"[Cache] Error downloading embedded_pdf: {e}")
        
        # Download mapping JSON
        if ref_files.get('mapping_json'):
            tmp_path = os.path.join(tmp_dir, "cached_mapping.json")
            try:
                downloaded_path = download_from_source(ref_files['mapping_json'], tmp_path)
                if downloaded_path and os.path.exists(downloaded_path):
                    config.cached_mapping_json = downloaded_path
                    logger.info(f"[Cache] ✓ Downloaded mapping_json to {downloaded_path}")
                else:
                    logger.warning(f"[Cache] Failed to download mapping_json")
            except Exception as e:
                logger.warning(f"[Cache] Error downloading mapping_json: {e}")
        
        # Download radio groups
        if ref_files.get('radio_groups'):
            tmp_path = os.path.join(tmp_dir, "cached_radio_groups.json")
            try:
                downloaded_path = download_from_source(ref_files['radio_groups'], tmp_path)
                if downloaded_path and os.path.exists(downloaded_path):
                    config.cached_radio_groups = downloaded_path
                    logger.info(f"[Cache] ✓ Downloaded radio_groups to {downloaded_path}")
                else:
                    logger.warning(f"[Cache] Failed to download radio_groups")
            except Exception as e:
                logger.warning(f"[Cache] Error downloading radio_groups: {e}")
        
        # Download headers with fields
        if ref_files.get('headers_with_fields'):
            tmp_path = os.path.join(tmp_dir, "cached_headers_with_fields.json")
            try:
                downloaded_path = download_from_source(ref_files['headers_with_fields'], tmp_path)
                if downloaded_path and os.path.exists(downloaded_path):
                    config.cached_headers_with_fields = downloaded_path
                    logger.info(f"[Cache] ✓ Downloaded headers_with_fields to {downloaded_path}")
                else:
                    logger.warning(f"[Cache] Failed to download headers_with_fields")
            except Exception as e:
                logger.warning(f"[Cache] Error downloading headers_with_fields: {e}")
        
        # Download final form fields
        if ref_files.get('final_form_fields'):
            tmp_path = os.path.join(tmp_dir, "cached_final_form_fields.json")
            try:
                downloaded_path = download_from_source(ref_files['final_form_fields'], tmp_path)
                if downloaded_path and os.path.exists(downloaded_path):
                    config.cached_final_form_fields = downloaded_path
                    logger.info(f"[Cache] ✓ Downloaded final_form_fields to {downloaded_path}")
                else:
                    logger.warning(f"[Cache] Failed to download final_form_fields")
            except Exception as e:
                logger.warning(f"[Cache] Error downloading final_form_fields: {e}")
        
        # Verify we got at least the essential files
        if config.cached_mapping_json and config.cached_radio_groups:
            logger.info("[Cache] Successfully populated config with cached files")
            return True
        else:
            logger.warning("[Cache] Failed to download essential cached files (mapping_json, radio_groups)")
            return False
            
    except Exception as e:
        logger.error(f"[Cache] Error downloading cached files: {e}", exc_info=True)
        return False
