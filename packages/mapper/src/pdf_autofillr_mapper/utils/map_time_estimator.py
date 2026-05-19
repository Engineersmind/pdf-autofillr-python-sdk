import math
import os
from typing import Any, Dict

from pdf_autofillr_mapper.core.config import get_chunking_config, settings

DEFAULT_CLAUDE_STAGE_SECONDS = 44.0
DEFAULT_OPENAI_STAGE_SECONDS = 33.0
OVERHEAD_MULTIPLIER = 1.3


def _load_json(path: str) -> Dict[str, Any]:
    """Load JSON from local disk or S3."""
    if not path:
        raise ValueError("JSON path is required")

    if path.startswith("s3://"):
        # Lazy import - only load S3Client when actually needed for S3 paths
        from pdf_autofillr_mapper.clients.s3_client import S3Client
        client = S3Client()
        return client.load_json_from_s3(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"JSON path not found: {path}")

    with open(path, "r", encoding="utf-8") as handler:
        import json

        return json.load(handler)


def _resolve_chunk_size(mapping_config: Dict[str, Any]) -> int:
    chunking_config = get_chunking_config()
    strategy = mapping_config.get("chunking_strategy") or chunking_config.get("current_strategy", "page")

    strategies = chunking_config.get("strategies", [])
    for cfg in strategies:
        if cfg.get("name") == strategy:
            chunk_size = cfg.get("chunk_size") or cfg.get("lines_limit")
            if chunk_size:
                return max(1, int(chunk_size))

    # Fallback to current page chunk size
    return max(1, settings.mapper_chunking_page_chunk_size)


def _resolve_threads(mapping_config: Dict[str, Any]) -> int:
    threads = mapping_config.get("max_threads") or mapping_config.get("llm_max_threads")
    if threads:
        return max(1, int(threads))
    return max(1, settings.llm_max_threads)


def _provider_stage_seconds(mapping_config: Dict[str, Any]) -> float:
    provider = (mapping_config.get("llm_provider") or settings.llm_current_provider or "claude").lower()
    if provider.startswith("openai") or provider.startswith("gpt"):
        return DEFAULT_OPENAI_STAGE_SECONDS
    return DEFAULT_CLAUDE_STAGE_SECONDS


def estimate_map_stage_time(
    extracted_json_path: str,
    input_json_path: str,
    mapping_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Estimate mapping duration using a simple page-count heuristic."""
    mapping_config = mapping_config or {}

    try:
        extracted_data = _load_json(extracted_json_path)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to load extracted JSON: {exc}"}

    # Validate input mapping JSON exists even if unused for timing.
    try:
        _load_json(input_json_path)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to load input JSON: {exc}"}

    pages = extracted_data.get("pages")
    if isinstance(pages, list):
        total_pages = len(pages)
    else:
        total_pages = extracted_data.get("total_pages") or extracted_data.get("page_count") or 0

    chunk_size = _resolve_chunk_size(mapping_config)
    max_threads = _resolve_threads(mapping_config)
    base_stage_seconds = _provider_stage_seconds(mapping_config)

    num_chunks = max(1, math.ceil(total_pages / chunk_size)) if chunk_size else 1
    thread_cycles = max(1, math.ceil(num_chunks / max_threads))
    estimated_seconds = OVERHEAD_MULTIPLIER * thread_cycles * base_stage_seconds

    return {
        "status": "ok",
        "details": {
            "total_pages": total_pages,
            "chunk_size": chunk_size,
            "num_chunks": num_chunks,
            "llm_threads": max_threads,
            "thread_cycles": thread_cycles,
            "provider_stage_seconds": base_stage_seconds,
            "overhead_multiplier": OVERHEAD_MULTIPLIER,
        },
        "totals": {
            "estimated_seconds": round(estimated_seconds, 2)
        }
    }


__all__ = ["estimate_map_stage_time"]
