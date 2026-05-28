# chatbot/pdf/workflow.py
"""
PDFWorkflowManager — orchestration only.

All intermediate mapper files go to:
    {data_path}/{user_id}/sessions/{session_id}/mapper/

Final filled PDF (original location, unchanged):
    Local  -> {data_path}/{user_id}/sessions/{session_id}/filled.pdf

Copy with clean name also written to:
    Local  -> {data_path}/output/{user_id}/sessions/{session_id}/{pdf_name}_filled.pdf
    S3     -> uploaded to output_bucket at {user_id}/sessions/{session_id}/filled.pdf
    GCP    -> uploaded to output_bucket at {user_id}/sessions/{session_id}/filled.pdf
    Azure  -> uploaded to output_container at {user_id}/sessions/{session_id}/filled.pdf
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from chatbot.pdf.interface import PDFFillerInterface
from chatbot.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class PDFWorkflowManager:

    def __init__(
        self, filler: PDFFillerInterface, storage: StorageBackend, settings=None
    ):
        self.filler = filler
        self.storage = storage
        self.poll_interval = getattr(settings, "pdf_poll_interval", 10)
        self.poll_timeout = getattr(settings, "pdf_poll_timeout", 150)
        self.max_retries = getattr(settings, "pdf_max_retries", 3)
        self.max_poll_attempts = self.poll_timeout // max(self.poll_interval, 1)
        self._storage_type = self._detect_storage_type(storage)
        self._data_path = getattr(storage, "data_path", None) or os.getenv(
            "chatbot_DATA_PATH", "./data/chatbot"
        )

    # ------------------------------------------------------------------
    # Storage detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_storage_type(storage) -> str:
        cls = type(storage).__name__
        if "S3" in cls:
            return "s3"
        if "GCS" in cls or "Gcp" in cls:
            return "gcp"
        if "Azure" in cls:
            return "azure"
        return "local"

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _mapper_dir(self, user_id: str, session_id: str) -> str:
        """Local dir for intermediate mapper files (extract/map/embed)."""
        d = Path(str(self._data_path)) / user_id / "sessions" / session_id / "mapper"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def _local_filled_pdf_path(self, user_id: str, session_id: str) -> str:
        """Local path where Java filler writes the filled PDF (original location)."""
        p = Path(str(self._data_path)) / user_id / "sessions" / session_id
        p.mkdir(parents=True, exist_ok=True)
        return str(p / "filled.pdf")

    def _output_filled_pdf_path(
        self, user_id: str, session_id: str, pdf_path: str
    ) -> str:
        """
        Clean output copy path:
            {data_path}/output/{user_id}/sessions/{session_id}/{pdf_name}_filled.pdf
        """
        pdf_stem = Path(pdf_path).stem
        out_dir = (
            Path(str(self._data_path)) / "output" / user_id / "sessions" / session_id
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        return str(out_dir / f"{pdf_stem}_filled.pdf")

    # ------------------------------------------------------------------
    # Cloud upload
    # ------------------------------------------------------------------

    def _upload_filled_pdf(self, user_id: str, session_id: str, local_path: str) -> str:
        """
        Upload filled PDF to cloud bucket if using a cloud backend.
        Returns cloud URI for cloud backends, local path for local.
        """
        key = f"{user_id}/sessions/{session_id}/filled.pdf"

        if self._storage_type == "s3":
            try:
                self.storage.s3.upload_file(
                    local_path,
                    self.storage.output_bucket,
                    key,
                    ExtraArgs={"ContentType": "application/pdf"},
                )
                return f"s3://{self.storage.output_bucket}/{key}"
            except Exception as e:
                raise RuntimeError(f"S3 upload of filled PDF failed: {e}") from e

        if self._storage_type == "gcp":
            try:
                blob = self.storage._out.blob(key)
                blob.upload_from_filename(local_path, content_type="application/pdf")
                return f"gs://{self.storage.output_bucket}/{key}"
            except Exception as e:
                raise RuntimeError(f"GCS upload of filled PDF failed: {e}") from e

        if self._storage_type == "azure":
            try:
                blob_client = self.storage._out.get_blob_client(key)
                with open(local_path, "rb") as f:
                    blob_client.upload_blob(f, overwrite=True)
                return f"azure://{self.storage.output_container}/{key}"
            except Exception as e:
                raise RuntimeError(f"Azure upload of filled PDF failed: {e}") from e

        return local_path  # local — already at correct path

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def trigger_prepare_async(
        self, user_id: str, session_id: str, pdf_path: str, investor_type: str
    ) -> None:
        threading.Thread(
            target=self._prepare_worker,
            args=(user_id, session_id, pdf_path, investor_type),
            daemon=True,
        ).start()

    def trigger_async(
        self,
        user_id: str,
        session_id: str,
        pdf_path: str,
        investor_type: str,
        data_flat: dict,
    ) -> None:
        threading.Thread(
            target=self._fill_worker,
            args=(user_id, session_id, pdf_path, investor_type, data_flat),
            daemon=False,
        ).start()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def _prepare_worker(self, user_id, session_id, pdf_path, investor_type):
        try:
            doc_id = self._call_prepare(user_id, session_id, pdf_path, investor_type)
            self._log_step(user_id, session_id, "prepare", success=True, doc_id=doc_id)
            session = self.storage.get_session_state(user_id, session_id) or {}
            session["pdf_doc_id"] = doc_id
            self.storage.save_session_state(user_id, session_id, session)
        except Exception as e:
            self._log_step(user_id, session_id, "prepare", success=False, error=str(e))

    def _fill_worker(self, user_id, session_id, pdf_path, investor_type, data_flat):
        try:
            session = self.storage.get_session_state(user_id, session_id) or {}
            doc_id = session.get("pdf_doc_id")

            if not doc_id:
                doc_id = self._call_prepare(
                    user_id, session_id, pdf_path, investor_type
                )
                session["pdf_doc_id"] = doc_id
                self.storage.save_session_state(user_id, session_id, session)
                self._log_step(
                    user_id, session_id, "prepare", success=True, doc_id=doc_id
                )

            ready = self._poll_ready(user_id, session_id, doc_id)
            if not ready:
                doc_id = self._call_prepare(
                    user_id, session_id, pdf_path, investor_type
                )
                session["pdf_doc_id"] = doc_id
                self.storage.save_session_state(user_id, session_id, session)
                time.sleep(180)
                ready = self._poll_ready(user_id, session_id, doc_id)

            if not ready:
                self._log_step(
                    user_id,
                    session_id,
                    "check",
                    success=False,
                    error="Timeout waiting for document",
                )
                return

            # Java filler always writes to local disk first (original location preserved)
            local_filled_path = self._local_filled_pdf_path(user_id, session_id)

            result = None
            for attempt in range(self.max_retries):
                try:
                    result = self._call_fill(doc_id, data_flat, local_filled_path)
                    if result:
                        break
                except Exception as e:
                    self._log_step(
                        user_id,
                        session_id,
                        "fill",
                        success=False,
                        error=str(e),
                        attempt=attempt,
                    )
                    time.sleep(5 * (attempt + 1))

            if result:
                # Upload to cloud if needed, get final URI/path
                final_path = self._upload_filled_pdf(
                    user_id, session_id, local_filled_path
                )

                # Also copy a clean {pdf_name}_filled.pdf to the output dir (local only)
                output_copy_path = None
                if self._storage_type == "local" and os.path.exists(local_filled_path):
                    try:
                        output_copy_path = self._output_filled_pdf_path(
                            user_id, session_id, pdf_path
                        )
                        shutil.copy2(local_filled_path, output_copy_path)
                    except Exception as copy_err:
                        # Non-fatal — original filled.pdf is still intact
                        self._log_step(
                            user_id,
                            session_id,
                            "fill_copy",
                            success=False,
                            error=str(copy_err),
                        )
                        output_copy_path = None

                self._log_step(
                    user_id,
                    session_id,
                    "fill",
                    success=True,
                    local_path=local_filled_path,
                    final_path=final_path,
                    output_copy_path=output_copy_path,
                    storage_type=self._storage_type,
                )
                session = self.storage.get_session_state(user_id, session_id) or {}
                session["filled_pdf_path"] = final_path
                session["filled_pdf_local"] = local_filled_path
                if output_copy_path:
                    session["filled_pdf_output"] = output_copy_path
                self.storage.save_session_state(user_id, session_id, session)

                # ── RAG API 2: post-fill vector learning ──────────────────
                # Runs after every successful fill to update vector confidence
                # scores and create new vectors from LLM predictions.
                # Fully non-blocking — a failure here never affects the fill result.
                self._call_rag_api2(user_id, session_id, data_flat)

        except Exception as e:
            self._log_step(user_id, session_id, "fill", success=False, error=str(e))

    # ------------------------------------------------------------------
    # RAG API 2 — post-fill learning
    # ------------------------------------------------------------------

    def _call_rag_api2(self, user_id: str, session_id: str, data_flat: dict) -> None:
        """
        Call RAGPDFClient.save_filled_pdf() (API 2) after a successful fill.

        This runs the full post-fill processing pipeline:
            1. Case classification  (RAG vs LLM vs both vs neither per field)
            2. Metrics calculation
            3. Vector confidence updates (boost correct, decay wrong)
            4. New vector creation for fields the RAG missed but LLM got right
            5. Time series update

        Reads llm_predictions.json and final_predictions.json from the mapper's
        session_dir (written there by InProcessMapperFiller._prepare_with_rag).
        These files are only present when rag_enabled=True — if they don't exist
        (RAG disabled or plain orchestrator path), this method exits silently.

        All exceptions are caught and logged — a RAG failure must never surface
        to the user or abort the fill result.
        """
        # Only runs when RAG was enabled for this filler
        if not self._is_rag_enabled():
            return

        try:
            from ragpdf import RAGPDFClient
        except ImportError:
            logger.debug(
                "_call_rag_api2: ragpdf SDK not installed — skipping post-fill learning"
            )
            return

        try:
            # Get prediction file paths from the filler (InProcessMapperFiller exposes them)
            pred_paths = self._get_prediction_paths(user_id, session_id)
            if not pred_paths:
                logger.debug(
                    "_call_rag_api2: no prediction paths available (RAG may not have run) — skip"
                )
                return

            llm_path = pred_paths.get("llm_predictions")
            final_path = pred_paths.get("final_predictions")
            rag_uid = pred_paths.get("user_id", user_id)
            rag_sid = pred_paths.get("session_id", session_id)
            rag_pid = pred_paths.get("pdf_id", session_id)

            if not llm_path or not final_path:
                logger.debug(
                    "_call_rag_api2: llm_predictions=%s final_predictions=%s — "
                    "one or both missing, skipping API 2",
                    llm_path,
                    final_path,
                )
                return

            if not Path(llm_path).exists() or not Path(final_path).exists():
                logger.debug(
                    "_call_rag_api2: prediction files do not exist on disk — "
                    "RAG step likely did not run (rag_enabled may be false in mapper config)"
                )
                return

            with open(llm_path, encoding="utf-8") as f:
                llm_predictions = json.load(f)
            with open(final_path, encoding="utf-8") as f:
                final_predictions = json.load(f)

            logger.info(
                "_call_rag_api2: calling save_filled_pdf — user=%s session=%s pdf=%s",
                rag_uid,
                rag_sid,
                rag_pid,
            )

            client = RAGPDFClient.from_env()
            result = client.save_filled_pdf(
                user_id=str(rag_uid),
                session_id=str(rag_sid),
                pdf_id=str(rag_pid),
                llm_predictions=llm_predictions,
                final_predictions=final_predictions,
                filled_pdf_location=None,
            )

            vectors_created = (result.get("vector_updates") or {}).get(
                "vectors_created", 0
            )
            vectors_updated = (result.get("vector_updates") or {}).get(
                "vectors_updated", 0
            )
            logger.info(
                "_call_rag_api2: done — vectors_created=%d vectors_updated=%d",
                vectors_created,
                vectors_updated,
            )

        except Exception as e:
            # Non-fatal — log at WARNING level and continue
            logger.warning(
                "_call_rag_api2: post-fill RAG learning failed (non-fatal): %s",
                e,
                exc_info=True,
            )

    def _is_rag_enabled(self) -> bool:
        """Return True if the filler has RAG enabled."""
        # Check the filler itself (InProcessMapperFiller exposes _mapper_config)
        mapper_config = getattr(self.filler, "_mapper_config", None)
        if mapper_config is not None:
            return bool(getattr(mapper_config, "rag_enabled", False))
        # Fallback: read the env var directly
        return os.getenv("RAG_ENABLED", "false").lower() == "true"

    def _get_prediction_paths(self, user_id: str, session_id: str) -> dict | None:
        """
        Retrieve prediction file paths from the filler.

        InProcessMapperFiller exposes get_rag_prediction_paths() after
        prepare_document() completes.  Returns None if not available.
        """
        get_paths = getattr(self.filler, "get_rag_prediction_paths", None)
        if callable(get_paths):
            return get_paths()
        return None

    # ------------------------------------------------------------------
    # Filler call helpers — graceful fallback for old/HTTP filler signatures
    # ------------------------------------------------------------------

    def _call_prepare(self, user_id, session_id, pdf_path, investor_type) -> str:
        session_dir = self._mapper_dir(user_id, session_id)
        try:
            return self.filler.prepare_document(
                pdf_path, investor_type, session_dir=session_dir
            )
        except TypeError:
            return self.filler.prepare_document(pdf_path, investor_type)

    def _call_fill(self, doc_id, data_flat, output_path):
        try:
            return self.filler.fill_document(doc_id, data_flat, output_path=output_path)
        except TypeError:
            return self.filler.fill_document(doc_id, data_flat)

    def _poll_ready(self, user_id, session_id, doc_id) -> bool:
        for attempt in range(self.max_poll_attempts):
            try:
                if self.filler.check_document_ready(doc_id):
                    self._log_step(
                        user_id, session_id, "check", success=True, attempt=attempt
                    )
                    return True
            except Exception:
                pass  # intentional
            self._log_step(
                user_id,
                session_id,
                "check",
                success=False,
                attempt=attempt,
                ready=False,
            )
            time.sleep(self.poll_interval)
        return False

    def _log_step(self, user_id, session_id, step, **kwargs):
        existing = self.storage.get_pdf_filling_logs(user_id, session_id) or {
            "steps": []
        }
        existing.setdefault("steps", []).append(
            {
                "step": step,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **kwargs,
            }
        )
        self.storage.save_pdf_filling_logs(user_id, session_id, existing)
