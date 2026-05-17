# pdf_autofillr_doc_upload/client.py
"""
DocUploadClient — the main public interface for the extractor SDK.

Ports Lambda main.py into a clean, reusable client that runs the parallel
extraction + embed-file pipeline and (optionally) fills a PDF.

Pipeline (mirrors Lambda main.process_pdf exactly):
    Sequential:
        1. Load schema
        2. Download / locate document

    Parallel:
        Thread A — Extract text -> LLM -> upload output (nested + flat)
        Thread B — make_embed_file -> check_embed_file (poll)

    Sequential (after both threads):
        7. fill_pdf
        8. Save execution log

Usage::

    from pdf_autofillr_doc_upload import DocUploadClient

    client = DocUploadClient()
    result = client.run(
        document_path="investor_profile.pdf",
        schema_path="configs/form_keys.json",
        job_id="job_001",
        output_path="output/filled.json",
    )

    # With PDF filling
    result = client.run(
        document_path="investor_profile.pdf",
        schema_path="configs/form_keys.json",
        job_id="job_001",
        user_id="user_42",
        pdf_doc_id="99",
        session_id="sess_abc",
        investor_type="Individual",
    )
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from pdf_autofillr_doc_upload.config.settings import DocUploadSettings
from pdf_autofillr_doc_upload.extraction.extractor import Extractor, flatten_dict
from pdf_autofillr_doc_upload.logging.logger import ExecutionLogger
from pdf_autofillr_doc_upload.storage.base import StorageBackend
from pdf_autofillr_doc_upload.storage.factory import StorageFactory
from pdf_autofillr_doc_upload.telemetry.collector import TelemetryCollector
from pdf_autofillr_doc_upload.telemetry.config import TelemetryConfig

# Allowed extensions for post-download rename.
# Used only to restore the correct extension on the temp file so the
# extractor can detect the format — user input never reaches NamedTemporaryFile (CWE-22).
_ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".xlsx", ".xls", ".csv", ".tsv",
    ".json", ".txt", ".md", ".markdown", ".html", ".htm", ".xml",
}


class DocUploadClient:
    """
    High-level client for document extraction + optional PDF filling.

    Args:
        storage:   StorageBackend instance. Created from env vars if not provided.
        extractor: Extractor instance. Created from env vars if not provided.
        pdf_filler:PDFFillerInterface instance. None = no PDF filling.
        telemetry: TelemetryCollector. Off by default.
        settings:  DocUploadSettings. Loaded from env vars if not provided.
    """

    def __init__(
        self,
        storage: Optional[StorageBackend] = None,
        extractor: Optional[Extractor] = None,
        pdf_filler=None,
        telemetry: Optional[TelemetryCollector] = None,
        settings: Optional[DocUploadSettings] = None,
    ):
        self.settings = settings or DocUploadSettings.from_env()
        self.storage = storage or StorageFactory.create()
        self.extractor = extractor or Extractor()
        self.pdf_filler = pdf_filler if pdf_filler is not None else self._build_default_filler(self.settings)
        self.telemetry = telemetry or TelemetryCollector(
            TelemetryConfig() if self.settings.telemetry != "off" else None
        )

    @staticmethod
    def _build_default_filler(settings: DocUploadSettings):
        """
        Build the PDF filler from env config — exact mirror of chatbot behaviour.

        DOC_UPLOAD_PDF_FILLER=mapper  +  MAPPER_API_URL set   -> HTTP mapper filler
        DOC_UPLOAD_PDF_FILLER=mapper  +  MAPPER_API_URL empty -> in-process mapper filler
        DOC_UPLOAD_PDF_FILLER=managed                         -> in-process mapper filler (stub)
        DOC_UPLOAD_PDF_FILLER=none (default)                  -> no filling
        """
        mode = settings.pdf_filler
        if mode not in ("mapper", "managed"):
            return None

        if settings.mapper_api_url:
            # HTTP mode — mapper running as a separate server
            from pdf_autofillr_doc_upload.pdf.mapper_filler import MapperPDFFiller
            return MapperPDFFiller(
                lambda_url=settings.mapper_api_url,
                api_key=settings.mapper_api_key,
            )
        else:
            # In-process mode — call mapper directly in this Python process
            from pdf_autofillr_doc_upload.pdf.inprocess_filler import InProcessMapperFiller
            return InProcessMapperFiller(
                pdf_path=settings.pdf_path,
                config_dir=settings.config_path,
                data_path=settings.data_path,
                poll_interval=settings.pdf_poll_interval,
                poll_timeout=settings.pdf_poll_timeout,
                max_retries=settings.pdf_max_retries,
            )

    # ── Main API ───────────────────────────────────────────────────────

    def run(
        self,
        document_path: str,
        schema_path: str,
        job_id: Optional[str] = None,
        output_path: Optional[str] = None,
        # PDF filling parameters (all optional)
        pdf_path: Optional[str] = None,        # blank PDF to fill (overrides DOC_UPLOAD_PDF_PATH)
        investor_type: str = "Individual",
        output_pdf_path: Optional[str] = None, # where to write the filled PDF
        # Remote Lambda filling params (only needed when MAPPER_API_URL is set)
        user_id: Optional[str] = None,
        pdf_doc_id: Optional[str] = None,
        session_id: Optional[str] = None,
        filled_doc_pdf_id: Optional[str] = None,
        use_profile_info: bool = True,
    ) -> dict:
        """
        Run the full extraction + optional PDF filling pipeline.

        Args:
            document_path:    Path or URI to the source document
                              (PDF/DOCX/PPTX/XLSX/CSV/JSON/MD/TXT/HTML/XML).
            schema_path:      Path or URI to form_keys.json.
            job_id:           Auto-generated UUID if not provided.
            output_path:      Where to save extracted JSON (local path or cloud URI).
            pdf_path:         Blank PDF to fill. Overrides DOC_UPLOAD_PDF_PATH env var.
                              Local:  ./data/input/blank_form.pdf
                              S3:     s3://bucket/blank_form.pdf
            investor_type:    Investor type string (default: Individual).
            output_pdf_path:  Where to write the filled PDF (in-process mode only).
                              Defaults to {data_path}/output/{job_id}/blank_form_filled.pdf
            user_id:          Only needed for remote Lambda filling.
            pdf_doc_id:       Only needed for remote Lambda filling.
            session_id:       Only needed for remote Lambda filling.
            filled_doc_pdf_id:Only needed for remote Lambda filling.
            use_profile_info: Passed to remote fill_pdf operation.

        Returns:
            dict with keys: job_id, output_nested, output_flat, output_path,
                            filled_pdf_path, success, errors
        """
        import uuid
        job_id = job_id or str(uuid.uuid4())
        filled_doc_pdf_id = filled_doc_pdf_id or pdf_doc_id
        # pdf_path arg overrides settings value — mirrors chatbot_PDF_PATH behaviour
        effective_pdf_path = pdf_path or self.settings.pdf_path
        logger = ExecutionLogger(job_id=job_id)

        start_time = time.time()

        logger.log("=" * 70)
        logger.log("STARTING EXTRACTION PIPELINE")
        logger.log("=" * 70)
        logger.log(f"Job ID       : {job_id}")
        logger.log(f"Document     : {document_path}")
        logger.log(f"Schema       : {schema_path}")
        logger.log(f"Investor type: {investor_type}")

        self.telemetry.record_job_start(
            job_id=job_id,
            file_ext=Path(document_path).suffix.lower(),
        )

        # ── Step 1: Load schema ──────────────────────────────────────
        logger.log("\n── Step 1: Load schema ──")
        schema = self.storage.load_schema(schema_path)
        logger.log(f"✅ Schema loaded ({len(schema)} top-level keys)")

        # ── Step 2: Download / locate document ──────────────────────
        logger.log("\n── Step 2: Locate document ──")
        # Create temp file with neutral suffix — user input never touches
        # NamedTemporaryFile directly (CWE-22). After download, rename using
        # a sanitized copy of the original extension (basename only, whitelist-
        # checked) so the extractor can detect the file format correctly.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = tmp.name
        local_doc = self.storage.download_document(document_path, tmp_path)
        raw_ext = Path(os.path.basename(document_path)).suffix.lower()
        if raw_ext in _ALLOWED_EXTENSIONS:
            renamed = tmp_path[:-4] + raw_ext  # replace .tmp with correct ext
            os.rename(local_doc, renamed)
            local_doc = renamed
        logger.log(f"✅ Document ready at: {local_doc}")

        # ── Steps 3–6: Parallel threads ──────────────────────────────
        extraction_result: dict = {}
        api_result: dict = {}
        extraction_error: list = []
        api_error: list = []

        # ── Thread A: Extract + Upload ───────────────────────────────
        def extraction_thread():
            try:
                logger.log("\n[Thread A] ── Step 3: Extract ──")
                extracted = self.extractor.extract(
                    document_path=local_doc,
                    schema=schema,
                    telemetry=logger,
                )
                logger.log(f"[Thread A] ✅ Extracted ({len(extracted)} top-level keys)")

                logger.log("[Thread A] ── Step 4: Save output ──")
                self.storage.save_output(job_id, extracted)

                flat = flatten_dict(extracted)
                self.storage.save_output_flat(job_id, flat)
                logger.log(f"[Thread A] ✅ Saved (nested: {len(extracted)} keys, flat: {len(flat)} keys)")

                # If output_path given, also write there
                if output_path:
                    self.storage.upload_file(
                        self._write_tmp_json(extracted),
                        output_path,
                    )
                    logger.log(f"[Thread A] ✅ Uploaded to: {output_path}")

                extraction_result["extracted"] = extracted
                extraction_result["flat"] = flat
                extraction_result["success"] = True

            except Exception as e:
                extraction_error.append(str(e))
                logger.log_error("[Thread A] Extraction failed", exception=e)

        # ── Thread B: prepare embed (in-process) or make_embed_file (remote) ────
        def api_thread():
            from pdf_autofillr_doc_upload.pdf.inprocess_filler import InProcessMapperFiller

            if not self.pdf_filler:
                api_result["success"] = True
                api_result["skipped"] = True
                return

            is_inprocess = isinstance(self.pdf_filler, InProcessMapperFiller)

            if is_inprocess:
                # In-process: no separate embed step — just mark ready
                # The actual fill happens synchronously in Step 7
                if not effective_pdf_path:
                    logger.log("[Thread B] PDF filling skipped — DOC_UPLOAD_PDF_PATH not set")
                    api_result["success"] = True
                    api_result["skipped"] = True
                    return
                logger.log(f"[Thread B] In-process mapper — PDF: {effective_pdf_path}")
                api_result["success"] = True
                api_result["inprocess"] = True
                return

            # Remote HTTP/Lambda mode
            if not (user_id and pdf_doc_id and session_id):
                logger.log("[Thread B] PDF filling skipped (user_id / pdf_doc_id / session_id not provided)")
                api_result["success"] = True
                api_result["skipped"] = True
                return

            try:
                logger.log("\n[Thread B] ── Step 5: make_embed_file ──")
                ok = self.pdf_filler.make_embed_file(
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    session_id=session_id,
                    investor_type=investor_type,
                    use_second_mapper=True,
                )
                if not ok:
                    logger.log("[Thread B] ⚠️ make_embed_file failed, continuing to polling…")

                logger.log("[Thread B] ── Step 6: check_embed_file (polling) ──")
                ready, embed_path = self.pdf_filler.check_embed_file(
                    user_id=user_id,
                    pdf_doc_id=pdf_doc_id,
                    investor_type=investor_type,
                )
                if not ready:
                    raise RuntimeError("Embed file not ready after maximum wait time")

                logger.log(f"[Thread B] ✅ Embed file ready: {embed_path}")
                api_result["embed_path"] = embed_path
                api_result["success"] = True

            except Exception as e:
                api_error.append(str(e))
                logger.log_error("[Thread B] API thread failed", exception=e)

        thread_a = threading.Thread(target=extraction_thread, name="ExtractionThread")
        thread_b = threading.Thread(target=api_thread, name="APIThread")

        logger.log("\n🚀 Starting parallel threads…")
        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()
        logger.log("✅ Parallel threads complete")

        # ── Error check ──────────────────────────────────────────────
        if extraction_error:
            raise RuntimeError(f"Extraction failed: {extraction_error[0]}")
        if api_error:
            raise RuntimeError(f"API thread failed: {api_error[0]}")

        # ── Step 7: fill ─────────────────────────────────────────────
        filled_pdf_path = None

        if not self.pdf_filler or api_result.get("skipped"):
            logger.log("\n── Step 7: PDF filling skipped (no filler configured) ──")

        elif api_result.get("inprocess"):
            # In-process mapper fill
            from pdf_autofillr_doc_upload.pdf.inprocess_filler import InProcessMapperFiller
            logger.log("\n── Step 7: fill PDF (in-process mapper) ──")
            filler = self.pdf_filler
            # Update filler pdf_path if caller passed one explicitly
            if effective_pdf_path:
                filler.pdf_path = effective_pdf_path
            filled_pdf_path = filler.prepare_and_fill(
                data_flat=extraction_result.get("flat", {}),
                investor_type=investor_type,
                job_id=job_id,
                output_path=output_pdf_path,
            )
            logger.log(f"✅ PDF filled: {filled_pdf_path}")

        elif user_id and pdf_doc_id and session_id:
            # Remote Lambda fill
            logger.log("\n── Step 7: fill_pdf (remote Lambda) ──")
            fill_ok = self.pdf_filler.fill_pdf(
                user_id=user_id,
                pdf_doc_id=pdf_doc_id,
                session_id=session_id,
                use_profile_info=use_profile_info,
            )
            if not fill_ok:
                raise RuntimeError("fill_pdf failed")
            logger.log("✅ PDF filled successfully")

        # ── Step 8: save execution log ───────────────────────────────
        logger.log("\n── Step 8: Save execution log ──")
        summary = logger.finalize()
        self.storage.save_execution_log(job_id, summary)

        duration = time.time() - start_time
        self.telemetry.record_job_complete(
            job_id=job_id,
            duration_seconds=duration,
            fields_extracted=len(extraction_result.get("flat", {})),
            success=True,
        )

        logger.log(f"\n🎉 PIPELINE COMPLETE  ({duration:.1f}s)")
        logger.print_summary()

        return {
            "job_id": job_id,
            "output_nested": extraction_result.get("extracted", {}),
            "output_flat": extraction_result.get("flat", {}),
            "output_path": output_path,
            "filled_pdf_path": filled_pdf_path or api_result.get("embed_path"),
            "success": True,
            "errors": [],
        }

    # ── Helpers ───────────────────────────────────────────────────────


    def run_local_with_pdf(
        self,
        document_path: str,
        schema_path: str,
        pdf_path: Optional[str] = None,
        job_id: Optional[str] = None,
        investor_type: str = "Individual",
        output_json_path: Optional[str] = None,
        output_pdf_path: Optional[str] = None,
    ) -> dict:
        """
        Convenience method for local development: extract from a document
        AND fill a local blank PDF using the in-process mapper.

        Args:
            document_path:    Source document (PDF/DOCX/TXT/CSV/JSON/MD/...).
            schema_path:      Path to form_keys.json.
            pdf_path:         Blank PDF to fill. Falls back to DOC_UPLOAD_PDF_PATH env var.
            job_id:           Auto-generated UUID if not provided.
            investor_type:    e.g. "Individual".
            output_json_path: Where to save extracted JSON (optional).
            output_pdf_path:  Where to save filled PDF (optional).

        Returns:
            dict with keys: job_id, output_flat, output_nested, filled_pdf_path, success
        """
        import uuid
        from pdf_autofillr_doc_upload.pdf.inprocess_filler import InProcessMapperFiller

        job_id = job_id or str(uuid.uuid4())

        # Override filler with InProcessMapperFiller for this call
        filler = InProcessMapperFiller(
            pdf_path=pdf_path or os.getenv("DOC_UPLOAD_PDF_PATH", ""),
            config_dir=str(self.settings.config_path),
            data_path=str(self.settings.data_path),
        )

        # Step 1: extract
        result = self.run(
            document_path=document_path,
            schema_path=schema_path,
            job_id=job_id,
            output_path=output_json_path,
        )

        if not result["success"]:
            return result

        # Step 2: fill PDF in-process
        filled_path = filler.prepare_and_fill(
            data_flat=result["output_flat"],
            investor_type=investor_type,
            job_id=job_id,
            output_path=output_pdf_path,
        )

        result["filled_pdf_path"] = filled_path
        return result

    @staticmethod
    def _write_tmp_json(data: dict) -> str:
        import json
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(data, f, indent=2, default=str)
            return f.name