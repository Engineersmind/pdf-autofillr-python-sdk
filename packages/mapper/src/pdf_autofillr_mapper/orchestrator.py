# mapper/src/pdf_autofillr_mapper/orchestrator.py

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from pdf_autofillr_mapper.embedders.embed_keys import run_embed_java_stage
from pdf_autofillr_mapper.extractors.detailed_fitz import DetailedFitzExtractor
from pdf_autofillr_mapper.fillers.fill_pdf import fill_with_java
from pdf_autofillr_mapper.mappers.semantic_mapper import SemanticMapper

logger = logging.getLogger(__name__)
"""
Cloud-agnostic PDF processing orchestrator.

This module provides a pure orchestration layer that works ONLY with local files.
No cloud storage, database, or API dependencies.

Platform-specific wrappers (Lambda, Azure, GCP) should:
1. Download files from cloud storage to /tmp
2. Call this orchestrator with local file paths
3. Upload results back to cloud storage
"""


class PDFPipeline:
    """
    Cloud-agnostic PDF processing pipeline.

    ALL inputs and outputs are LOCAL file paths (e.g., /tmp/*.pdf, /tmp/*.json).

    This class has NO knowledge of:
    - Cloud storage (S3, GCS, Azure Blob)
    - Database IDs (user_id, pdf_doc_id, session_id)
    - Backend APIs
    - Platform-specific notifications

    Example:
        >>> pipeline = PDFPipeline()
        >>> result = await pipeline.run_all(
        ...     input_pdf_path="/tmp/form.pdf",
        ...     input_data_path="/tmp/data.json"
        ... )
        >>> print(result['filled_pdf'])  # /tmp/form_filled.pdf
    """

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        mapper_config=None,  # MapperConfig instance (preferred)
    ):
        """
        Initialize PDF processing pipeline.

        Args:
            config:        Legacy dict config (backwards compat).
            mapper_config: MapperConfig instance. When provided, its values
                           are merged into self.config and take priority.
                           This is how the chatbot SDK passes configuration.
        """
        self.config = config or {}
        if mapper_config is not None:
            self.config.setdefault("llm_model", mapper_config.llm_model)
            self.config.setdefault(
                "confidence_threshold", mapper_config.confidence_threshold
            )
            self.config.setdefault("chunking_strategy", mapper_config.chunking_strategy)
            self.config.setdefault(
                "include_description", mapper_config.include_description
            )
            self.config["_mapper_config"] = mapper_config
        self.logger = logging.getLogger(f"{__name__}.PDFPipeline")

    async def extract(
        self,
        pdf_path: str,
        output_path: Optional[str] = None,
        file_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Extract form fields from PDF.

        Args:
            pdf_path: LOCAL path to PDF file (e.g., "/tmp/input.pdf")
            output_path: LOCAL path for output JSON (optional, auto-generated if not provided)
            file_config: File-specific configuration (optional)

        Returns:
            Dict with:
            {
                'output_file': '/tmp/input_extracted.json',
                'execution_time_seconds': 2.5,
                'status': 'success',
                'extracted_data': {...}  # The actual extracted data
            }

        Example:
            >>> pipeline = PDFPipeline()
            >>> result = await pipeline.extract("/tmp/form.pdf")
            >>> print(result['output_file'])  # /tmp/form_extracted.json
        """
        start_time = time.time()
        self.logger.info(f"Starting extraction from: {pdf_path}")

        # Validate input
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            # Use file_config if provided, otherwise get from settings
            config = file_config or self._get_file_config(pdf_path)

            # Generate output path if not provided
            if not output_path:
                pdf_name = Path(pdf_path).stem
                output_path = str(Path(pdf_path).parent / f"{pdf_name}_extracted.json")

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Extract using local file - extractor handles saving internally
            extractor = DetailedFitzExtractor(config)
            storage_config = {"type": "local", "path": output_path}
            extracted_data = extractor.extract(
                pdf_path=pdf_path, storage_config=storage_config
            )

            execution_time = round(time.time() - start_time, 2)
            self.logger.info(
                f"Extraction completed in {execution_time}s: {output_path}"
            )

            return {
                "output_file": output_path,
                "execution_time_seconds": execution_time,
                "status": "success",
                "extracted_data": extracted_data,
            }

        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            self.logger.error(f"Extraction failed after {execution_time}s: {e}")
            raise

    async def map(
        self,
        extracted_json_path: str,
        input_schema_path: str,
        output_path: Optional[str] = None,
        radio_output_path: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Map extracted fields to input schema using semantic mapping.

        Args:
            extracted_json_path: LOCAL path to extracted JSON
            input_schema_path: LOCAL path to input schema/data JSON
            output_path: LOCAL path for mapping output JSON (optional)
            radio_output_path: LOCAL path for radio groups JSON (optional)
            config: Mapping configuration (optional)

        Returns:
            Dict with:
            {
                'output_files': {
                    'mapping': '/tmp/form_mapped.json',
                    'radio_groups': '/tmp/form_radio.json'
                },
                'execution_time_seconds': 5.3,
                'status': 'success',
                'mapped_data': {...}
            }

        Example:
            >>> result = await pipeline.map(
            ...     "/tmp/form_extracted.json",
            ...     "/tmp/input_data.json"
            ... )
            >>> print(result['output_files']['mapping'])
        """
        start_time = time.time()
        self.logger.info(
            f"Starting mapping: {extracted_json_path} + {input_schema_path}"
        )

        # Validate inputs
        if not os.path.exists(extracted_json_path):
            raise FileNotFoundError(f"Extracted JSON not found: {extracted_json_path}")
        if not os.path.exists(input_schema_path):
            raise FileNotFoundError(f"Input schema not found: {input_schema_path}")

        try:
            # Read local files
            with open(extracted_json_path, encoding="utf-8") as f:
                extracted_data = json.load(f)

            with open(input_schema_path, encoding="utf-8") as f:
                input_schema = json.load(f)

            # Merge mapping config
            mapping_config = {**self.config, **(config or {})}

            # Process using semantic mapper
            mapper = SemanticMapper(
                method_config=mapping_config.get("mapper_config"),
                chunking_section=mapping_config.get("chunking_config"),
                # llm_provider=mapping_config.get('llm_provider'),
                llm_provider=mapping_config.get("llm_model"),
                confidence_threshold=mapping_config.get("confidence_threshold"),
            )

            mapped_data = await mapper.map(extracted_data, input_schema)

            # Generate output paths if not provided
            base_name = Path(extracted_json_path).stem.replace("_extracted", "")
            parent_dir = Path(extracted_json_path).parent

            if not output_path:
                output_path = str(parent_dir / f"{base_name}_mapped.json")
            if not radio_output_path:
                radio_output_path = str(parent_dir / f"{base_name}_radio.json")

            # Ensure output directories exist
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(radio_output_path).parent.mkdir(parents=True, exist_ok=True)

            # Save mapping results to local files
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(
                    mapped_data.get("mapping", {}), f, indent=2, ensure_ascii=False
                )

            # Save radio groups (if available)
            radio_groups = mapped_data.get("radio_groups", {})
            with open(radio_output_path, "w", encoding="utf-8") as f:
                json.dump(radio_groups, f, indent=2, ensure_ascii=False)

            execution_time = round(time.time() - start_time, 2)
            self.logger.info(f"Mapping completed in {execution_time}s: {output_path}")

            return {
                "output_files": {
                    "mapping": output_path,
                    "radio_groups": radio_output_path,
                },
                "execution_time_seconds": execution_time,
                "status": "success",
                "mapped_data": mapped_data,
            }

        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            self.logger.error(f"Mapping failed after {execution_time}s: {e}")
            raise

    async def embed(
        self,
        original_pdf_path: str,
        extracted_json_path: str,
        mapping_json_path: str,
        radio_json_path: str,
        output_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Embed mapped field data into PDF using Java utility.

        ALL arguments are LOCAL file paths.

        Args:
            original_pdf_path: LOCAL path to original PDF
            extracted_json_path: LOCAL path to extracted JSON
            mapping_json_path: LOCAL path to mapping JSON
            radio_json_path: LOCAL path to radio groups JSON
            output_path: LOCAL path for output PDF (optional)

        Returns:
            Dict with:
            {
                'output_file': '/tmp/form_embedded.pdf',
                'execution_time_seconds': 1.2,
                'status': 'success'
            }

        Example:
            >>> result = await pipeline.embed(
            ...     "/tmp/form.pdf",
            ...     "/tmp/form_extracted.json",
            ...     "/tmp/form_mapped.json",
            ...     "/tmp/form_radio.json"
            ... )
        """
        start_time = time.time()
        self.logger.info(f"Starting embed operation for: {original_pdf_path}")

        # Validate inputs
        for path, name in [
            (original_pdf_path, "Original PDF"),
            (extracted_json_path, "Extracted JSON"),
            (mapping_json_path, "Mapping JSON"),
            (radio_json_path, "Radio JSON"),
        ]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"{name} not found: {path}")

        try:
            # Process using Java embedder
            embedded_pdf = await run_embed_java_stage(
                original_pdf_path,
                extracted_json_path,
                mapping_json_path,
                radio_json_path,
            )

            # Generate output path if not provided
            if not output_path:
                base_name = Path(original_pdf_path).stem
                parent_dir = Path(original_pdf_path).parent
                output_path = str(parent_dir / f"{base_name}_embedded.pdf")

            # Move/copy result to output path if different
            if embedded_pdf != output_path:
                import shutil

                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(embedded_pdf, output_path)

            execution_time = round(time.time() - start_time, 2)
            self.logger.info(f"Embed completed in {execution_time}s: {output_path}")

            return {
                "output_file": output_path,
                "execution_time_seconds": execution_time,
                "status": "success",
            }

        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            self.logger.error(f"Embed failed after {execution_time}s: {e}")
            raise

    async def fill(
        self,
        embedded_pdf_path: str,
        input_data_path: str,
        output_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Fill PDF form with data using Java utility.

        ALL arguments are LOCAL file paths.

        Args:
            embedded_pdf_path: LOCAL path to embedded PDF
            input_data_path: LOCAL path to input data JSON
            output_path: LOCAL path for output PDF (optional)

        Returns:
            Dict with:
            {
                'output_file': '/tmp/form_filled.pdf',
                'execution_time_seconds': 0.8,
                'status': 'success'
            }

        Example:
            >>> result = await pipeline.fill(
            ...     "/tmp/form_embedded.pdf",
            ...     "/tmp/input_data.json"
            ... )
        """
        start_time = time.time()
        self.logger.info(f"Starting fill operation for: {embedded_pdf_path}")

        # Validate inputs
        if not os.path.exists(embedded_pdf_path):
            raise FileNotFoundError(f"Embedded PDF not found: {embedded_pdf_path}")
        if not os.path.exists(input_data_path):
            raise FileNotFoundError(f"Input data not found: {input_data_path}")

        try:
            # Process using Java filler
            # filled_pdf = fill_with_java(embedded_pdf_path, input_data_path)
            filled_pdf = await fill_with_java(embedded_pdf_path, input_data_path)

            # Generate output path if not provided
            if not output_path:
                base_name = Path(embedded_pdf_path).stem.replace("_embedded", "")
                parent_dir = Path(embedded_pdf_path).parent
                output_path = str(parent_dir / f"{base_name}_filled.pdf")

            # Move/copy result to output path if different
            if filled_pdf != output_path:
                import shutil

                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(filled_pdf, output_path)

            execution_time = round(time.time() - start_time, 2)
            self.logger.info(f"Fill completed in {execution_time}s: {output_path}")

            return {
                "output_file": output_path,
                "execution_time_seconds": execution_time,
                "status": "success",
            }

        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            self.logger.error(f"Fill failed after {execution_time}s: {e}")
            raise

    async def run_all(
        self,
        input_pdf_path: str,
        input_data_path: str,
        output_path: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        keep_intermediates: bool = True,
    ) -> dict[str, Any]:
        """
        Complete pipeline: Extract -> Map -> Embed -> Fill

        ALL arguments are LOCAL file paths.

        Args:
            input_pdf_path: LOCAL path to input PDF (e.g., "/tmp/form.pdf")
            input_data_path: LOCAL path to input data JSON (e.g., "/tmp/data.json")
            output_path: LOCAL path for final filled PDF (optional)
            config: Processing configuration (optional)
            keep_intermediates: Keep intermediate files (default: True)

        Returns:
            Dict with LOCAL paths to all generated files:
            {
                'status': 'success',
                'final_output': '/tmp/form_filled.pdf',
                'all_outputs': {
                    'extracted_json': '/tmp/form_extracted.json',
                    'mapping_json': '/tmp/form_mapped.json',
                    'radio_groups': '/tmp/form_radio.json',
                    'embedded_pdf': '/tmp/form_embedded.pdf',
                    'filled_pdf': '/tmp/form_filled.pdf'
                },
                'timing': {
                    'total_pipeline_seconds': 12.5,
                    'stage_breakdown': {
                        'extract': 2.3,
                        'map': 7.8,
                        'embed': 1.5,
                        'fill': 0.9
                    },
                    'stage_percentages': {...}
                },
                'pipeline_stages': {
                    'extract': {...},
                    'map': {...},
                    'embed': {...},
                    'fill': {...}
                }
            }

        Example:
            >>> pipeline = PDFPipeline()
            >>> result = await pipeline.run_all(
            ...     input_pdf_path="/tmp/form.pdf",
            ...     input_data_path="/tmp/data.json"
            ... )
            >>> print(result['final_output'])  # /tmp/form_filled.pdf
        """
        pipeline_start = time.time()
        self.logger.info("=" * 80)
        self.logger.info("Starting complete PDF processing pipeline (run_all)")
        self.logger.info(f"Input PDF: {input_pdf_path}")
        self.logger.info(f"Input Data: {input_data_path}")
        self.logger.info("=" * 80)

        # Validate inputs
        if not os.path.exists(input_pdf_path):
            raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")
        if not os.path.exists(input_data_path):
            raise FileNotFoundError(f"Input data not found: {input_data_path}")

        # Merge config
        pipeline_config = {**self.config, **(config or {})}

        pipeline_results: dict[str, Any] = {
            "operation": "run_all",
            "status": "success",
            "pipeline_stages": {},
            "inputs": {"input_pdf": input_pdf_path, "input_json": input_data_path},
        }

        try:
            # STAGE 1: EXTRACT
            self.logger.info(
                "\n[Stage 1/4] EXTRACT - Extracting form fields from PDF..."
            )
            extract_result = await self.extract(
                pdf_path=input_pdf_path, file_config=pipeline_config.get("file_config")
            )
            pipeline_results["pipeline_stages"]["extract"] = {
                **extract_result,
                "stage": "1/4",
            }
            extracted_json_path = extract_result["output_file"]
            self.logger.info(
                f"✓ Stage 1 completed in {extract_result['execution_time_seconds']}s"
            )

            # STAGE 2: MAP
            self.logger.info("\n[Stage 2/4] MAP - Semantic mapping with LLM...")
            map_result = await self.map(
                extracted_json_path=extracted_json_path,
                input_schema_path=input_data_path,
                config=pipeline_config,
            )
            pipeline_results["pipeline_stages"]["map"] = {**map_result, "stage": "2/4"}
            mapping_json_path = map_result["output_files"]["mapping"]
            radio_json_path = map_result["output_files"]["radio_groups"]
            self.logger.info(
                f"✓ Stage 2 completed in {map_result['execution_time_seconds']}s"
            )

            # STAGE 3: EMBED
            self.logger.info("\n[Stage 3/4] EMBED - Embedding mapped data into PDF...")
            embed_result = await self.embed(
                original_pdf_path=input_pdf_path,
                extracted_json_path=extracted_json_path,
                mapping_json_path=mapping_json_path,
                radio_json_path=radio_json_path,
            )
            pipeline_results["pipeline_stages"]["embed"] = {
                **embed_result,
                "stage": "3/4",
            }
            embedded_pdf_path = embed_result["output_file"]
            self.logger.info(
                f"✓ Stage 3 completed in {embed_result['execution_time_seconds']}s"
            )

            # STAGE 4: FILL
            self.logger.info("\n[Stage 4/4] FILL - Filling PDF form with data...")
            fill_result = await self.fill(
                embedded_pdf_path=embedded_pdf_path,
                input_data_path=input_data_path,
                output_path=output_path,
            )
            pipeline_results["pipeline_stages"]["fill"] = {
                **fill_result,
                "stage": "4/4",
            }
            filled_pdf_path = fill_result["output_file"]
            self.logger.info(
                f"✓ Stage 4 completed in {fill_result['execution_time_seconds']}s"
            )

            # Calculate timing
            pipeline_end = time.time()
            total_duration = round(pipeline_end - pipeline_start, 2)

            stage_times = {
                "extract": extract_result["execution_time_seconds"],
                "map": map_result["execution_time_seconds"],
                "embed": embed_result["execution_time_seconds"],
                "fill": fill_result["execution_time_seconds"],
            }

            stage_percentages = {
                stage: (
                    round((time_val / total_duration) * 100, 1)
                    if total_duration > 0
                    else 0.0
                )
                for stage, time_val in stage_times.items()
            }

            pipeline_results["timing"] = {
                "total_pipeline_seconds": total_duration,
                "stage_breakdown": stage_times,
                "stage_percentages": stage_percentages,
            }

            pipeline_results["final_output"] = filled_pdf_path
            pipeline_results["all_outputs"] = {
                "extracted_json": extracted_json_path,
                "mapping_json": mapping_json_path,
                "radio_groups": radio_json_path,
                "embedded_pdf": embedded_pdf_path,
                "filled_pdf": filled_pdf_path,
            }

            # Clean up intermediates if requested
            if not keep_intermediates:
                self.logger.info("\nCleaning up intermediate files...")
                for file_path in [
                    extracted_json_path,
                    mapping_json_path,
                    radio_json_path,
                    embedded_pdf_path,
                ]:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            self.logger.debug(f"Removed: {file_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to remove {file_path}: {e}")

            self.logger.info("=" * 80)
            self.logger.info(f"✓ Complete pipeline finished in {total_duration}s")
            self.logger.info(f"Final output: {filled_pdf_path}")
            self.logger.info("=" * 80)

            return pipeline_results

        except Exception as e:
            pipeline_end = time.time()
            execution_time = round(pipeline_end - pipeline_start, 2)
            self.logger.error(f"Pipeline failed after {execution_time}s: {e}")
            pipeline_results["status"] = "failed"
            pipeline_results["error"] = str(e)
            pipeline_results["timing"] = {"total_pipeline_seconds": execution_time}
            raise

    def _get_file_config(self, pdf_path: str) -> dict[str, Any]:
        """
        Get file configuration (placeholder for now).

        In future, this could analyze PDF and return optimal config.
        For now, returns default config from settings.
        """
        # TODO: Implement smart config detection based on PDF analysis
        return {}
