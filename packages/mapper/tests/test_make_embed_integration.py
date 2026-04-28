"""
Integration test for handle_make_embed_file_operation.

Tests the complete Extract -> Map -> Embed pipeline using local files and INI configuration.
This test validates the platform-independent operation handler with real PDF and JSON data.

To run these tests:
1. Add    # Restore original settings
    if original_cache_setting is not None:
        settings.cache_registry_path = original_cache_setting
        print(f"[Cache] Restored settings.cache_registry_path")
    
    # ========== CACHE UPLOAD (simulating AWS Lambda S3 upload) ==========
    if tmp_cache_registry and os.path.exists(tmp_cache_registry):
        try:
            print(f"\n[Cache Upload] Uploading cache registry to permanent storage...")
            
            # Simply copy /tmp cache registry to permanent storage (output/cache/)
            # No file copying needed - files are already in output/ (permanent storage)
            os.makedirs(os.path.dirname(cache_registry_path), exist_ok=True)
            shutil.copy2(tmp_cache_registry, cache_registry_path)
            
            print(f"[Cache Upload] ✅ Uploaded hash_registry.json to {cache_registry_path}")
            
            # Show what was saved
            with open(cache_registry_path, 'r') as f:
                cache_data = json.load(f)
                for pdf_hash_key, entry in cache_data.items():
                    print(f"[Cache Upload] Hash {pdf_hash_key[:16]}... cached with {entry.get('usage_count', 1)} usage(s)")
                    ref_files = entry.get('reference_files', {})
                    for file_type, file_path in ref_files.items():
                        exists = "✓" if os.path.exists(file_path) else "✗"
                        print(f"  {exists} {file_type}: {file_path}")
        except Exception as upload_err:
            print(f"[Cache Upload] ❌ Error: {upload_err}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")a/modules/mapper_sample/input.pdf
2. Add input.json to: data/modules/mapper_sample/input.json
3. Run: pytest tests/test_make_embed_integration.py -v -s
"""

import pytest
import asyncio
import os
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the operation handler
from pdf_autofillr_mapper.handlers.operations import handle_make_embed_file_operation

# Import INI configuration
from pdf_autofillr_mapper.utils.ini_config import reload_ini_config, get_ini_config

# Import local storage config
from pdf_autofillr_mapper.configs.local import LocalStorageConfig

# Import settings for cache configuration
from pdf_autofillr_mapper.core.config import settings


@pytest.fixture
def test_data_dir():
    """Get test data directory path."""
    # From tests/test_make_embed_integration.py -> tests/ -> mapper/ -> modules/ -> project_root/
    return Path(__file__).parent.parent.parent.parent / "data" / "modules" / "mapper_sample"


@pytest.fixture
def test_config_path(test_data_dir):
    """Get path to test configuration file."""
    return str(test_data_dir / "config.ini")


@pytest.fixture
def sample_input_pdf(load_test_config):
    """Path to sample input PDF (from INI config)."""
    ini_config = load_test_config
    pdf_path = ini_config.get('local', 'local_input_pdf', fallback=None)
    
    if not pdf_path:
        pytest.skip("local_input_pdf not configured in config.ini [local] section")
    
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found at {pdf_path}. Please add the PDF file or update config.ini")
    
    return str(pdf_path)


@pytest.fixture
def sample_input_json(load_test_config):
    """Path to sample input JSON (from INI config)."""
    ini_config = load_test_config
    json_path = ini_config.get('local', 'local_input_json', fallback=None)
    
    # If not set, try local_global_json as fallback
    if not json_path:
        json_path = ini_config.get('local', 'local_global_json', fallback=None)
    
    if not json_path:
        pytest.skip("local_input_json or local_global_json not configured in config.ini [local] section")
    
    json_path = Path(json_path)
    if not json_path.exists():
        pytest.skip(f"Sample JSON not found at {json_path}. Please add the JSON file or update config.ini")
    
    return str(json_path)


@pytest.fixture
def output_dir(load_test_config):
    """Create and return output directory for test results (from INI config)."""
    ini_config = load_test_config
    output = ini_config.get('local', 'output_base_path', fallback=None)
    
    if not output:
        pytest.skip("output_base_path not configured in config.ini [local] section")
    
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    return str(output_path)


@pytest.fixture
def cache_registry_path(load_test_config):
    """Path to hash cache registry (from INI config)."""
    ini_config = load_test_config
    cache_path = ini_config.get('local', 'cache_registry_path', fallback=None)
    
    if not cache_path:
        pytest.skip("cache_registry_path not configured in config.ini [local] section")
    
    return cache_path


