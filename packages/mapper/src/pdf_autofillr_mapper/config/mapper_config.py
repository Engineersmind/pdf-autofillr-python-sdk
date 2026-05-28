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
    cfg = MapperConfig(
        llm_model="anthropic/claude-3-5-sonnet-20241022",
        llm_api_key="sk-ant-...",
        headers_llm_model="openai/gpt-4o",
        headers_llm_api_key="sk-...",
    )

LLM credentials
---------------
Two LLM phases are used internally, each can point to a different model/provider:

  Phase 1 — Mapping:  llm_model        (default: gpt-4o)
  Phase 2 — Headers:  headers_llm_model (default: gpt-4o)

Keys are resolved in this order for each phase:
  1. ``llm_api_key`` / ``headers_llm_api_key`` fields (programmatic override)
  2. ``MAPPER_LLM_API_KEY`` / ``MAPPER_HEADERS_LLM_API_KEY`` env vars
  3. Provider-specific env vars read automatically by litellm:
       OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY,
       GEMINI_API_KEY, AZURE_API_KEY, AWS_ACCESS_KEY_ID, etc.

Both phases can use the same model or completely different providers.
"""

from __future__ import annotations

import configparser
import os
import warnings
from dataclasses import dataclass
from pathlib import Path


def _has_key_for_model(model: str, api_key: str) -> bool:
    """Return True if a usable credential exists for the given litellm model name."""
    if api_key:
        return True
    m = model.lower()
    return any(
        [
            os.getenv("OPENAI_API_KEY")
            and any(t in m for t in ("openai/", "gpt-", "o1", "o3")),
            os.getenv("ANTHROPIC_API_KEY")
            and any(t in m for t in ("anthropic/", "claude-")),
            os.getenv("GROQ_API_KEY") and "groq/" in m,
            os.getenv("GEMINI_API_KEY") and "gemini/" in m,
            os.getenv("AZURE_API_KEY") and "azure/" in m,
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and "vertex_ai/" in m,
            os.getenv("AWS_ACCESS_KEY_ID") and "bedrock/" in m,
            "ollama/" in m,
        ]
    )


@dataclass
class MapperConfig:
    # ── Mapping LLM (Phase 1) ────────────────────────────────────────────────
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""  # set MAPPER_LLM_API_KEY or a provider-specific key
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

    # ── Headers LLM (Phase 2) ────────────────────────────────────────────────
    headers_llm_model: str = "gpt-4o"
    headers_llm_api_key: str = ""  # set MAPPER_HEADERS_LLM_API_KEY or provider key
    headers_temperature: float = 0.0
    headers_max_tokens: int = 8192
    headers_chunk_size: int = 5
    headers_max_workers: int = 3

    # JAR override (None = use bundled JARs)
    java_jar_dir: str | None = None

    def __post_init__(self):
        if self.use_second_mapper and not self.rag_enabled:
            self.rag_enabled = True
        # Resolve api keys from env vars if not set programmatically
        if not self.llm_api_key:
            self.llm_api_key = os.getenv("MAPPER_LLM_API_KEY", "")
        if not self.headers_llm_api_key:
            self.headers_llm_api_key = os.getenv("MAPPER_HEADERS_LLM_API_KEY", "")

    def validate(self) -> None:
        """Warn at startup if no credential is found for either LLM phase."""

        def _warn(phase: str, model: str, key: str, env_var: str) -> None:
            if not _has_key_for_model(model, key):
                warnings.warn(
                    f"[pdf-autofillr-mapper] No API key found for {phase} model {model!r}.\n"
                    f"  Set {env_var} as a universal override, or the provider-specific key:\n"
                    f"  OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY,\n"
                    f"  AZURE_API_KEY, GEMINI_API_KEY, AWS_ACCESS_KEY_ID.\n"
                    f"  For Ollama: no key needed.",
                    stacklevel=3,
                )

        _warn("mapping", self.llm_model, self.llm_api_key, "MAPPER_LLM_API_KEY")
        _warn(
            "headers",
            self.headers_llm_model,
            self.headers_llm_api_key,
            "MAPPER_HEADERS_LLM_API_KEY",
        )

    @classmethod
    def from_directory(cls, config_dir: str) -> MapperConfig:
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
        rag_enabled_new = _b("rag", "enabled", False)
        use_second_mapper = _b("mapping", "use_second_mapper", False)
        rag_enabled = rag_enabled_new or use_second_mapper

        rag_mode = _s("rag", "mode", "inprocess")
        rag_api_url = _s("rag", "api_url", "") or _s("general", "rag_api_url", "")
        rag_api_key = _s("rag", "api_key", "")

        return cls(
            llm_model=_s("mapping", "llm_model", "gpt-4o"),
            # API keys always come from env, never from .ini files
            llm_api_key=os.getenv("MAPPER_LLM_API_KEY", ""),
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
            output_base_path=_s(
                source_type, "output_base_path", "./data/mapper/output"
            ),
            temp_local_dir=_s(source_type, "temp_local_dir", "/tmp"),
            cache_registry_path=_s(source_type, "cache_registry_path", ""),
            pdf_cache_enabled=_b("general", "pdf_cache_enabled", True),
            notifications_enabled=_b(
                "notifications", "teams_notifications_enabled", False
            ),
            teams_webhook_url=_s("notifications", "teams_webhook_url", ""),
            headers_llm_model=_s("headers", "headers_llm_model", "gpt-4o"),
            headers_llm_api_key=os.getenv("MAPPER_HEADERS_LLM_API_KEY", ""),
            headers_temperature=_f("headers", "headers_temperature", 0.0),
            headers_max_tokens=_i("headers", "headers_max_tokens", 8192),
            headers_chunk_size=_i("headers", "headers_chunk_size", 5),
            headers_max_workers=_i("headers", "headers_max_workers", 3),
        )

    @classmethod
    def from_env(cls) -> MapperConfig:
        """Load entirely from environment variables — no config file needed."""
        source_type = os.getenv("MAPPER_SOURCE_TYPE", "local")

        # RAG: check new vars first, fall back to legacy MAPPER_USE_SECOND_MAPPER
        rag_enabled_env = os.getenv("RAG_ENABLED", "").lower()
        use_second_mapper = (
            os.getenv("MAPPER_USE_SECOND_MAPPER", "false").lower() == "true"
        )
        rag_enabled = (rag_enabled_env == "true") or use_second_mapper

        return cls(
            llm_model=os.getenv("MAPPER_LLM_MODEL", "gpt-4o"),
            llm_api_key=os.getenv("MAPPER_LLM_API_KEY", ""),
            llm_temperature=float(os.getenv("MAPPER_LLM_TEMPERATURE", "0.0")),
            llm_max_tokens=int(os.getenv("MAPPER_LLM_MAX_TOKENS", "4096")),
            llm_timeout=int(os.getenv("MAPPER_LLM_TIMEOUT", "120")),
            llm_max_retries=int(os.getenv("MAPPER_LLM_MAX_RETRIES", "3")),
            confidence_threshold=float(os.getenv("MAPPER_CONFIDENCE_THRESHOLD", "0.7")),
            chunking_strategy=os.getenv("MAPPER_CHUNKING_STRATEGY", "page"),
            source_type=source_type,
            output_base_path=os.getenv("MAPPER_OUTPUT_PATH", "./data/mapper/output"),
            temp_local_dir=os.getenv("MAPPER_TEMP_DIR", "/tmp"),
            pdf_cache_enabled=os.getenv("MAPPER_CACHE_ENABLED", "true").lower()
            == "true",
            use_second_mapper=use_second_mapper,
            rag_enabled=rag_enabled,
            rag_mode=os.getenv("RAG_MODE", "inprocess"),
            rag_api_url=os.getenv("RAG_API_URL", ""),
            rag_api_key=os.getenv("RAG_API_KEY", ""),
            headers_llm_model=os.getenv("MAPPER_HEADERS_LLM_MODEL", "gpt-4o"),
            headers_llm_api_key=os.getenv("MAPPER_HEADERS_LLM_API_KEY", ""),
        )
