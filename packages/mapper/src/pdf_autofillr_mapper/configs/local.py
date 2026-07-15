"""
Local filesystem storage configuration.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from .base import BaseStorageConfig

logger = logging.getLogger(__name__)


class LocalStorageConfig(BaseStorageConfig):
    """Local filesystem storage implementation."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize local storage config.

        Args:
            base_dir: Optional base directory for output files (default: /tmp/pdf_processing)
        """
        super().__init__(source_type="local")
        import tempfile as _tempfile

        self.base_dir = base_dir or os.path.join(
            _tempfile.gettempdir(), "pdf_processing"
        )

        # RAG integration flags (read from env — same source as MapperConfig.from_env)
        self.rag_enabled = os.getenv("RAG_ENABLED", "false").lower() == "true"
        self.rag_mode = os.getenv("RAG_MODE", "inprocess")
        self.rag_api_url = os.getenv("RAG_API_URL", "")
        self.rag_api_key = os.getenv("RAG_API_KEY", "")

        # RAG local file paths (set by operations after calling create_rag_api_files)
        self.local_header_file: Optional[str] = None
        self.local_section_file: Optional[str] = None
        self.local_rag_predictions: Optional[str] = None
        self.local_llm_predictions = None
        self.local_final_predictions = None

        # Create base directory if it doesn't exist
        Path(self.base_dir).mkdir(parents=True, exist_ok=True)

    def parse_path(self, file_path: str) -> dict[str, str]:
        """
        Parse local file path.

        Returns:
            {
                "type": "local",
                "path": "/full/path/to/file.ext",
                "directory": "/full/path/to",
                "filename": "file.ext"
            }
        """
        abs_path = os.path.abspath(file_path)
        directory = os.path.dirname(abs_path)
        filename = os.path.basename(abs_path)

        return {
            "type": "local",
            "path": abs_path,
            "directory": directory,
            "filename": filename,
        }

    def download_file(self, source_path: str, local_path: str) -> str:
        """
        'Download' file (copy from source to destination for local).

        For local files, this is essentially a copy operation.
        """
        source_abs = os.path.abspath(source_path)
        dest_abs = os.path.abspath(local_path)

        # Create destination directory if needed
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)

        # Copy file
        shutil.copy2(source_abs, dest_abs)
        logger.info(f"Copied {source_abs} to {dest_abs}")
        return dest_abs

    def upload_file(self, local_path: str, destination_path: str) -> str:
        """
        'Upload' file (copy from source to destination for local).
        """
        source_abs = os.path.abspath(local_path)
        dest_abs = os.path.abspath(destination_path)

        # Create destination directory if needed
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)

        # Copy file
        shutil.copy2(source_abs, dest_abs)
        logger.info(f"Copied {source_abs} to {dest_abs}")
        return dest_abs

    def file_exists(self, file_path: str) -> bool:
        """Check if local file exists."""
        return os.path.exists(file_path)

    def generate_output_path(
        self, input_path: str, suffix: str, extension: Optional[str] = None
    ) -> str:
        """
        Generate local output path.

        Example:
            input: /path/to/file.pdf
            suffix: _extracted
            extension: .json
            output: /path/to/file_extracted.json
        """
        parsed = self.parse_path(input_path)

        path = parsed["path"]
        if "." in path:
            base_path = path.rsplit(".", 1)[0]
            original_ext = "." + path.rsplit(".", 1)[1]
        else:
            base_path = path
            original_ext = ""

        new_ext = extension if extension else original_ext
        return f"{base_path}{suffix}{new_ext}"

    def get_storage_config(self, file_path: str) -> dict[str, Any]:
        """
        Get storage config for processing modules.

        Returns:
            {
                "type": "local",
                "path": "/full/path/to/file",
                "directory": "/full/path/to",
                "filename": "file.ext"
            }
        """
        return self.parse_path(file_path)

    def get_complete_file_config(
        self,
        input_path: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Generate complete file configuration for local processing.

        Returns config with all pipeline paths in the same directory as input,
        or in output_base_path if set with proper user/pdf directory structure.
        """
        parsed = self.parse_path(input_path)

        # Generate session suffix if applicable
        session_suffix = ""
        if user_id is not None and session_id is not None:
            session_suffix = f"_user{user_id}_session{session_id}"

        # Base paths
        filename = parsed["filename"]
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # Check if output_base_path is set (for tests or custom directory structure)
        if (
            hasattr(self, "output_base_path")
            and self.output_base_path
            and user_id is not None
        ):
            # Create structured output: output_base_path/users/{user_id}/pdfs/{pdf_doc_id}/
            pdf_doc_id = getattr(self, "pdf_doc_id", session_id or 1)
            user_dir = os.path.join(self.output_base_path, "users", str(user_id))
            pdf_dir = os.path.join(user_dir, "pdfs", str(pdf_doc_id))

            # Create subdirectories for each stage
            extraction_dir = os.path.join(pdf_dir, "extraction")
            mapping_dir = os.path.join(pdf_dir, "mapping")
            embedding_dir = os.path.join(pdf_dir, "embedding")
            filling_dir = os.path.join(pdf_dir, "filling")
            headers_dir = os.path.join(pdf_dir, "headers")  # For dual mapper / RAG

            for d in [
                extraction_dir,
                mapping_dir,
                embedding_dir,
                filling_dir,
                headers_dir,
            ]:
                os.makedirs(d, exist_ok=True)

            extraction_output_dir = extraction_dir
            mapping_output_dir = mapping_dir
            embedding_output_dir = embedding_dir
            filling_output_dir = filling_dir
            headers_output_dir = headers_dir
        else:
            # Default: all in same directory as input
            directory = parsed["directory"]
            extraction_output_dir = directory
            mapping_output_dir = directory
            embedding_output_dir = directory
            filling_output_dir = directory
            headers_output_dir = directory

        # Generate all pipeline paths
        config = {
            "source_type": "local",
            "input_path": parsed["path"],
            "input_filename": filename,
            "session_suffix": session_suffix,
            # Extraction stage outputs
            "extraction": {
                "extracted_path": os.path.join(
                    extraction_output_dir, f"{base_name}{session_suffix}_extracted.json"
                ),
                "radio_groups_path": os.path.join(
                    extraction_output_dir,
                    f"{base_name}{session_suffix}_radio_groups.json",
                ),
            },
            # Mapping stage outputs
            "mapping": {
                "mapping_path": os.path.join(
                    mapping_output_dir,
                    f"{base_name}{session_suffix}_mapped_fields.json",
                ),
                "radio_groups_path": os.path.join(
                    mapping_output_dir, f"{base_name}{session_suffix}_radio_groups.json"
                ),
            },
            # Embedding stage output
            "embedding": {
                "embedded_pdf_path": os.path.join(
                    embedding_output_dir, f"{base_name}{session_suffix}_embedded.pdf"
                )
            },
            # Filling stage output
            "filling": {
                "filled_pdf_path": os.path.join(
                    filling_output_dir, f"{base_name}{session_suffix}_filled.pdf"
                )
            },
            # Headers stage (for dual mapper / RAG)
            "headers": {
                "headers_with_fields_path": os.path.join(
                    headers_output_dir,
                    f"{base_name}{session_suffix}_headers_with_fields.json",
                ),
                "final_form_fields_path": os.path.join(
                    headers_output_dir,
                    f"{base_name}{session_suffix}_final_form_fields.json",
                ),
            },
        }

        return config


