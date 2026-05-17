"""
MapperConfig
============
Single configuration object for the mapper pipeline.

Three ways to build::

    # From a configs/ directory (recommended with chatbot)
    cfg = MapperConfig.from_directory("./configs")

    # From environment variables (Lambda / Docker)
    cfg = MapperConfig.from_env()

    # Directly (testing / programmatic)
    cfg = MapperConfig(llm_model="gpt-4o", confidence_threshold=0.8)
"""
from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MapperConfig:
    # LLM
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout: int = 120
    llm_max_retries: int = 3
    llm_max_threads: int = 10

    # Mapping
    confidence_threshold: float = 0.7
    chunking_strategy: str = "page"
    chunking_chunk_size: int = 9
    chunking_overlap: int = 1
    include_description: int = 1

    # Storage
    source_type: str = "local"
    output_base_path: str = "./data/mapper/output"
    temp_local_dir: str = "/tmp"
    cache_registry_path: str = ""
    pdf_cache_enabled: bool = True

    # Cloud
    s3_bucket: str = ""
    global_input_json_s3_uri: str = ""

    # ── RAG integration ───────────────────────────────────────────────────────
    # use_second_mapper kept for backward compatibility — sets rag_enabled = True
    use_second_mapper: bool = False

    # rag_enabled: master switch for the RAG pipeline
    #   false (default) -> LLM mapping only, RAG block is never entered
    #   true            -> RAG runs as second predictor after LLM
    rag_enabled: bool = False

    # rag_mode: how the RAG pipeline is invoked
    #   "inprocess" -> call installed ragpdf SDK directly (no HTTP, same process)
    #   "http"      -> call remote RAG API (Lambda/FastAPI), set rag_api_url + rag_api_key
    rag_mode: str = "inprocess"

    # Remote API credentials (only used when rag_mode = "http")
    rag_api_url: str = ""
    rag_api_key: str = ""
    # ─────────────────────────────────────────────────────────────────────────

    # Notifications
    notifications_enabled: bool = False
    notifications_backend_url: str = ""
    teams_webhook_url: str = ""

    # Headers LLM
    headers_llm_model: str = "gpt-4o"
    headers_temperature: float = 0.0
    headers_max_tokens: int = 8192
    headers_chunk_size: int = 5
    headers_max_workers: int = 3

    # JAR override (None = use bundled JARs)
    java_jar_dir: Optional[str] = None

    def __post_init__(self):
        # Backward compat: if caller passed use_second_mapper=True but left
        # rag_enabled at default False, honour use_second_mapper.
        if self.use_second_mapper and not self.rag_enabled:
            self.rag_enabled = True

    @classmethod
    def from_directory(cls, config_dir: str) -> "MapperConfig":
        """
        Load from a config directory containing mapper_config.ini.

        This is the primary factory when using chatbot + mapper together.
        The chatbot passes its own configs/ folder here so both SDKs
        read from the same directory.

        If mapper_config.ini is missing, returns defaults (no crash).
        """
        ini = configparser.ConfigParser()
        config_path = Path(config_dir) / "mapper_config.ini"
        if config_path.exists():
            ini.read(config_path)

        def _s(sec, key, fb=""):
            try:
                return ini.get(sec, key)
            except Exception:
                return fb

        def _f(sec, key, fb):
            try:
                return ini.getfloat(sec, key)
            except Exception:
                return fb

        def _i(sec, key, fb):
            try:
                return ini.getint(sec, key)
            except Exception:
                return fb

        def _b(sec, key, fb):
            try:
                return ini.getboolean(sec, key)
            except Exception:
                return fb

        source_type = _s("general", "source_type", "local")

        # rag_enabled: check new [rag] section first, then legacy use_second_mapper
        rag_enabled_new    = _b("rag", "enabled", False)
        use_second_mapper  = _b("mapping", "use_second_mapper", False)
        rag_enabled        = rag_enabled_new or use_second_mapper

        rag_mode    = _s("rag", "mode",    "inprocess")
        rag_api_url = _s("rag", "api_url", "") or _s("general", "rag_api_url", "")
        rag_api_key = _s("rag", "api_key", "")

        return cls(
            llm_model=_s("mapping", "llm_model", "gpt-4o"),
            llm_temperature=_f("mapping", "llm_temperature", 0.0),
            llm_max_tokens=_i("mapping", "llm_max_tokens", 4096),
            llm_timeout=_i("mapping", "llm_timeout", 120),
            llm_max_retries=_i("mapping", "llm_max_retries", 3),
            confidence_threshold=_f("mapping", "confidence_threshold", 0.7),
            chunking_strategy=_s("mapping", "chunking_strategy", "page"),
            chunking_chunk_size=_i("mapping", "chunking_chunk_size", 9),
            chunking_overlap=_i("mapping", "chunking_overlap", 1),
            include_description=_i("mapping", "include_description", 1),
            use_second_mapper=use_second_mapper,
            rag_enabled=rag_enabled,
            rag_mode=rag_mode,
            rag_api_url=rag_api_url,
            rag_api_key=rag_api_key,
            source_type=source_type,
            output_base_path=_s(source_type, "output_base_path", "./data/mapper/output"),
            temp_local_dir=_s(source_type, "temp_local_dir", "/tmp"),
            cache_registry_path=_s(source_type, "cache_registry_path", ""),
            pdf_cache_enabled=_b("general", "pdf_cache_enabled", True),
            notifications_enabled=_b("notifications", "teams_notifications_enabled", False),
            teams_webhook_url=_s("notifications", "teams_webhook_url", ""),
            headers_llm_model=_s("headers", "headers_llm_model", "gpt-4o"),
            headers_temperature=_f("headers", "headers_temperature", 0.0),
            headers_max_tokens=_i("headers", "headers_max_tokens", 8192),
            headers_chunk_size=_i("headers", "headers_chunk_size", 5),
            headers_max_workers=_i("headers", "headers_max_workers", 3),
        )

    @classmethod
    def from_env(cls) -> "MapperConfig":
        """Load entirely from environment variables — no config file needed."""
        source_type = os.getenv("MAPPER_SOURCE_TYPE", "local")

        # RAG: check new vars first, fall back to legacy MAPPER_USE_SECOND_MAPPER
        rag_enabled_env   = os.getenv("RAG_ENABLED", "").lower()
        use_second_mapper = os.getenv("MAPPER_USE_SECOND_MAPPER", "false").lower() == "true"
        rag_enabled       = (rag_enabled_env == "true") or use_second_mapper

        return cls(
            llm_model=os.getenv("MAPPER_LLM_MODEL", "gpt-4o"),
            llm_temperature=float(os.getenv("MAPPER_LLM_TEMPERATURE", "0.0")),
            llm_max_tokens=int(os.getenv("MAPPER_LLM_MAX_TOKENS", "4096")),
            llm_timeout=int(os.getenv("MAPPER_LLM_TIMEOUT", "120")),
            llm_max_retries=int(os.getenv("MAPPER_LLM_MAX_RETRIES", "3")),
            confidence_threshold=float(os.getenv("MAPPER_CONFIDENCE_THRESHOLD", "0.7")),
            chunking_strategy=os.getenv("MAPPER_CHUNKING_STRATEGY", "page"),
            source_type=source_type,
            output_base_path=os.getenv("MAPPER_OUTPUT_PATH", "./data/mapper/output"),
            temp_local_dir=os.getenv("MAPPER_TEMP_DIR", "/tmp"),
            pdf_cache_enabled=os.getenv("MAPPER_CACHE_ENABLED", "true").lower() == "true",
            use_second_mapper=use_second_mapper,
            rag_enabled=rag_enabled,
            rag_mode=os.getenv("RAG_MODE", "inprocess"),
            rag_api_url=os.getenv("RAG_API_URL", ""),
            rag_api_key=os.getenv("RAG_API_KEY", ""),
        )
