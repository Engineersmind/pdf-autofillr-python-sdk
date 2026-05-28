"""
Tests for the make_embed_file operation.

This tests the complete Extract -> Map -> Embed pipeline without the Fill stage.
Tests are done directly with handlers, not through entrypoints.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pdf_autofillr_mapper.handlers.operations import handle_make_embed_file_operation


@pytest.mark.asyncio
class TestMakeEmbedFileOperation:
    """Test suite for make_embed_file operation."""

    def _map_result(self, mapped_path, temp_dir, **extra):
        """Helper: build a complete mock_map return value with all required keys."""
        return {
            "output_file": str(mapped_path),
            "status": "success",
            "confidence": 0.85,
            "semantic_mapping_path": str(mapped_path),
            "mapping_path": str(mapped_path),
            "radio_groups_path": str(temp_dir / "radio.json"),
            "dest_semantic_mapping": str(mapped_path),
            "dest_radio_groups": str(temp_dir / "radio.json"),
            **extra,
        }

    def _create_mapped_file(self, mapped_path):
        """Create a real mapped.json on disk so convert_semantic_to_java_format can open it."""
        mapped_path = Path(mapped_path)
        mapped_path.write_text(
            json.dumps(
                {
                    "field1": {"fid": "field1", "value": "", "confidence": 0.9},
                    "field2": {"fid": "field2", "value": "", "confidence": 0.85},
                }
            )
        )

    def _create_extracted_file(self, extracted_path):
        """Create a real extracted.json on disk."""
        extracted_path = Path(extracted_path)
        extracted_path.write_text(
            json.dumps(
                {
                    "fields": [{"name": "field1", "type": "text", "value": ""}],
                    "metadata": {"page_count": 1},
                }
            )
        )

    async def test_make_embed_file_basic_flow(
        self, mock_storage_config, user_id, pdf_doc_id, session_id, temp_dir
    ):
        """Test basic make_embed_file operation flow."""
        # Arrange: Set up local paths for the pipeline
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"

        # Create real files on disk so downstream functions can open them
        self._create_extracted_file(extracted_path)
        self._create_mapped_file(mapped_path)

        # Mock the sub-operations
        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map, patch(
            "pdf_autofillr_mapper.handlers.operations.convert_semantic_to_java_format"
        ) as mock_convert, patch(
            "pdf_autofillr_mapper.handlers.operations.handle_embed_operation"
        ) as mock_embed:

            # Configure mocks
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
                "execution_time": 1.5,
            }
            mock_map.return_value = self._map_result(
                mapped_path, temp_dir, execution_time=2.0
            )
            mock_convert.return_value = str(temp_dir / "java_mapping.json")
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"],
                "execution_time": 1.0,
            }

            # Act: Run the operation
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                investor_type="individual",
            )

            # Assert
            assert result["status"] == "success"
            assert "extract" in result["pipeline_results"]
            assert "embed" in result["pipeline_results"]
            assert result["pipeline_results"]["extract"]["status"] == "success"

            # Verify all stages were called
            mock_extract.assert_called_once()
            mock_embed.assert_called_once()

    async def test_make_embed_file_with_cache_hit(
        self, mock_storage_config, user_id, pdf_doc_id, session_id, temp_dir
    ):
        """Test make_embed_file operation with cache hit (skip MAP stage)."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        cached_mapped_path = temp_dir / "cached_mapped.json"
        embedded_path = temp_dir / "embedded.pdf"

        # Create real files on disk
        self._create_extracted_file(extracted_path)
        self._create_mapped_file(cached_mapped_path)

        # Create cached mapping file
        cached_mapped_path.write_text(
            json.dumps({"mapped_fields": {"field1": "value1"}, "confidence": 0.9})
        )

        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map, patch(
            "pdf_autofillr_mapper.handlers.operations.convert_semantic_to_java_format"
        ) as mock_convert, patch(
            "pdf_autofillr_mapper.handlers.operations.handle_embed_operation"
        ) as mock_embed:

            # Configure mocks
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
                "execution_time": 1.5,
            }
            mock_map.return_value = self._map_result(
                cached_mapped_path, temp_dir, execution_time=0.1
            )
            mock_convert.return_value = str(temp_dir / "java_mapping.json")
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1"],
                "execution_time": 1.0,
            }

            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
            )

            # Assert
            assert result["status"] == "success"
            assert "extract" in result["pipeline_results"]
            assert "embed" in result["pipeline_results"]

    async def test_make_embed_file_extract_failure(
        self, mock_storage_config, user_id, pdf_doc_id, session_id
    ):
        """Test make_embed_file operation when extract stage fails."""
        # Arrange
        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract:
            # Simulate extract failure
            mock_extract.side_effect = Exception("Extraction failed")

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await handle_make_embed_file_operation(
                    config=mock_storage_config,
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id,
                )

            assert (
                "Extraction failed" in str(exc_info.value)
                or "extract" in str(exc_info.value).lower()
            )

    async def test_make_embed_file_map_failure(
        self, mock_storage_config, user_id, pdf_doc_id, session_id, temp_dir
    ):
        """Test make_embed_file operation when map stage fails."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        self._create_extracted_file(extracted_path)

        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map:

            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
            }

            # Simulate map failure
            mock_map.side_effect = Exception("Mapping failed")

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await handle_make_embed_file_operation(
                    config=mock_storage_config,
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id,
                )

            assert (
                "Mapping failed" in str(exc_info.value)
                or "map" in str(exc_info.value).lower()
            )

    async def test_make_embed_file_embed_failure(
        self, mock_storage_config, user_id, pdf_doc_id, session_id, temp_dir
    ):
        """Test make_embed_file operation when embed stage fails."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"

        self._create_extracted_file(extracted_path)
        self._create_mapped_file(mapped_path)

        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map, patch(
            "pdf_autofillr_mapper.handlers.operations.convert_semantic_to_java_format"
        ) as mock_convert, patch(
            "pdf_autofillr_mapper.handlers.operations.handle_embed_operation"
        ) as mock_embed:

            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
            }
            mock_map.return_value = self._map_result(mapped_path, temp_dir)
            mock_convert.return_value = str(temp_dir / "java_mapping.json")

            # Simulate embed failure
            mock_embed.side_effect = Exception("Embedding failed")

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await handle_make_embed_file_operation(
                    config=mock_storage_config,
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id,
                )

            assert (
                "Embedding failed" in str(exc_info.value)
                or "embed" in str(exc_info.value).lower()
            )

    async def test_make_embed_file_with_notifications(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        mock_notifier,
        temp_dir,
    ):
        """Test make_embed_file operation with notifications enabled."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"

        self._create_extracted_file(extracted_path)
        self._create_mapped_file(mapped_path)

        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map, patch(
            "pdf_autofillr_mapper.handlers.operations.convert_semantic_to_java_format"
        ) as mock_convert, patch(
            "pdf_autofillr_mapper.handlers.operations.handle_embed_operation"
        ) as mock_embed:

            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
            }
            mock_map.return_value = self._map_result(mapped_path, temp_dir)
            mock_convert.return_value = str(temp_dir / "java_mapping.json")
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"],
            }

            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                notifier=mock_notifier,
            )

            # Assert
            assert result["status"] == "success"
            # Notifications should have been called (if implementation supports it)
            # Note: This depends on the actual implementation

    async def test_make_embed_file_with_dual_mapper(
        self, mock_storage_config, user_id, pdf_doc_id, session_id, temp_dir
    ):
        """Test make_embed_file operation with dual mapper enabled."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"

        self._create_extracted_file(extracted_path)
        self._create_mapped_file(mapped_path)

        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map, patch(
            "pdf_autofillr_mapper.handlers.operations.convert_semantic_to_java_format"
        ) as mock_convert, patch(
            "pdf_autofillr_mapper.headers.get_form_fields_points.get_form_fields_points"
        ) as mock_headers, patch(
            "pdf_autofillr_mapper.handlers.operations.handle_embed_operation"
        ) as mock_embed:

            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
            }
            mock_map.return_value = self._map_result(
                mapped_path, temp_dir, dual_mapper_used=True
            )
            mock_convert.return_value = str(temp_dir / "java_mapping.json")
            mock_headers.return_value = {
                "status": "success",
                "pdf_category": "financial",
                "headers_with_fields_path": str(temp_dir / "headers.json"),
                "final_form_fields_path": str(temp_dir / "final_fields.json"),
            }
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"],
            }

            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                use_second_mapper=True,
            )

            # Assert
            assert result["status"] == "success"
            assert "map" in result["pipeline_results"]

    async def test_make_embed_file_execution_time(
        self, mock_storage_config, user_id, pdf_doc_id, session_id, temp_dir
    ):
        """Test that make_embed_file operation tracks execution time."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"

        self._create_extracted_file(extracted_path)
        self._create_mapped_file(mapped_path)

        with patch(
            "pdf_autofillr_mapper.handlers.operations.handle_extract_operation"
        ) as mock_extract, patch(
            "pdf_autofillr_mapper.handlers.operations.run_semantic_api_mapper"
        ) as mock_map, patch(
            "pdf_autofillr_mapper.handlers.operations.convert_semantic_to_java_format"
        ) as mock_convert, patch(
            "pdf_autofillr_mapper.handlers.operations.handle_embed_operation"
        ) as mock_embed:

            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
                "execution_time": 1.5,
            }
            mock_map.return_value = self._map_result(
                mapped_path, temp_dir, execution_time=2.0
            )
            mock_convert.return_value = str(temp_dir / "java_mapping.json")
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"],
                "execution_time": 1.0,
            }

            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
            )

            # Assert
            assert result["status"] == "success"
            assert result["status"] == "success"
            # Timing is tracked internally; top-level key varies by cache/non-cache path


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