def build_operation_config(
    pdf_path: str,
    input_json_path: Optional[str] = None,
    base_dir: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    pdf_doc_id: Optional[int] = None,
) -> "LocalStorageConfig":
    """
    Build a fully-populated LocalStorageConfig ready to pass straight into
    handle_extract_operation/handle_map_operation/handle_embed_operation/
    handle_fill_operation (via create_file_handlers()).

    This exists because those handlers expect a config object with specific
    `local_*` attributes already set (config.local_input_pdf,
    config.local_extracted_json, etc. — see InputFileHandler/OutputFileHandler)
    rather than a bare file path or a plain dict. Call sites that used to pass
    a raw dict or omit config entirely (see CHANGELOG) were relying on a
    calling convention this module never actually implemented; this is the
    single place that builds a config those handlers can use correctly.

    Output files are named after the input PDF's stem, but always written
    under `base_dir` (default: LocalStorageConfig's own default,
    <tempdir>/pdf_processing) rather than next to the input file — so
    generated output never lands in whatever arbitrary directory a caller's
    pdf_path happens to point at.

    Args:
        pdf_path: Path to the input PDF (local path).
        input_json_path: Optional path to input JSON data for mapping.
        base_dir: Directory to write generated output files into.
        user_id, session_id, pdf_doc_id: Optional identifiers, stored on the
            config for logging/tracking; not required by the handlers.

    Returns:
        A LocalStorageConfig with every local_* attribute the extract/map/
        embed/fill handlers read already set.
    """
    config = LocalStorageConfig(base_dir=base_dir)

    abs_pdf = os.path.abspath(pdf_path)
    stem = Path(abs_pdf).stem

    def out(suffix: str, ext: str) -> str:
        return os.path.join(config.base_dir, f"{stem}{suffix}{ext}")

    config.local_input_pdf = abs_pdf
    config.local_input_json = os.path.abspath(input_json_path) if input_json_path else None

    config.local_extracted_json = out("_extracted", ".json")
    config.local_mapped_json = out("_mapped_fields", ".json")
    config.local_radio_json = out("_radio_groups", ".json")
    config.local_embedded_pdf = out("_embedded", ".pdf")
    config.local_filled_pdf = out("_filled", ".pdf")

    # Dual-mapper / RAG-adjacent outputs — populated on demand by the
    # handlers that use them; harmless to pre-declare the paths.
    config.local_headers_with_fields = out("_headers_with_fields", ".json")
    config.local_final_form_fields = out("_final_form_fields", ".json")
    config.local_java_mapping = out("_java_mapping", ".json")

    config.user_id = user_id
    config.session_id = session_id
    config.pdf_doc_id = pdf_doc_id

    return config


