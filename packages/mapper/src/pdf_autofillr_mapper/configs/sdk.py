"""
SDK Storage Configuration

A storage config for SDK / library use where the caller supplies only
file paths — no user_id, session_id, or pdf_doc_id required.

All internal pipeline paths are derived automatically from the PDF stem
and a single output directory.  Cloud storage attributes are set to None
so the operations fall through to local-file logic.

JSON path semantics
-------------------
``global_json_path``
    Keys-only schema file — tells the mapper what fields the form should
    produce (e.g. ``{"firstName": "", "lastName": ""}``).  Used during the
    **extract → map → embed** pipeline.  Consumed by ``handle_map_operation``
    via ``config.local_input_json``.

``input_json_path``
    Actual per-user data file — the values to fill into a prepared PDF
    (e.g. ``{"firstName": "Jane", "lastName": "Doe"}``).  Used during the
    **fill** pipeline.  Consumed by ``handle_fill_operation`` via
    ``config.local_input_json``.

Exactly one of the two must be provided; both may be provided when a
single config object is needed for the full extract→map→embed→fill
pipeline (though PDFMapper.process() creates two separate configs to
keep the stages clean).
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from .local import LocalStorageConfig


class SDKStorageConfig(LocalStorageConfig):
    """
    Storage config for embedded SDK use.

    For the **embed pipeline** (extract → map → embed), pass *global_json_path*:

        cfg = SDKStorageConfig(
            pdf_path="application.pdf",
            global_json_path="schema_keys.json",
            output_dir="/tmp/my_output",
        )

    For the **fill pipeline**, pass *input_json_path*:

        cfg = SDKStorageConfig(
            pdf_path="application.pdf",
            input_json_path="investor_data.json",
            output_dir="/tmp/my_output",
        )

    Exactly one (or both) must be supplied; at least one is required.
    """

    def __init__(
        self,
        pdf_path: str,
        global_json_path: Optional[str] = None,
        input_json_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """
        Args:
            pdf_path:
                Absolute or relative path to the input PDF.
            global_json_path:
                Path to the global JSON schema (keys only, empty values).
                Required for extract / map / embed phases.
            input_json_path:
                Path to the per-user data JSON (actual values).
                Required for the fill phase.
            output_dir:
                Directory where all intermediate and final files are written.
                Created if it does not exist.
                Defaults to a ``pdf_mapper_<stem>`` sub-directory inside the
                system temp dir.

        Raises:
            ValueError: if neither *global_json_path* nor *input_json_path*
                is provided.
        """
        if not global_json_path and not input_json_path:
            raise ValueError(
                "SDKStorageConfig requires at least one of "
                "global_json_path or input_json_path."
            )

        pdf_path = os.path.abspath(pdf_path)

        stem = Path(pdf_path).stem  # e.g. "application" from "application.pdf"

        if output_dir is None:
            import tempfile
            output_dir = os.path.join(tempfile.gettempdir(), f"pdf_mapper_{stem}")

        output_dir = os.path.abspath(output_dir)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Initialise LocalStorageConfig (sets source_type="local", creates base_dir)
        super().__init__(base_dir=output_dir)

        # ── Input files ──────────────────────────────────────────────────────
        self.local_input_pdf = pdf_path

        # Global JSON: keys-only schema (e.g. {"firstName": "", "lastName": ""})
        # Read by handle_map_operation via input_handler.get_input('global_json').
        # Only set when this config is used for the embed pipeline.
        self.local_global_json = os.path.abspath(global_json_path) \
            if global_json_path else None

        # Input JSON: per-user data (e.g. {"firstName": "Jane", "lastName": "Doe"})
        # Read by handle_fill_operation via input_handler.get_input('input_json').
        # Only set when this config is used for the fill pipeline.
        self.local_input_json = os.path.abspath(input_json_path) \
            if input_json_path else None

        # ── Pipeline output files ─────────────────────────────────────────────
        self.local_extracted_json  = os.path.join(output_dir, f"{stem}_extracted.json")
        self.local_mapped_json     = os.path.join(output_dir, f"{stem}_mapped_fields.json")
        self.local_radio_json      = os.path.join(output_dir, f"{stem}_radio_groups.json")
        self.local_embedded_pdf    = os.path.join(output_dir, f"{stem}_embedded.pdf")
        self.local_filled_pdf      = os.path.join(output_dir, f"{stem}_filled.pdf")
        self.dest_embedded_pdf     = self.local_embedded_pdf

        # ── RAG / headers (only used when use_second_mapper=True) ─────────────
        self.local_header_file          = os.path.join(output_dir, f"{stem}_header_file.json")
        self.local_section_file         = os.path.join(output_dir, f"{stem}_section_file.json")
        self.local_rag_predictions      = os.path.join(output_dir, f"{stem}_rag_predictions.json")
        self.local_headers_with_fields  = os.path.join(output_dir, f"{stem}_headers_with_fields.json")
        self.local_final_form_fields    = os.path.join(output_dir, f"{stem}_final_form_fields.json")

        # ── Cloud paths — all None in SDK mode ───────────────────────────────
        self.s3_input_pdf       = None
        self.s3_input_json      = None
        self.s3_global_json     = None
        self.s3_extracted_json  = None
        self.s3_mapped_json     = None
        self.s3_embedded_json   = None
        self.s3_rag_predictions = None

        self.azure_input_pdf = None
        self.gcp_input_pdf   = None

    # ── Convenience ──────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a dict of all configured paths — useful for debugging."""
        return {
            "source_type":              self.source_type,
            "local_input_pdf":          self.local_input_pdf,
            "local_global_json":        self.local_global_json,   # embed pipeline only
            "local_input_json":         self.local_input_json,    # fill pipeline only
            "local_extracted_json":     self.local_extracted_json,
            "local_mapped_json":        self.local_mapped_json,
            "local_radio_json":         self.local_radio_json,
            "local_embedded_pdf":       self.local_embedded_pdf,
            "local_filled_pdf":         self.local_filled_pdf,
            "local_header_file":        self.local_header_file,
            "local_section_file":       self.local_section_file,
            "local_rag_predictions":    self.local_rag_predictions,
        }

    def __repr__(self) -> str:
        return (
            f"SDKStorageConfig("
            f"pdf={os.path.basename(self.local_input_pdf)!r}, "
            f"output_dir={self.base_dir!r})"
        )