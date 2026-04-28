"""
Tests for the make_embed_file operation.

This tests the complete Extract -> Map -> Embed pipeline without the Fill stage.
Tests are done directly with handlers, not through entrypoints.
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from pdf_autofillr_mapper.handlers.operations import handle_make_embed_file_operation


@pytest.mark.asyncio
class TestMakeEmbedFileOperation:
    """Test suite for make_embed_file operation."""
    
    async def test_make_embed_file_basic_flow(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        temp_dir
    ):
        """Test basic make_embed_file operation flow."""
        # Arrange: Set up local paths for the pipeline
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"
        
        # Mock the sub-operations
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.handle_map_operation') as mock_map, \
             patch('src.handlers.operations.handle_embed_operation') as mock_embed:
            
            # Configure mocks
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
                "execution_time": 1.5
            }
            
            mock_map.return_value = {
                "output_file": str(mapped_path),
                "status": "success",
                "confidence": 0.85,
                "execution_time": 2.0
            }
            
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"],
                "execution_time": 1.0
            }
            
            # Act: Run the operation
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                investor_type='individual'
            )
            
            # Assert
            assert result["status"] == "success"
            assert "extract" in result["pipeline_results"]
            assert "map" in result["pipeline_results"]
            assert "embed" in result["pipeline_results"]
            assert result["pipeline_results"]["extract"]["status"] == "success"
            assert result["pipeline_results"]["map"]["status"] == "success"
            assert result["pipeline_results"]["embed"]["status"] == "success"
            
            # Verify all stages were called
            mock_extract.assert_called_once()
            mock_map.assert_called_once()
            mock_embed.assert_called_once()
    
    async def test_make_embed_file_with_cache_hit(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        temp_dir
    ):
        """Test make_embed_file operation with cache hit (skip MAP stage)."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        cached_mapped_path = temp_dir / "cached_mapped.json"
        embedded_path = temp_dir / "embedded.pdf"
        
        # Create cached mapping file
        cached_mapped_path.write_text(json.dumps({
            "mapped_fields": {"field1": "value1"},
            "confidence": 0.9
        }))
        
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.check_hash_cache') as mock_cache_check, \
             patch('src.handlers.operations.copy_cached_files') as mock_copy, \
             patch('src.handlers.operations.handle_embed_operation') as mock_embed:
            
            # Configure mocks
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
                "execution_time": 1.5
            }
            
            # Simulate cache hit
            mock_cache_check.return_value = {
                "status": "hit",
                "cached_files": {
                    "mapped_json": str(cached_mapped_path)
                }
            }
            
            mock_copy.return_value = True
            
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1"],
                "execution_time": 1.0
            }
            
            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id
            )
            
            # Assert
            assert result["status"] == "success"
            assert "extract" in result["pipeline_results"]
            assert "embed" in result["pipeline_results"]
            # MAP should be skipped due to cache
            assert "cache_hit" in result.get("cache_info", {}) or result["pipeline_results"].get("map", {}).get("cached", False)
    
    async def test_make_embed_file_extract_failure(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id
    ):
        """Test make_embed_file operation when extract stage fails."""
        # Arrange
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract:
            # Simulate extract failure
            mock_extract.side_effect = Exception("Extraction failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await handle_make_embed_file_operation(
                    config=mock_storage_config,
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id
                )
            
            assert "Extraction failed" in str(exc_info.value) or "extract" in str(exc_info.value).lower()
    
    async def test_make_embed_file_map_failure(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        temp_dir
    ):
        """Test make_embed_file operation when map stage fails."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.handle_map_operation') as mock_map:
            
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123"
            }
            
            # Simulate map failure
            mock_map.side_effect = Exception("Mapping failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await handle_make_embed_file_operation(
                    config=mock_storage_config,
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id
                )
            
            assert "Mapping failed" in str(exc_info.value) or "map" in str(exc_info.value).lower()
    
    async def test_make_embed_file_embed_failure(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        temp_dir
    ):
        """Test make_embed_file operation when embed stage fails."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.handle_map_operation') as mock_map, \
             patch('src.handlers.operations.handle_embed_operation') as mock_embed:
            
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123"
            }
            
            mock_map.return_value = {
                "output_file": str(mapped_path),
                "status": "success",
                "confidence": 0.85
            }
            
            # Simulate embed failure
            mock_embed.side_effect = Exception("Embedding failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await handle_make_embed_file_operation(
                    config=mock_storage_config,
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id
                )
            
            assert "Embedding failed" in str(exc_info.value) or "embed" in str(exc_info.value).lower()
    
    async def test_make_embed_file_with_notifications(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        mock_notifier,
        temp_dir
    ):
        """Test make_embed_file operation with notifications enabled."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"
        
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.handle_map_operation') as mock_map, \
             patch('src.handlers.operations.handle_embed_operation') as mock_embed:
            
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123"
            }
            
            mock_map.return_value = {
                "output_file": str(mapped_path),
                "status": "success",
                "confidence": 0.85
            }
            
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"]
            }
            
            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                notifier=mock_notifier
            )
            
            # Assert
            assert result["status"] == "success"
            # Notifications should have been called (if implementation supports it)
            # Note: This depends on the actual implementation
    
    async def test_make_embed_file_with_dual_mapper(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        temp_dir
    ):
        """Test make_embed_file operation with dual mapper enabled."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"
        
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.handle_map_operation') as mock_map, \
             patch('src.handlers.operations.handle_embed_operation') as mock_embed:
            
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123"
            }
            
            mock_map.return_value = {
                "output_file": str(mapped_path),
                "status": "success",
                "confidence": 0.85,
                "dual_mapper_used": True
            }
            
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"]
            }
            
            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                use_second_mapper=True
            )
            
            # Assert
            assert result["status"] == "success"
            assert "map" in result["pipeline_results"]
    
    async def test_make_embed_file_execution_time(
        self,
        mock_storage_config,
        user_id,
        pdf_doc_id,
        session_id,
        temp_dir
    ):
        """Test that make_embed_file operation tracks execution time."""
        # Arrange
        extracted_path = temp_dir / "extracted.json"
        mapped_path = temp_dir / "mapped.json"
        embedded_path = temp_dir / "embedded.pdf"
        
        with patch('src.handlers.operations.handle_extract_operation') as mock_extract, \
             patch('src.handlers.operations.handle_map_operation') as mock_map, \
             patch('src.handlers.operations.handle_embed_operation') as mock_embed:
            
            mock_extract.return_value = {
                "output_file": str(extracted_path),
                "status": "success",
                "pdf_hash": "test_hash_123",
                "execution_time": 1.5
            }
            
            mock_map.return_value = {
                "output_file": str(mapped_path),
                "status": "success",
                "confidence": 0.85,
                "execution_time": 2.0
            }
            
            mock_embed.return_value = {
                "output_file": str(embedded_path),
                "status": "success",
                "embedded_keys": ["field1", "field2"],
                "execution_time": 1.0
            }
            
            # Act
            result = await handle_make_embed_file_operation(
                config=mock_storage_config,
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id
            )
            
            # Assert
            assert result["status"] == "success"
            assert "execution_time" in result or "total_time" in result
            # Total time should be tracked


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
