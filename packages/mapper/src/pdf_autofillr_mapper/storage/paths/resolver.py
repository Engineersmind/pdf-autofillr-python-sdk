"""
PathResolver - generates all file paths from job parameters.

Single source of truth for every filename in the pipeline.
Delegates base-path resolution to StorageConfig.

Prod path structure (bucket: pdf-fillr-production):
  Input PDF (uploaded by caller before invoking mapper):
    shared/input-pdfs/{env_folder}/{uid}/sessions/{sid}/pdfs/{pid}/{filename}.pdf

  Mapper outputs:
    {env_folder}/{user_type}/{uid}/sessions/{sid}/mapper/{pid}/{pid}_*.json|pdf

  RAG inputs (written by mapper, read by RAG API 1):
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/input/header_file.json
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/input/section_file.json

  RAG predictions:
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/predictions/rag_predictions.json
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/predictions/llm_predictions.json
    {env_folder}/{user_type}/{uid}/sessions/{sid}/rag/{pid}/predictions/final_predictions.json

  Session handoff (written by chatbot/doc_upload, read by mapper fill stage):
    {env_folder}/{user_type}/{uid}/sessions/{sid}/final_output_flat.json

  Shared / global:
    shared/pdf-cache/pdf-registry/hash_registry.json
    shared/filled_pdf_store/{env_folder}/{uid}/{sid}/{pid}/filled.pdf
    shared/unpredicted_fields/{env_folder}/{uid}/{sid}/{pid}/unpredicted_fields.json
    config/form_keys_flat.json   ← global input schema for mapper Phase 1

Adding a new pipeline file = add one method here, nowhere else.
"""

import os

# ── Filename constants ────────────────────────────────────────────────────────
# All mapper output files are prefixed with {pid}_ per the prod spec.
# Changing a name? Update it here — one place, all paths follow.

# Input files
_INPUT_PDF = "{pid}_input.pdf"  # mapper/{pid}/{pid}_input.pdf  (fetched via API, stored in mapper folder)
_GLOBAL_JSON = "form_keys_flat.json"  # config/form_keys_flat.json
_INPUT_JSON = "final_output_flat.json"  # session root handoff file

# Mapper output files — all prefixed with {pid}_
_EXTRACTED_JSON = "{pid}_extracted.json"
_MAPPED_JSON = "{pid}_mapping.json"
_RADIO_JSON = "{pid}_radio_groups.json"
_HEADERS_FIELDS = "{pid}_headers_with_fields.json"
_FINAL_FIELDS = "{pid}_final_form_fields.json"
_JAVA_MAPPING = "{pid}_final_mapping_json_combined.json"
_EMBEDDED_PDF = "{pid}_embedded.pdf"
_FILLED_PDF = "{pid}_filled.pdf"

# RAG input files (written by mapper into rag/{pid}/input/)
_HEADER_FILE = "header_file.json"
_SECTION_FILE = "section_file.json"

# RAG prediction files (rag/{pid}/predictions/)
_RAG_PRED = "rag_predictions.json"
_LLM_PRED = "llm_predictions.json"
_FINAL_PRED = "final_predictions.json"

# Shared global files
_CACHE_REGISTRY = "hash_registry.json"
_UNPREDICTED_FIELDS = "unpredicted_fields.json"


def _f(template: str, pid) -> str:
    """Resolve a filename template that may contain {pid}."""
    return template.replace("{pid}", str(pid))