@pytest.fixture
def clean_output_dir(output_dir):
    """
    Ensure output directory exists (but DON'T delete for cache testing).
    
    Note: If testing cache, we need to keep output files from previous runs
    because the cache registry points to them. To test with a clean slate,
    manually delete output/ and cache/ directories before running.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    yield output_dir
    # Optionally clean after test (comment out to inspect results)
    # shutil.rmtree(output_path, ignore_errors=True)


@pytest.fixture
def local_config(sample_input_pdf, sample_input_json, output_dir, cache_registry_path):
    """Create LocalStorageConfig with test paths."""
    config = LocalStorageConfig()
    
    # Set input file paths
    config.local_input_pdf = sample_input_pdf
    config.local_input_json = sample_input_json
    config.local_global_json = sample_input_json  # Use same JSON as global template
    
    # Set output base path
    config.output_base_path = output_dir
    
    # Set cache registry
    config.cache_registry_path = cache_registry_path
    
    return config


@pytest.fixture
def load_test_config(test_config_path):
    """Load INI configuration for testing."""
    if os.path.exists(test_config_path):
        reload_ini_config(test_config_path)
        yield get_ini_config()
    else:
        pytest.skip(f"Test config not found at {test_config_path}")


@pytest.mark.asyncio
async def test_make_embed_file_complete(local_config, clean_output_dir, load_test_config, cache_registry_path):
    """
    Test complete make_embed_file operation with Extract -> Map -> Embed pipeline.
    
    This test:
    1. Extracts form fields from PDF
    2. Maps extracted fields to input JSON keys
    3. Embeds mapped data into PDF
    4. Validates all output files exist and contain valid data
    5. Tests hash caching (if enabled in config)
    6. Validates output directory structure
    """
    # Test parameters
    user_id = 1
    pdf_doc_id = 100
    session_id = 200
    investor_type = "individual"
    
    # Mapping configuration
    mapping_config = {
        "llm_provider": "claude",
        "confidence_threshold": 0.7,
        "chunking_strategy": "page"
    }
    
    # Read use_second_mapper from loaded config
    mapping_section = load_test_config.get_mapping_config()
    use_second_mapper = mapping_section.get('use_second_mapper', False)
    
    print(f"\n{'='*70}")
    print(f"MAKE EMBED FILE INTEGRATION TEST")
    print(f"{'='*70}")
    print(f"📂 Input PDF: {local_config.local_input_pdf}")
    print(f"📂 Input JSON: {local_config.local_input_json}")
    print(f"📂 Output Dir: {clean_output_dir}")
    print(f"📂 Cache Registry: {cache_registry_path}")
    print(f"🔧 Use Second Mapper (RAG): {use_second_mapper}")
    
    # Check if cache exists before test
    cache_existed_before = os.path.exists(cache_registry_path)
    if cache_existed_before:
        print(f"ℹ️  Cache registry exists (will test cache hit scenario)")
    else:
        print(f"ℹ️  No cache registry (will test cache miss scenario)")
    
    # ========== CACHE SETUP (simulating AWS Lambda entry point) ==========
    from pdf_autofillr_mapper.utils.hash_cache import populate_cached_files_to_config
    import tempfile
    
    # Use /tmp for cache registry (like AWS Lambda does)
    tmp_cache_registry = None
    
    if settings.pdf_cache_enabled:
        # Always create tmp cache path (for both first and subsequent runs)
        tmp_cache_registry = "/tmp/hash_registry_test.json"
        
        if cache_existed_before:
            try:
                # 1. Copy hash_registry.json to /tmp (simulate S3 download)
                shutil.copy2(cache_registry_path, tmp_cache_registry)
                print(f"\n[Cache] Copied hash_registry.json to /tmp (simulating S3 download)")
                
                # 2. Read cache to get PDF hash (we'll let operation do extraction)
                with open(tmp_cache_registry, 'r') as f:
                    cache_data = json.load(f)
                
                if cache_data:
                    # Get first hash (assuming single PDF test)
                    pdf_hash = list(cache_data.keys())[0]
                    print(f"[Cache] Found cached PDF hash: {pdf_hash[:32]}...")
                    
                    # 3. Check cache and populate config.cached_* fields (downloads to /tmp)
                    cache_hit = await populate_cached_files_to_config(
                        pdf_hash=pdf_hash,
                        cache_registry_path=tmp_cache_registry,  # Use /tmp path!
                        config=local_config
                    )
                    
                    if cache_hit:
                        print("[Cache] ✅ Config populated with cached files in /tmp")
                    else:
                        print("[Cache] Cache miss - will run full pipeline")
                else:
                    print("[Cache] Cache registry is empty")
            except Exception as cache_err:
                print(f"[Cache] Error setting up cache: {cache_err}")
                import traceback
                traceback.print_exc()
        else:
            # First run - just create empty tmp cache registry
            print(f"\n[Cache] No cache exists, will create at /tmp")
            with open(tmp_cache_registry, 'w') as f:
                json.dump({}, f)
    
    # Override cache_registry_path to use /tmp (like AWS Lambda)
    original_cache_setting = None
    if tmp_cache_registry:
        original_cache_path = cache_registry_path
        # Override settings to use /tmp cache path
        original_cache_setting = settings.cache_registry_path
        settings.cache_registry_path = tmp_cache_registry
        print(f"[Cache] ✅ Overrode settings.cache_registry_path -> {tmp_cache_registry}")
    
    print(f"\n🚀 Running operation...")
    start_time = __import__('time').time()

    print(f"🔧 use_second_mapper: {use_second_mapper} (from config.ini)")
    
    # Run operation (no mocking - test real system)
    # use_second_mapper is now read from config.ini
    result = await handle_make_embed_file_operation(
        config=local_config,
        user_id=user_id,
        pdf_doc_id=pdf_doc_id,
        session_id=session_id,
        investor_type=investor_type,
        mapping_config=mapping_config,
        use_second_mapper=use_second_mapper,  # ← Now from config instead of hardcoded
        notifier=None
    )
    
    end_time = __import__('time').time()
    elapsed = end_time - start_time
    
    # Restore original settings
    if original_cache_setting is not None:
        settings.pdf_cache_registry = original_cache_setting
        print(f"[Cache] Restored settings.pdf_cache_registry")
    
    # ========== CACHE UPLOAD (simulating AWS Lambda S3 upload) ==========
    if tmp_cache_registry and os.path.exists(tmp_cache_registry):
        try:
            # Copy /tmp/hash_registry.json back to permanent cache/ (simulate S3 upload)
            os.makedirs(os.path.dirname(cache_registry_path), exist_ok=True)
            shutil.copy2(tmp_cache_registry, cache_registry_path)
            print(f"[Cache] ✅ Uploaded hash_registry.json back to cache/ (simulating S3 upload)")
        except Exception as upload_err:
            print(f"[Cache] Error uploading cache: {upload_err}")
    
    print(f"\n{'='*70}")
    print(f"RESULTS")
    print(f"{'='*70}")
    
    # Validate result structure
    assert result is not None, "Result should not be None"
    assert result["operation"] == "make_embed_file", "Operation type mismatch"
    assert result["status"] == "success", f"Operation failed: {result.get('error', 'Unknown error')}"
    assert "pipeline_results" in result, "Missing pipeline_results"
    
    print(f"✅ Operation completed successfully")
    print(f"⏱️  Total execution time: {elapsed:.2f}s")
    
    # === VALIDATE EXTRACT STAGE ===
    print(f"\n--- Extract Stage ---")
    extract_result = result["pipeline_results"]["extract"]
    assert extract_result["status"] == "success", "Extract stage failed"
    assert "output_file" in extract_result, "Missing extract output file"
    
    extracted_json_path = extract_result["output_file"]
    assert os.path.exists(extracted_json_path), f"Extracted JSON not found: {extracted_json_path}"
    
    with open(extracted_json_path, 'r') as f:
        extracted_data = json.load(f)
        assert isinstance(extracted_data, dict), "Extracted data should be a dictionary"
        assert len(extracted_data) > 0, "Extracted JSON is empty"
        print(f"✅ Extracted {len(extracted_data)} fields from PDF")
        print(f"📄 Output: {extracted_json_path}")
    
    # Get PDF hash for cache validation
    pdf_hash = extract_result.get("pdf_hash")
    if pdf_hash:
        print(f"🔑 PDF hash: {pdf_hash[:16]}...")
    
    # === VALIDATE MAP STAGE ===
    print(f"\n--- Map Stage ---")
    map_result = result["pipeline_results"]["map"]
    assert "mapping_path" in map_result, "Missing mapping path"
    assert "radio_groups_path" in map_result, "Missing radio groups path"
    
    mapping_json_path = map_result["mapping_path"]
    radio_groups_path = map_result["radio_groups_path"]
    
    assert os.path.exists(mapping_json_path), f"Mapping JSON not found: {mapping_json_path}"
    assert os.path.exists(radio_groups_path), f"Radio groups not found: {radio_groups_path}"
    
    with open(mapping_json_path, 'r') as f:
        mapping_data = json.load(f)
        assert isinstance(mapping_data, dict), "Mapping data should be a dictionary"
        assert len(mapping_data) > 0, "Mapping JSON is empty"
        print(f"✅ Mapped {len(mapping_data)} fields")
        print(f"📄 Mapping: {mapping_json_path}")
        print(f"📄 Radio groups: {radio_groups_path}")
    
    # Check if MAP stage used cache
    if "status" in map_result and map_result["status"] == "cache_hit":
        print(f"🎯 MAP stage used cache (skipped LLM calls)")
    
    # === VALIDATE EMBED STAGE ===
    print(f"\n--- Embed Stage ---")
    embed_result = result["pipeline_results"]["embed"]
    assert embed_result["status"] == "success", "Embed stage failed"
    assert "output_file" in embed_result, "Missing embed output file"
    
    embedded_pdf_path = embed_result["output_file"]
    assert os.path.exists(embedded_pdf_path), f"Embedded PDF not found: {embedded_pdf_path}"
    
    embedded_size = os.path.getsize(embedded_pdf_path)
    assert embedded_size > 0, "Embedded PDF is empty"
    print(f"✅ Embedded PDF created: {embedded_size:,} bytes")
    print(f"📄 Output: {embedded_pdf_path}")
    
    # === VALIDATE DIRECTORY STRUCTURE ===
    print(f"\n--- Directory Structure ---")
    output_base = Path(clean_output_dir)
    user_dir = output_base / "users" / str(user_id)
    pdf_dir = user_dir / "pdfs" / str(pdf_doc_id)
    
    assert user_dir.exists(), f"User directory not created: {user_dir}"
    assert pdf_dir.exists(), f"PDF directory not created: {pdf_dir}"
    
    # Check extraction directory
    extraction_dir = pdf_dir / "extraction"
    assert extraction_dir.exists(), f"Extraction directory not created: {extraction_dir}"
    extracted_files = list(extraction_dir.glob("*_extracted.json"))
    assert len(extracted_files) > 0, "No extracted JSON files found"
    print(f"✅ Extraction: {extraction_dir} ({len(extracted_files)} files)")
    
    # Check mapping directory
    mapping_dir = pdf_dir / "mapping"
    assert mapping_dir.exists(), f"Mapping directory not created: {mapping_dir}"
    mapped_files = list(mapping_dir.glob("*_mapped*.json"))
    radio_files = list(mapping_dir.glob("*_radio_groups.json"))
    assert len(mapped_files) > 0, "No mapping JSON files found"
    assert len(radio_files) > 0, "No radio groups JSON files found"
    print(f"✅ Mapping: {mapping_dir} ({len(mapped_files)} mapped, {len(radio_files)} radio)")
    
    # Check embedding directory
    embedding_dir = pdf_dir / "embedding"
    assert embedding_dir.exists(), f"Embedding directory not created: {embedding_dir}"
    embedded_files = list(embedding_dir.glob("*_embedded.pdf"))
    assert len(embedded_files) > 0, "No embedded PDF files found"
    print(f"✅ Embedding: {embedding_dir} ({len(embedded_files)} files)")
    
    # === VALIDATE CACHE (if caching is enabled) ===
    print(f"\n--- Cache Validation ---")
    if os.path.exists(cache_registry_path):
        with open(cache_registry_path, 'r') as f:
            cache_data = json.load(f)
            cache_entries = len(cache_data)
            print(f"✅ Cache registry exists with {cache_entries} entries")
            
            if pdf_hash and pdf_hash in cache_data:
                cache_entry = cache_data[pdf_hash]
                print(f"✅ PDF hash {pdf_hash[:16]}... is cached")
                print(f"   Cached at: {cache_entry.get('timestamp', 'unknown')}")
                if not cache_existed_before:
                    print(f"   (Newly cached in this run)")
            elif pdf_hash:
                print(f"⚠️  PDF hash {pdf_hash[:16]}... not in cache yet")
    else:
        print(f"ℹ️  No cache registry (caching may be disabled)")
    
    # === SUMMARY ===
    print(f"\n{'='*70}")
    print(f"✅ ALL VALIDATIONS PASSED")
    print(f"{'='*70}")
    print(f"Pipeline: Extract -> Map -> Embed")
    print(f"Execution time: {elapsed:.2f}s")
    print(f"Output directory: {pdf_dir}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
