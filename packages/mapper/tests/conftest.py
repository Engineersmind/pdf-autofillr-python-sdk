"""
Test configuration and fixtures for mapper module tests.

This module provides common fixtures and utilities for testing
the mapper operations without needing to invoke AWS Lambda or other entrypoints.
"""

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pdf_path(temp_dir):
    """Create a sample PDF file for testing."""
    pdf_path = temp_dir / "test_form.pdf"
    # Create a minimal PDF (just for path testing, not real PDF operations)
    pdf_path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    return str(pdf_path)


@pytest.fixture
def sample_extracted_json(temp_dir):
    """Create a sample extracted JSON file."""
    import json

    json_path = temp_dir / "extracted.json"
    data = {
        "fields": [
            {
                "name": "first_name",
                "type": "text",
                "value": "",
                "bbox": [100, 100, 200, 120],
                "page": 1,
            },
            {
                "name": "last_name",
                "type": "text",
                "value": "",
                "bbox": [250, 100, 350, 120],
                "page": 1,
            },
            {
                "name": "email",
                "type": "text",
                "value": "",
                "bbox": [100, 150, 300, 170],
                "page": 1,
            },
        ],
        "metadata": {"page_count": 1, "extractor": "test"},
    }

    json_path.write_text(json.dumps(data, indent=2))
    return str(json_path)


@pytest.fixture
def sample_mapped_json(temp_dir):
    """Create a sample mapped JSON file."""
    import json

    json_path = temp_dir / "mapped.json"
    data = {
        "mapped_fields": {
            "firstName": "first_name",
            "lastName": "last_name",
            "emailAddress": "email",
        },
        "confidence": 0.85,
        "mapper": "semantic",
    }

    json_path.write_text(json.dumps(data, indent=2))
    return str(json_path)


@pytest.fixture
def sample_input_json(temp_dir):
    """Create a sample input/global JSON file."""
    import json

    json_path = temp_dir / "global_input.json"
    data = {
        "firstName": "John",
        "lastName": "Doe",
        "emailAddress": "john.doe@example.com",
        "address": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zipCode": "12345",
    }

    json_path.write_text(json.dumps(data, indent=2))
    return str(json_path)


@pytest.fixture
def mock_storage_config(temp_dir, sample_pdf_path, sample_input_json):
    """Create a mock storage configuration object."""

    class MockStorageConfig:
        def __init__(self):
            self.source_type = "local"
            self.local_input_pdf = sample_pdf_path
            self.local_input_json = sample_input_json
            self.local_global_json = sample_input_json
            self.s3_input_pdf = None
            self.s3_input_json = None
            self.s3_global_json = None
            self.s3_extracted_json = None
            self.s3_mapped_json = None
            self.s3_embedded_json = None
            self.local_extracted_json = str(temp_dir / "extracted.json")
            self.local_mapped_json = str(temp_dir / "mapped.json")
            self.local_embedded_json = str(temp_dir / "embedded.json")
            self.local_filled_pdf = str(temp_dir / "filled.pdf")
            self.local_radio_json = str(temp_dir / "radio.json")
            self.local_embedded_pdf = str(temp_dir / "embedded.pdf")
            self.local_header_file = str(temp_dir / "header.json")
            self.local_llm_predictions = str(temp_dir / "llm_predictions.json")
            self.local_rag_predictions = str(temp_dir / "rag_predictions.json")
            self.local_final_predictions = str(temp_dir / "final_predictions.json")
            self.local_headers_with_fields = str(temp_dir / "headers_with_fields.json")
            self.local_final_form_fields = str(temp_dir / "final_form_fields.json")
            self.local_section_file = str(temp_dir / "section_file.json")
            self.local_java_mapping = str(temp_dir / "java_mapping.json")
            self.output_base_path = str(temp_dir)
            self.cache_registry_path = str(temp_dir / "cache.json")
            self.dest_embedded_pdf = str(temp_dir / "embedded.pdf")
            self.dest_mapped_json = str(temp_dir / "mapped.json")
            self.dest_radio_json = str(temp_dir / "radio.json")
            self.dest_extracted_json = str(temp_dir / "extracted.json")
            self.dest_filled_pdf = str(temp_dir / "filled.pdf")
            self.dest_header_file_json = str(temp_dir / "header.json")
            self.dest_llm_predictions_json = str(temp_dir / "llm_predictions.json")
            self.dest_rag_predictions_json = str(temp_dir / "rag_predictions.json")
            self.dest_final_predictions_json = str(temp_dir / "final_predictions.json")
            self.cached_mapping_json = str(temp_dir / "cached_mapping.json")
            self.cached_radio_json = str(temp_dir / "radio.json")
            self.cached_embedded_pdf = str(temp_dir / "embedded.pdf")
            self.cached_mapping_json = str(temp_dir / "cached_mapping.json")
            self.cached_radio_json = str(temp_dir / "radio.json")
            self.cached_radio_groups = str(temp_dir / "radio.json")
            self.cached_embedded_pdf = str(temp_dir / "embedded.pdf")

    return MockStorageConfig()


