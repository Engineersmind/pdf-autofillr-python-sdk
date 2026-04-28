# # modules3/mapper/src/pdf_autofillr_mapper/inprocess_filler.py
# from __future__ import annotations

# import json
# import logging
# import os
# import tempfile
# from pathlib import Path
# from typing import Any, Optional

# logger = logging.getLogger(__name__)
# """
# InProcessMapperFiller
# =====================
# Runs the full mapper pipeline (Extract -> Map -> Embed -> Fill) in-process.

# Used by MapperPDFFiller when MAPPER_API_URL is NOT set.
# No HTTP. No separate server needed.

# Output layout:
#     {data_path}/{user_id}/sessions/{session_id}/mapper/
#         blank_form_extracted.json
#         blank_form_mapped.json
#         blank_form_radio.json
#         blank_form_embedded.pdf

#     {data_path}/{user_id}/sessions/{session_id}/
#         filled.pdf
# """

# class InProcessMapperFiller:

#     def __init__(self, mapper_config=None, config_dir: Optional[str] = None):
#         from pdf_autofillr_mapper.config.mapper_config import MapperConfig
#         from pdf_autofillr_mapper.orchestrator import PDFPipeline

#         self._config_dir = config_dir or os.getenv("chatbot_CONFIG_PATH", "./configs")

#         if mapper_config is None:
#             ini_path = Path(self._config_dir) / "mapper_config.ini"
#             if ini_path.exists():
#                 mapper_config = MapperConfig.from_directory(self._config_dir)
#                 logger.info("InProcessMapperFiller: loaded config from %s", ini_path)
#             else:
#                 mapper_config = MapperConfig.from_env()
#                 logger.info("InProcessMapperFiller: no mapper_config.ini, using env vars")

#         self._mapper_config = mapper_config
#         self._pipeline = PDFPipeline(mapper_config=mapper_config)

#     def prepare_document(self, pdf_path: str, investor_type: str,
#                          session_dir: Optional[str] = None) -> str:
#         """
#         Run Extract + Map + Embed on the blank PDF.

#         Args:
#             pdf_path:      Path to the blank input PDF.
#             investor_type: Investor type string (e.g. "Individual").
#             session_dir:   Directory for intermediate files.
#                            Passed by workflow.py as
#                            {data_path}/{user_id}/sessions/{session_id}/mapper/
#                            When None, files land next to the input PDF.

#         Returns:
#             Path to the embedded PDF (used as doc_id).
#         """
#         import asyncio

#         logger.info("InProcessMapperFiller.prepare_document: pdf=%s type=%s session_dir=%s",
#                     pdf_path, investor_type, session_dir or "(next to pdf)")
#         schema_path = self._get_form_keys_path()
#         pdf_stem = Path(pdf_path).stem

#         if session_dir:
#             out_dir = Path(session_dir)
#             out_dir.mkdir(parents=True, exist_ok=True)
#         else:
#             out_dir = Path(pdf_path).parent

#         async def _run():
#             extract = await self._pipeline.extract(
#                 pdf_path=pdf_path,
#                 output_path=str(out_dir / f"{pdf_stem}_extracted.json"),
#             )
#             extracted_json = extract["output_file"]

#             map_result = await self._pipeline.map(
#                 extracted_json_path=extracted_json,
#                 input_schema_path=schema_path,
#                 output_path=str(out_dir / f"{pdf_stem}_mapped.json"),
#                 radio_output_path=str(out_dir / f"{pdf_stem}_radio.json"),
#             )
#             mapping_json = map_result["output_files"]["mapping"]
#             radio_json = map_result["output_files"]["radio_groups"]

#             embed = await self._pipeline.embed(
#                 original_pdf_path=pdf_path,
#                 extracted_json_path=extracted_json,
#                 mapping_json_path=mapping_json,
#                 radio_json_path=radio_json,
#                 output_path=str(out_dir / f"{pdf_stem}_embedded.pdf"),
#             )
#             return embed["output_file"]

#         return asyncio.run(_run())

#     def check_document_ready(self, doc_id: str) -> bool:
#         return Path(doc_id).exists()