class PathResolver:
    """
    Generates remote (storage) and local (processing) paths for every file
    in the mapper pipeline.

    Remote paths  → S3 / Azure / GCS / local-data-dir
    Local paths   → /tmp/processing/<uuid>/ for in-flight work

    All methods take (uid, sid, pid).  StorageConfig handles env_folder and
    user_type internally (set once at construction from env/developer_id).
    """

    def __init__(self, storage_config):
        self._sc = storage_config

    # ── Remote input paths ────────────────────────────────────────────────────

    def remote_input_pdf(self, uid, sid, pid) -> str:
        """Input PDF — stored in mapper folder after fetching via API."""
        return self._sc.mapper_path(uid, sid, pid, _f(_INPUT_PDF, pid))

    def remote_global_json(self) -> str:
        """Global input schema — s3://pdf-fillr-production/config/form_keys_flat.json.
        Overridable via GLOBAL_INPUT_JSON_S3_URI env var."""
        import os

        override = os.environ.get("GLOBAL_INPUT_JSON_S3_URI", "")
        if override:
            return override
        return self._sc.config_path(_GLOBAL_JSON)

    def remote_input_json(self, uid, sid) -> str:
        """Session handoff file — final_output_flat.json at session root."""
        return self._sc.session_root_path(uid, sid, _INPUT_JSON)

    # ── Remote mapper output paths ────────────────────────────────────────────

    def remote_extracted(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_EXTRACTED_JSON, pid))

    def remote_mapped(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_MAPPED_JSON, pid))

    def remote_radio(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_RADIO_JSON, pid))

    def remote_headers_with_fields(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_HEADERS_FIELDS, pid))

    def remote_final_form_fields(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_FINAL_FIELDS, pid))

    def remote_java_mapping(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_JAVA_MAPPING, pid))

    def remote_embedded(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_EMBEDDED_PDF, pid))

    def remote_filled(self, uid, sid, pid) -> str:
        return self._sc.mapper_path(uid, sid, pid, _f(_FILLED_PDF, pid))

    # ── Remote RAG input paths (written by mapper, read by RAG API 1) ─────────

    def remote_header_file(self, uid, sid, pid) -> str:
        return self._sc.rag_input_path(uid, sid, pid, _HEADER_FILE)

    def remote_section_file(self, uid, sid, pid) -> str:
        return self._sc.rag_input_path(uid, sid, pid, _SECTION_FILE)

    # ── Remote RAG prediction paths ───────────────────────────────────────────

    def remote_rag_predictions(self, uid, sid, pid) -> str:
        return self._sc.rag_predictions_path(uid, sid, pid, _RAG_PRED)

    def remote_llm_predictions(self, uid, sid, pid) -> str:
        return self._sc.rag_predictions_path(uid, sid, pid, _LLM_PRED)

    def remote_final_predictions(self, uid, sid, pid) -> str:
        return self._sc.rag_predictions_path(uid, sid, pid, _FINAL_PRED)

    # ── Shared / global paths ─────────────────────────────────────────────────

    def remote_cache_registry(self) -> str:
        """Global hash registry — shared/pdf-cache/pdf-registry/hash_registry.json"""
        return self._sc.cache_path(_CACHE_REGISTRY)

    def local_cache_registry_path(self) -> str:
        """Always-local path for reading/writing the hash registry."""
        return self._sc.local_cache_path(_CACHE_REGISTRY)

    def remote_filled_pdf_store(self, uid, sid, pid) -> str:
        """Permanent copy of filled PDF — shared/filled_pdf_store/{env}/{uid}/{sid}/{pid}/filled.pdf"""
        return self._sc.filled_pdf_store_path(uid, sid, pid)

    def remote_unpredicted_fields(self, uid, sid, pid) -> str:
        """Fields neither RAG nor LLM could predict — shared/unpredicted_fields/…"""
        return self._sc.unpredicted_fields_path(uid, sid, pid, _UNPREDICTED_FIELDS)

    # ── Local processing paths (all under processing_dir) ────────────────────

    def local_paths(self, uid, sid, pid, processing_dir: str) -> dict:
        """Return all local /tmp processing paths for a job."""

        def p(f):
            return os.path.join(processing_dir, f)

        return {
            # inputs
            "processing_input_pdf": p(_f(_INPUT_PDF, pid)),
            "processing_global_json": p(_GLOBAL_JSON),
            "processing_input_json": p(_INPUT_JSON),
            # mapper outputs
            "extracted_json": p(_f(_EXTRACTED_JSON, pid)),
            "mapped_json": p(_f(_MAPPED_JSON, pid)),
            "radio_groups_json": p(_f(_RADIO_JSON, pid)),
            "headers_with_fields": p(_f(_HEADERS_FIELDS, pid)),
            "final_form_fields": p(_f(_FINAL_FIELDS, pid)),
            "java_mapping": p(_f(_JAVA_MAPPING, pid)),
            "embedded_pdf": p(_f(_EMBEDDED_PDF, pid)),
            "filled_pdf": p(_f(_FILLED_PDF, pid)),
            # RAG inputs
            "header_file": p(_HEADER_FILE),
            "section_file": p(_SECTION_FILE),
            # RAG predictions
            "rag_predictions": p(_RAG_PRED),
            "llm_predictions": p(_LLM_PRED),
            "final_predictions": p(_FINAL_PRED),
        }