@pytest.fixture
def mock_notifier():
    """Create a mock notifier for testing notifications."""
    notifier = AsyncMock()
    notifier.notify_stage_completion = AsyncMock(return_value=True)
    notifier.notify_pipeline_completion = AsyncMock(return_value=True)
    return notifier


@pytest.fixture
def user_id():
    """Sample user ID for testing."""
    return 12345


@pytest.fixture
def session_id():
    """Sample session ID for testing."""
    return 67890


@pytest.fixture
def pdf_doc_id():
    """Sample PDF document ID for testing."""
    return 111


@pytest.fixture
def sample_mapping_config():
    """Sample mapping configuration."""
    return {"strategy": "semantic", "confidence_threshold": 0.7, "use_cache": True}


@pytest.fixture(autouse=True)
def setup_env_vars(temp_dir):
    """Set up environment variables for testing."""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOCAL_WORKSPACE"] = str(temp_dir)
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["S3_BUCKET"] = "test-bucket"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_extractor(monkeypatch):
    """Mock the PDF extractor."""

    async def mock_extract(*args, **kwargs):
        return {
            "fields": [
                {"name": "field1", "value": "value1"},
                {"name": "field2", "value": "value2"},
            ],
            "metadata": {"extractor": "mock"},
        }

    # This would be patched in actual tests
    return mock_extract


@pytest.fixture
def mock_mapper(monkeypatch):
    """Mock the semantic mapper."""

    async def mock_map(*args, **kwargs):
        return {
            "mapped_fields": {"targetField1": "field1", "targetField2": "field2"},
            "confidence": 0.9,
        }

    return mock_map


@pytest.fixture
def mock_embedder(monkeypatch):
    """Mock the PDF embedder."""

    async def mock_embed(*args, **kwargs):
        return {"embedded_keys": ["field1", "field2"], "success": True}

    return mock_embed


@pytest.fixture
def mock_filler(monkeypatch):
    """Mock the PDF filler."""

    async def mock_fill(*args, **kwargs):
        return {
            "filled_fields": ["field1", "field2"],
            "output_path": "/tmp/filled.pdf",
            "success": True,
        }

    return mock_fill


# Helper functions for tests


def create_test_pdf(path: str) -> None:
    """Create a minimal test PDF file."""
    Path(path).write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")


def create_test_json(path: str, data: dict[str, Any]) -> None:
    """Create a test JSON file."""
    import json

    Path(path).write_text(json.dumps(data, indent=2))


def assert_file_exists(path: str) -> bool:
    """Assert that a file exists."""
    return Path(path).exists()


def read_json_file(path: str) -> dict[str, Any]:
    """Read and parse a JSON file."""
    import json

    return json.loads(Path(path).read_text())