#     def fill_document(self, doc_id: str, data_flat: dict,
#                       output_path: Optional[str] = None) -> Any:
#         """
#         Fill the embedded PDF with collected investor data.

#         Args:
#             doc_id:      Embedded PDF path from prepare_document().
#             data_flat:   Flat dict of field values.
#             output_path: Destination for filled PDF.
#                          workflow.py passes
#                          {data_path}/{user_id}/sessions/{session_id}/filled.pdf
#                          When None, lands next to the embedded PDF.
#         """
#         import asyncio

#         logger.info("InProcessMapperFiller.fill_document: doc_id=%s fields=%d output=%s",
#                     doc_id, len(data_flat), output_path or "(next to embedded pdf)")

#         with tempfile.NamedTemporaryFile(
#             mode="w", suffix="_fill_data.json", delete=False, encoding="utf-8"
#         ) as tmp:
#             json.dump(data_flat, tmp, ensure_ascii=False, indent=2)
#             tmp_path = tmp.name

#         try:
#             result = asyncio.run(
#                 self._pipeline.fill(
#                     embedded_pdf_path=doc_id,
#                     input_data_path=tmp_path,
#                     output_path=output_path,
#                 )
#             )
#             logger.info("InProcessMapperFiller.fill_document: done -> %s", result.get("output_file"))
#             return result
#         finally:
#             try:
#                 os.unlink(tmp_path)
#             except OSError:
#                 pass

#     def _get_form_keys_path(self) -> str:
#         candidates = [
#             Path(self._config_dir) / "form_keys.json",
#             Path("configs") / "form_keys.json",
#         ]
#         for p in candidates:
#             if p.exists():
#                 return str(p)
#         raise FileNotFoundError(
#             "form_keys.json not found. Looked in:\n"
#             + "\n".join(f"  {p}" for p in candidates)
#             + "\n\nRun copy_sample_configs() first, or set chatbot_CONFIG_PATH."
#         )





































# pdf_autofillr_mapper/inprocess_filler.py
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
"""
InProcessMapperFiller
=====================
Runs the full mapper pipeline (Extract -> Map -> Embed [-> RAG] -> Fill) in-process.

Used by MapperPDFFiller when MAPPER_API_URL is NOT set.
No HTTP. No separate server needed.

When [rag] enabled=true in mapper_config.ini AND RAG_ENABLED=true in .env,
prepare_document() runs the full handle_make_embed_file_operation path which
includes the headers stage and RAG inprocess call, producing:
    header_file.json
    rag_predictions.json
    llm_predictions.json
    final_predictions.json

When RAG is disabled, prepare_document() falls back to the lightweight
PDFPipeline orchestrator (extract -> map -> embed only).

Output layout:
    {session_dir}/
        blank_form_extracted.json
        blank_form_mapped.json
        blank_form_radio.json
        blank_form_embedded.pdf
        blank_form_header_file.json      (RAG mode only)
        blank_form_rag_predictions.json  (RAG mode only)
        blank_form_llm_predictions.json  (RAG mode only)
        blank_form_final_predictions.json (RAG mode only)
"""


