# pdf_autofillr_doc_upload/pdf/inprocess_filler.py

"""

InProcessMapperFiller — connects doc_upload to pdf-autofillr-mapper directly.



Runs the mapper in the same Python process (no HTTP, no Lambda).

Identical to chatbot-final's MapperPDFFiller in-process mode.



This is the right filler for local testing when you have:

  - A blank PDF on disk

  - The mapper module installed

  - No Lambda / cloud setup



Usage::



    # Auto (env-driven — set DOC_UPLOAD_PDF_FILLER=mapper_local)

    client = DocUploadClient()



    # Explicit

    from pdf_autofillr_doc_upload.pdf.inprocess_filler import InProcessMapperFiller

    filler = InProcessMapperFiller(

        pdf_path="data/input/blank_form.pdf",

        config_dir="./configs",

    )

    client = DocUploadClient(pdf_filler=filler)



Env vars::

    DOC_UPLOAD_PDF_FILLER     mapper_local

    DOC_UPLOAD_PDF_PATH       path to the blank PDF

    DOC_UPLOAD_CONFIG_PATH    path to configs/ dir (default: ./configs)

    DOC_UPLOAD_DATA_PATH      data root for mapper output  (default: ./data/doc_upload)

"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from pdf_autofillr_doc_upload.pdf.interface import PDFFillerInterface


class InProcessMapperFiller(PDFFillerInterface):
    """

    Fills a local blank PDF using pdf-autofillr-mapper in-process.



    Steps (mirrors chatbot PDFWorkflowManager):

        1. prepare_document  — mapper embeds field metadata into the PDF

        2. check_document_ready — polls until embed is done

        3. fill_document     — Java filler writes values into the PDF



    Args:

        pdf_path:   Path to the blank source PDF.

        config_dir: Directory containing mapper_config.ini + form_keys.json.

        data_path:  Root for all intermediate + output files.

        poll_interval: Seconds between ready-checks (default 5).

        poll_timeout:  Max seconds to wait for embed (default 150).

        max_retries:   Fill retry attempts (default 3).

    """

    def __init__(
        self,
        pdf_path: str | None = None,
        config_dir: str | None = None,
        data_path: str | None = None,
        poll_interval: int = 5,
        poll_timeout: int = 150,
        max_retries: int = 3,
    ):

        self.pdf_path = (
            pdf_path
            or os.getenv("DOC_UPLOAD_PDF_PATH")
            or os.getenv("chatbot_PDF_PATH", "")
        )

        self.config_dir = config_dir or os.getenv("DOC_UPLOAD_CONFIG_PATH", "./configs")

        self.data_path = data_path or os.getenv(
            "DOC_UPLOAD_DATA_PATH", "./data/doc_upload"
        )

        self.poll_interval = poll_interval

        self.poll_timeout = poll_timeout

        self.max_retries = max_retries

        self._impl = None

        # Filled PDF output path — set after fill_document() succeeds

        self.filled_pdf_path: str | None = None

    # ── PDFFillerInterface stubs (not used in local mode) ──────────────────

    def make_embed_file(
        self, user_id, pdf_doc_id, session_id, investor_type, use_second_mapper=True
    ) -> bool:
        """Not used for in-process filling — prepare_and_fill() handles everything."""

        return True

    def check_embed_file(
        self, user_id, pdf_doc_id, investor_type, max_attempts=48, wait_interval=10
    ):
        """Not used for in-process filling."""

        return True, self.pdf_path

    def fill_pdf(self, user_id, pdf_doc_id, session_id, use_profile_info=True) -> bool:
        """Not used for in-process filling — use prepare_and_fill() instead."""

        return True

    # ── Main local API ─────────────────────────────────────────────────────

    def prepare_and_fill(
        self,
        data_flat: dict,
        investor_type: str = "Individual",
        job_id: str = "local",
        output_path: str | None = None,
    ) -> str:
        """

        Full local pipeline: prepare -> wait -> fill -> return filled PDF path.



        Args:

            data_flat:     Flat dot-notation dict from Extractor (output_flat).

            investor_type: Investor type string.

            job_id:        Used to build intermediate file paths.

            output_path:   Where to write the filled PDF.

                           Defaults to {data_path}/output/{job_id}/{pdf_stem}_filled.pdf



        Returns:

            Path to the filled PDF.



        Raises:

            RuntimeError: If mapper is not installed, PDF not found, or fill fails.

        """

        impl = self._get_impl()

        if not self.pdf_path or not Path(self.pdf_path).exists():

            raise FileNotFoundError(
                f"Blank PDF not found: {self.pdf_path!r}\n"
                "Set DOC_UPLOAD_PDF_PATH in .env or pass pdf_path= to InProcessMapperFiller."
            )

        # ── Session dir for mapper intermediates ──────────────────────

        session_dir = Path(self.data_path or "") / "jobs" / job_id / "mapper"

        session_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: prepare (embed metadata) ─────────────────────────

        print(f"📄 Preparing PDF: {self.pdf_path}")

        try:

            doc_id = impl.prepare_document(
                self.pdf_path, investor_type, session_dir=str(session_dir)
            )

        except TypeError:

            doc_id = impl.prepare_document(self.pdf_path, investor_type)

        print(f"   doc_id = {doc_id}")

        # ── Step 2: poll until ready ──────────────────────────────────

        print(f"⏳ Waiting for embed file (max {self.poll_timeout}s) …")

        max_attempts = self.poll_timeout // max(self.poll_interval, 1)

        ready = False

        for attempt in range(max_attempts):

            try:

                if impl.check_document_ready(doc_id):

                    ready = True

                    print(f"   ✅ Embed ready after {attempt * self.poll_interval}s")

                    break

            except Exception:

                pass

            time.sleep(self.poll_interval)

        if not ready:

            raise RuntimeError(
                f"Embed file not ready after {self.poll_timeout}s. "
                "Check that Java is on PATH and mapper_config.ini is correct."
            )

        # ── Step 3: fill ──────────────────────────────────────────────

        if output_path is None:

            pdf_stem = Path(self.pdf_path).stem

            out_dir = Path(self.data_path or "") / "output" / job_id

            out_dir.mkdir(parents=True, exist_ok=True)

            output_path = str(out_dir / f"{pdf_stem}_filled.pdf")

        print(f"📝 Filling PDF -> {output_path}")

        result = None

        for attempt in range(self.max_retries):

            try:

                result = impl.fill_document(doc_id, data_flat, output_path=output_path)

                if result:

                    break

            except TypeError:

                result = impl.fill_document(doc_id, data_flat)

                if result:

                    break

            except Exception as e:

                print(f"   ⚠️  Fill attempt {attempt+1} failed: {e}")

                time.sleep(3 * (attempt + 1))

        if not result:

            raise RuntimeError("fill_document failed after all retries.")

        # mapper writes to the output_path; also make a clean copy if needed

        if not Path(output_path).exists():

            # Some mapper versions write to the session dir — search for it

            candidates = list(session_dir.glob("*filled*.pdf")) + list(
                session_dir.glob("*.pdf")
            )

            if candidates:

                shutil.copy2(str(candidates[0]), output_path)

        self.filled_pdf_path = output_path

        print(f"✅ PDF filled: {output_path}")

        return output_path

    # ── Impl loader ────────────────────────────────────────────────────────

    def _get_impl(self):

        if self._impl is not None:

            return self._impl

        try:

            from pdf_autofillr_mapper.inprocess_filler import (
                InProcessMapperFiller as _Impl,
            )

            self._impl = _Impl(config_dir=self.config_dir)

            return self._impl

        except ImportError as e:

            raise ImportError(
                "pdf-autofillr-mapper is required for in-process filling.\n"
                "Install it: pip install -e ../mapper --no-cache-dir --no-deps"
            ) from e