# Directories user-supplied path fields (pdf_path, extracted_json_path, etc.)
# are allowed to point into on HTTP entrypoints. Defaults to the same
# base_dir LocalStorageConfig writes output to; extend with
# MAPPER_ALLOWED_INPUT_ROOTS (comma-separated) if your PDFs/JSON live
# elsewhere (e.g. an uploads directory).
def _allowed_input_roots() -> list[Path]:
    roots = [Path(LocalStorageConfig().base_dir).resolve()]
    extra = os.getenv("MAPPER_ALLOWED_INPUT_ROOTS", "")
    roots += [Path(r).resolve() for r in extra.split(",") if r.strip()]
    return roots


def validate_request_path(raw_path: str, *, label: str) -> str:
    """
    Normalize `raw_path` and verify it lives inside one of the allowed input
    roots (see _allowed_input_roots). Every HTTP-request field that ends up
    being read from or written to disk (pdf_path, extracted_json_path,
    input_json_path, embedded_pdf_path, mapping_json_path,
    radio_groups_path, original_pdf_path) must go through this before being
    used — otherwise an authenticated-but-malicious caller can read/write
    arbitrary files on the server (CWE-22 / CodeQL py/path-injection).

    Uses os.path.abspath + normpath (pure string manipulation) rather than
    Path.resolve() (which also follows symlinks via filesystem I/O) — the
    confinement check below is exactly as strict either way.

    Raises ValueError (callers should turn this into HTTP 400) if the path
    escapes the allowed roots.
    """
    normalized = os.path.normpath(os.path.abspath(raw_path))
    for root in _allowed_input_roots():
        root_str = str(root)
        if normalized == root_str or normalized.startswith(root_str + os.sep):
            return normalized
    raise ValueError(
        f"Invalid {label}: '{raw_path}' resolves to '{normalized}', which is "
        f"outside the allowed directories "
        f"{[str(r) for r in _allowed_input_roots()]}. Set "
        f"MAPPER_ALLOWED_INPUT_ROOTS if your files live elsewhere."
    )
