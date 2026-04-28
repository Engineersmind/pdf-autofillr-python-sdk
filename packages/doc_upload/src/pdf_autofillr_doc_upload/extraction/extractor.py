# pdf_autofillr_doc_upload/extraction/extractor.py
"""
Extractor — orchestrates document reading -> prompt -> LLM -> schema enforcement.

This is the heart of the module, porting the Lambda extractor_logic.py into a
clean, reusable class with:
  - Multi-format document reading (PDF, DOCX, PPTX, XLSX, CSV, JSON, MD, TXT …)
  - LiteLLM for any model (not just OpenAI)
  - Schema enforcement so the output always matches the provided structure
  - Address normalisation (line1/line2 split)
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pdf_autofillr_doc_upload.extraction.document_reader import DocumentReader
from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "You are a JSON extraction engine. Return only valid JSON, no markdown fences."


def _build_prompt(document_text: str, schema: dict) -> str:
    return f"""You are an extraction engine.

STRICT RULES:
- Follow the schema exactly — preserve all nested objects and keys.
- Extract every piece of information present in the document.
- Missing fields -> use "" for strings, false for booleans.
- No hallucination — only extract what is explicitly present.
- Return ONLY the JSON object shown below, fully populated.

SCHEMA:
{json.dumps(schema, indent=2)}

DOCUMENT:
\"\"\"{document_text}\"\"\"

Return:
{{
  "filled_form_keys": {json.dumps(schema, indent=2)}
}}"""


def _enforce_schema(llm_data: Any, schema: Any) -> Any:
    """
    Recursively enforce schema structure on LLM output.
    Ensures every key exists and has the right type.
    """
    if isinstance(schema, dict):
        fixed = {}
        for k, sub in schema.items():
            fixed[k] = _enforce_schema(llm_data.get(k) if isinstance(llm_data, dict) else None, sub)
        return fixed
    if isinstance(schema, bool):
        return bool(llm_data) if isinstance(llm_data, bool) else False
    if isinstance(schema, str):
        return str(llm_data) if llm_data is not None else ""
    return ""


def _normalize_address(full: str):
    """
    Split a full address string into line1 / line2.

    "123 Main St, Apt 4, London" -> ("123 Main St, Apt 4", "London")
    """
    if not full or not isinstance(full, str):
        return "", ""
    parts = [p.strip() for p in full.split(",") if p.strip()]
    if len(parts) == 1:
        return parts[0], ""
    return ", ".join(parts[:2]), ", ".join(parts[2:])


def _apply_address_normalization(data: dict) -> dict:
    """Apply line1/line2 split to all address groups."""
    groups = ["address_registered", "address_mailing", "address_jurisdiction"]
    for key in groups:
        if key in data:
            full = data[key].get(f"{key}_line1_id", "")
            l1, l2 = _normalize_address(full)
            data[key][f"{key}_line1_id"] = l1
            data[key][f"{key}_line2_id"] = l2

    # Wiring address — nested one level deeper
    if "wiring_details" in data:
        wd = data["wiring_details"]
        for sub_key in ("address", "wiring_address"):
            if sub_key in wd:
                full = wd[sub_key].get("wiring_details_address_line1_id", "")
                l1, l2 = _normalize_address(full)
                wd[sub_key]["wiring_details_address_line1_id"] = l1
                wd[sub_key]["wiring_details_address_line2_id"] = l2
    return data


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten a nested dict to dot-notation keys."""
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


class Extractor:
    """
    Full extraction pipeline: read document -> build prompt -> call LLM ->
    enforce schema -> normalize addresses.

    Args:
        llm_client: LLMClient instance. Created from env vars if not provided.
        reader:     DocumentReader instance.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        reader: Optional[DocumentReader] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.reader = reader or DocumentReader()

    def extract(
        self,
        document_path: str,
        schema: dict,
        telemetry=None,
    ) -> dict:
        """
        Extract structured data from a document.

        Args:
            document_path: Local path to the document.
            schema:        The form schema dict (e.g. form_keys.json content).
            telemetry:     Optional TelemetryCollector for logging.

        Returns:
            Cleaned and normalized dict matching the schema structure.
        """
        # ── Step 1: read document ──────────────────────────────────────
        logger.info("Extracting text from: %s", document_path)
        if telemetry:
            telemetry.log(f"📄 Reading document: {document_path}")

        document_text = self.reader.read(document_path)

        if telemetry:
            telemetry.log(f"✅ Text extracted ({len(document_text):,} characters)")

        # ── Step 2: call LLM ───────────────────────────────────────────
        prompt = _build_prompt(document_text, schema)

        if telemetry:
            telemetry.log(f"🤖 Calling LLM ({self.llm.model}) …")

        raw = self.llm.complete(system_prompt=_SYSTEM_PROMPT, user_prompt=prompt)

        # ── Step 3: parse JSON ─────────────────────────────────────────
        # Strip optional markdown fences
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("```", 2)[1]
            if raw_clean.startswith("json"):
                raw_clean = raw_clean[4:]
            raw_clean = raw_clean.rsplit("```", 1)[0].strip()

        llm_out = json.loads(raw_clean)

        # ── Step 4: enforce schema ─────────────────────────────────────
        cleaned = _enforce_schema(llm_out.get("filled_form_keys", llm_out), schema)

        # ── Step 5: address normalization ──────────────────────────────
        cleaned = _apply_address_normalization(cleaned)

        if telemetry:
            telemetry.log(f"✅ Extraction complete ({len(cleaned)} top-level keys)")

        return cleaned