class InProcessMapperFiller:

    def __init__(self, mapper_config=None, config_dir: Optional[str] = None):
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig
        from pdf_autofillr_mapper.orchestrator import PDFPipeline

        self._config_dir = (
            config_dir
            or os.getenv("chatbot_CONFIG_PATH")
            or os.getenv("DOC_UPLOAD_CONFIG_PATH", "./configs")
        )

        if mapper_config is None:
            ini_path = Path(self._config_dir) / "mapper_config.ini"
            if ini_path.exists():
                mapper_config = MapperConfig.from_directory(self._config_dir)
                logger.info("InProcessMapperFiller: loaded config from %s", ini_path)
            else:
                mapper_config = MapperConfig.from_env()
                logger.info("InProcessMapperFiller: no mapper_config.ini, using env vars")

        self._mapper_config = mapper_config
        self._pipeline = PDFPipeline(mapper_config=mapper_config)

        # Expose the last session_dir used so workflow.py can locate prediction files
        self._last_session_dir: Optional[str] = None
        self._last_user_id: Optional[str] = None
        self._last_session_id: Optional[str] = None
        self._last_pdf_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def prepare_document(self, pdf_path: str, investor_type: str,
                         session_dir: Optional[str] = None) -> str:
        """
        Run Extract + Map + Embed (+ RAG headers pipeline if enabled) on the blank PDF.

        Args:
            pdf_path:      Path to the blank input PDF.
            investor_type: Investor type string (e.g. "Individual").
            session_dir:   Directory for intermediate files.
                           Passed by workflow.py as
                           {data_path}/{user_id}/sessions/{session_id}/mapper/
                           When None, files land next to the input PDF.

        Returns:
            Path to the embedded PDF (used as doc_id).
        """
        logger.info(
            "InProcessMapperFiller.prepare_document: pdf=%s type=%s session_dir=%s rag_enabled=%s",
            pdf_path, investor_type, session_dir or "(next to pdf)",
            self._mapper_config.rag_enabled,
        )

        if session_dir:
            out_dir = Path(session_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = Path(pdf_path).parent

        self._last_session_dir = str(out_dir)

        if self._mapper_config.rag_enabled:
            return self._prepare_with_rag(pdf_path, investor_type, out_dir)
        else:
            return self._prepare_orchestrator(pdf_path, investor_type, out_dir)

    def check_document_ready(self, doc_id: str) -> bool:
        return Path(doc_id).exists()

    def fill_document(self, doc_id: str, data_flat: dict,
                      output_path: Optional[str] = None) -> Any:
        """
        Fill the embedded PDF with collected investor data.

        Args:
            doc_id:      Embedded PDF path from prepare_document().
            data_flat:   Flat dict of field values.
            output_path: Destination for filled PDF.
                         workflow.py passes
                         {data_path}/{user_id}/sessions/{session_id}/filled.pdf
                         When None, lands next to the embedded PDF.
        """
        import asyncio

        logger.info(
            "InProcessMapperFiller.fill_document: doc_id=%s fields=%d output=%s",
            doc_id, len(data_flat), output_path or "(next to embedded pdf)",
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_fill_data.json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(data_flat, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        try:
            result = asyncio.run(
                self._pipeline.fill(
                    embedded_pdf_path=doc_id,
                    input_data_path=tmp_path,
                    output_path=output_path,
                )
            )
            logger.info(
                "InProcessMapperFiller.fill_document: done -> %s", result.get("output_file")
            )
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Accessors for workflow.py to retrieve prediction file paths
    # ------------------------------------------------------------------

    def get_rag_prediction_paths(self) -> dict:
        """
        Return local paths to the prediction files written during prepare_document().
        Only populated after a successful RAG-enabled prepare_document() call.

        Returns dict with keys:
            rag_predictions    – path or None
            llm_predictions    – path or None
            final_predictions  – path or None
            user_id            – str used for RAG SDK storage key
            session_id         – str used for RAG SDK storage key
            pdf_id             – str used for RAG SDK storage key
        """
        out = Path(self._last_session_dir) if self._last_session_dir else None
        if out is None or not self._mapper_config.rag_enabled:
            return {
                "rag_predictions": None,
                "llm_predictions": None,
                "final_predictions": None,
                "user_id": self._last_user_id,
                "session_id": self._last_session_id,
                "pdf_id": self._last_pdf_id,
            }

        pdf_stem = None
        if out.exists():
            # Find the embedded PDF to derive the stem
            candidates = list(out.glob("*_embedded.pdf"))
            if candidates:
                pdf_stem = candidates[0].stem.replace("_embedded", "")

        def _p(suffix):
            if pdf_stem and (out / f"{pdf_stem}{suffix}").exists():
                return str(out / f"{pdf_stem}{suffix}")
            # Fallback: any file matching the suffix pattern
            candidates = list(out.glob(f"*{suffix}")) if out.exists() else []
            return str(candidates[0]) if candidates else None

        return {
            "rag_predictions": _p("_rag_predictions.json"),
            "llm_predictions": _p("_llm_predictions.json"),
            "final_predictions": _p("_final_predictions.json"),
            "user_id": self._last_user_id,
            "session_id": self._last_session_id,
            "pdf_id": self._last_pdf_id,
        }

    # ------------------------------------------------------------------
    # Private: lightweight path (no RAG)
    # ------------------------------------------------------------------

    def _prepare_orchestrator(self, pdf_path: str, investor_type: str,
                               out_dir: Path) -> str:
        """Extract + Map + Embed using the pure orchestrator (no RAG)."""
        import asyncio

        schema_path = self._get_form_keys_path()
        pdf_stem = Path(pdf_path).stem

        async def _run():
            extract = await self._pipeline.extract(
                pdf_path=pdf_path,
                output_path=str(out_dir / f"{pdf_stem}_extracted.json"),
            )
            extracted_json = extract["output_file"]

            map_result = await self._pipeline.map(
                extracted_json_path=extracted_json,
                input_schema_path=schema_path,
                output_path=str(out_dir / f"{pdf_stem}_mapped.json"),
                radio_output_path=str(out_dir / f"{pdf_stem}_radio.json"),
            )
            mapping_json = map_result["output_files"]["mapping"]
            radio_json = map_result["output_files"]["radio_groups"]

            embed = await self._pipeline.embed(
                original_pdf_path=pdf_path,
                extracted_json_path=extracted_json,
                mapping_json_path=mapping_json,
                radio_json_path=radio_json,
                output_path=str(out_dir / f"{pdf_stem}_embedded.pdf"),
            )
            return embed["output_file"]

        return asyncio.run(_run())

    # ------------------------------------------------------------------
    # Private: full path with RAG (Extract + Map + Embed + Headers + RAG)
    # ------------------------------------------------------------------

    def _prepare_with_rag(self, pdf_path: str, investor_type: str,
                           out_dir: Path) -> str:
        """
        Run the full handle_make_embed_file_operation pipeline which includes
        the headers stage and RAG inprocess call.

        Builds a minimal LocalStorageConfig pointing all local_* paths into
        out_dir, then delegates to operations.handle_make_embed_file_operation.
        Returns the path to the embedded PDF (doc_id).
        """
        import asyncio
        import uuid

        from pdf_autofillr_mapper.handlers import operations
        from pdf_autofillr_mapper.configs.local import LocalStorageConfig
        from pdf_autofillr_mapper.config.mapper_config import MapperConfig

        pdf_stem = Path(pdf_path).stem
        schema_path = self._get_form_keys_path()

        # Synthetic IDs — stable within this session_dir so RAG SDK paths are consistent
        # Use the session_dir's leaf name as the session_id for traceability
        session_id = out_dir.name  # e.g. "abc123-uuid" or "mapper"
        user_id = "chatbot"
        pdf_id = pdf_stem

        self._last_user_id = user_id
        self._last_session_id = session_id
        self._last_pdf_id = pdf_id

        # Build a LocalStorageConfig with all paths pre-wired into out_dir
        config = LocalStorageConfig(base_dir=str(out_dir))
        config.source_type = "local"

        # Input paths
        config.local_input_pdf = pdf_path
        config.local_input_json = schema_path

        # Processing / output paths — all inside out_dir
        config.local_extracted_json      = str(out_dir / f"{pdf_stem}_extracted.json")
        config.local_mapped_json         = str(out_dir / f"{pdf_stem}_mapped.json")
        config.local_radio_json          = str(out_dir / f"{pdf_stem}_radio.json")
        config.local_embedded_pdf        = str(out_dir / f"{pdf_stem}_embedded.pdf")
        config.local_filled_pdf          = str(out_dir / f"{pdf_stem}_filled.pdf")
        config.local_headers_with_fields = str(out_dir / f"{pdf_stem}_headers_with_fields.json")
        config.local_final_form_fields   = str(out_dir / f"{pdf_stem}_final_form_fields.json")
        config.local_header_file         = str(out_dir / f"{pdf_stem}_header_file.json")
        config.local_section_file        = str(out_dir / f"{pdf_stem}_section_file.json")
        config.local_llm_predictions     = str(out_dir / f"{pdf_stem}_llm_predictions.json")
        config.local_rag_predictions     = str(out_dir / f"{pdf_stem}_rag_predictions.json")
        config.local_final_predictions   = str(out_dir / f"{pdf_stem}_final_predictions.json")
        config.local_java_mapping        = str(out_dir / f"{pdf_stem}_java_mapping.json")

        # Destination paths (for OutputFileHandler) — same dir for local mode
        config.dest_extracted_json            = config.local_extracted_json
        config.dest_mapped_json               = config.local_mapped_json
        config.dest_radio_json                = config.local_radio_json
        config.dest_embedded_pdf              = config.local_embedded_pdf
        config.dest_filled_pdf                = config.local_filled_pdf
        config.dest_headers_with_fields_json  = config.local_headers_with_fields
        config.dest_final_form_fields_json    = config.local_final_form_fields
        config.dest_header_file_json          = config.local_header_file
        config.dest_section_file_json         = config.local_section_file
        config.dest_llm_predictions_json      = config.local_llm_predictions
        config.dest_rag_predictions_json      = config.local_rag_predictions
        config.dest_final_predictions_json    = config.local_final_predictions
        config.dest_java_mapping_json         = config.local_java_mapping
        config.dest_semantic_mapping_json     = str(out_dir / f"{pdf_stem}_semantic_mapping.json")
        config.dest_cache_registry            = None  # not needed for chatbot flow
        config.output_base_path               = None  # disable cloud-style path generation

        # Cache registry — point to mapper's own cache dir so it benefits from hash caching
        mapper_cache = Path(os.getenv("chatbot_DATA_PATH", "./data/chatbot")) / ".." / "mapper" / "cache"
        cache_registry = mapper_cache / "hash_registry.json"
        cache_registry.parent.mkdir(parents=True, exist_ok=True)
        config.cache_registry_path = str(cache_registry)

        # Build mapping_config from the loaded MapperConfig (respects mapper_config.ini)
        mc = self._mapper_config
        mapping_config = {
            "llm_model":            mc.llm_model,
            "llm_temperature":      mc.llm_temperature,
            "llm_max_tokens":       mc.llm_max_tokens,
            "confidence_threshold": mc.confidence_threshold,
            "chunking_strategy":    mc.chunking_strategy,
        }

        logger.info(
            "InProcessMapperFiller._prepare_with_rag: user=%s session=%s pdf=%s",
            user_id, session_id, pdf_id,
        )

        result = asyncio.run(
            operations.handle_make_embed_file_operation(
                config=config,
                user_id=user_id,
                pdf_doc_id=pdf_id,
                session_id=session_id,
                investor_type=investor_type.lower() if investor_type else "individual",
                mapping_config=mapping_config,
                use_second_mapper=True,   # rag_enabled=True means always use second mapper
            )
        )

        # The operation returns the embedded PDF path in result["outputs"]["embedded_pdf"]
        # or config.local_embedded_pdf — both point to the same file
        embedded_path = (
            (result.get("outputs") or result.get("data", {}).get("outputs") or {})
            .get("embedded_pdf")
            or config.local_embedded_pdf
        )

        if not Path(embedded_path).exists():
            raise RuntimeError(
                f"InProcessMapperFiller._prepare_with_rag: embedded PDF not found at "
                f"{embedded_path} after handle_make_embed_file_operation completed.\n"
                f"Operation result keys: {list(result.keys())}"
            )

        logger.info("InProcessMapperFiller._prepare_with_rag: done -> %s", embedded_path)
        return embedded_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_form_keys_path(self) -> str:
        candidates = [
            Path(self._config_dir) / "form_keys.json",
            Path("configs") / "form_keys.json",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        raise FileNotFoundError(
            "form_keys.json not found. Looked in:\n"
            + "\n".join(f"  {p}" for p in candidates)
            + "\n\nRun pdf-autofillr setup first, or set chatbot_CONFIG_PATH / DOC_UPLOAD_CONFIG_PATH."
        )