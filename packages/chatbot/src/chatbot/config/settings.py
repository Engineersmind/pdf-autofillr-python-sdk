# chatbot/src/chatbot/config/settings.py
"""SDK runtime settings — reads from environment variables or .env file."""

from __future__ import annotations

import os
import warnings


class Settings:
    """SDK runtime settings. All values readable from environment variables."""

    def __init__(self, validate: bool = True):
        self.llm_model: str = os.getenv("CHATBOT_LLM_MODEL", "openai/gpt-4o-mini")
        self.llm_api_key: str = os.getenv("CHATBOT_LLM_API_KEY", "")
        self.storage_type: str = os.getenv("chatbot_STORAGE", "local").lower()
        self.data_path: str = os.getenv("chatbot_DATA_PATH", "./data/chatbot")
        self.config_path: str = os.getenv("chatbot_CONFIG_PATH", "./configs")
        self.bot_name: str = os.getenv("chatbot_BOT_NAME", "Bot")
        self.greeting: str = os.getenv(
            "chatbot_GREETING",
            "Hi! I am here to help you fill out your investment documents.",
        )
        self.pdf_filler_mode: str = os.getenv("chatbot_PDF_FILLER", "none").lower()
        self.pdf_path: str = os.getenv("chatbot_PDF_PATH", "")
        self.pdf_poll_interval: int = int(os.getenv("chatbot_PDF_POLL_INTERVAL", "10"))
        self.pdf_poll_timeout: int = int(os.getenv("chatbot_PDF_POLL_TIMEOUT", "150"))
        self.pdf_max_retries: int = int(os.getenv("chatbot_PDF_MAX_RETRIES", "3"))
        self.mapper_api_url: str = os.getenv("MAPPER_API_URL", "")
        self.mapper_api_key: str = os.getenv("MAPPER_API_KEY", "")
        self.mapper_config_dir: str = os.getenv("chatbot_CONFIG_PATH", "./configs")
        self.telemetry_enabled: bool = (
            os.getenv("chatbot_TELEMETRY", "false").lower() == "true"
        )
        self.telemetry_endpoint: str = os.getenv("chatbot_TELEMETRY_ENDPOINT", "")
        self.debug_logging: bool = (
            os.getenv("chatbot_DEBUG_LOGGING", "true").lower() == "true"
        )
        self.log_level: str = os.getenv("chatbot_LOG_LEVEL", "INFO")

        if validate:
            self._validate()

    def _validate(self) -> None:
        errors = []
        warns = []

        model = self.llm_model.lower()
        if not self.llm_api_key:
            has_key = any(
                [
                    os.getenv("OPENAI_API_KEY")
                    and ("openai/" in model or model.startswith("gpt-")),
                    os.getenv("ANTHROPIC_API_KEY")
                    and ("anthropic/" in model or model.startswith("claude-")),
                    os.getenv("GROQ_API_KEY") and "groq/" in model,
                    os.getenv("GEMINI_API_KEY") and "gemini/" in model,
                    os.getenv("AZURE_API_KEY") and "azure/" in model,
                    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                    and "vertex_ai/" in model,
                    os.getenv("AWS_ACCESS_KEY_ID") and "bedrock/" in model,
                    "ollama/" in model,
                ]
            )
            if not has_key:
                warns.append(
                    f"No API key found for model {self.llm_model!r}.\n"
                    "  Set CHATBOT_LLM_API_KEY as a universal override, or the\n"
                    "  provider-specific key: OPENAI_API_KEY, ANTHROPIC_API_KEY,\n"
                    "  GROQ_API_KEY, AZURE_API_KEY, GEMINI_API_KEY.\n"
                    "  For Bedrock: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY.\n"
                    "  For Vertex AI: GOOGLE_APPLICATION_CREDENTIALS.\n"
                    "  For Ollama: no key needed."
                )

        if self.storage_type == "s3":
            missing = []
            if not os.getenv("AWS_OUTPUT_BUCKET"):
                missing.append("AWS_OUTPUT_BUCKET")
            if not os.getenv("AWS_CONFIG_BUCKET"):
                missing.append("AWS_CONFIG_BUCKET")
            has_creds = any(
                os.getenv(k)
                for k in [
                    "AWS_ACCESS_KEY_ID",
                    "AWS_PROFILE",
                    "AWS_ROLE_ARN",
                    "AWS_EXECUTION_ENV",
                    "AWS_LAMBDA_FUNCTION_NAME",
                ]
            )
            if not has_creds:
                missing.append("AWS credentials")
            if missing:
                errors.append(
                    "chatbot_STORAGE=s3 but missing:\n"
                    + "\n".join(f"  - {v}" for v in missing)
                )

        elif self.storage_type == "gcp":
            missing = []
            if not os.getenv("GCP_OUTPUT_BUCKET"):
                missing.append("GCP_OUTPUT_BUCKET")
            if not os.getenv("GCP_CONFIG_BUCKET"):
                missing.append("GCP_CONFIG_BUCKET")
            if not (
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                or os.getenv("GOOGLE_CLOUD_PROJECT")
            ):
                missing.append("GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_CLOUD_PROJECT")
            if missing:
                errors.append(
                    "chatbot_STORAGE=gcp but missing:\n"
                    + "\n".join(f"  - {v}" for v in missing)
                )

        elif self.storage_type == "azure":
            missing = []
            if not os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
                missing.append("AZURE_STORAGE_CONNECTION_STRING")
            if not os.getenv("AZURE_OUTPUT_CONTAINER"):
                missing.append("AZURE_OUTPUT_CONTAINER")
            if not os.getenv("AZURE_CONFIG_CONTAINER"):
                missing.append("AZURE_CONFIG_CONTAINER")
            if missing:
                errors.append(
                    "chatbot_STORAGE=azure but missing:\n"
                    + "\n".join(f"  - {v}" for v in missing)
                )

        if self.pdf_filler_mode not in ("none", "") and not self.pdf_path:
            errors.append("chatbot_PDF_FILLER is set but chatbot_PDF_PATH is missing.")

        if (
            self.pdf_filler_mode == "mapper"
            and self.mapper_api_url
            and not self.mapper_api_key
        ):
            warns.append("MAPPER_API_KEY is not set but MAPPER_API_URL is configured.")

        if self.telemetry_enabled and not self.telemetry_endpoint:
            warns.append(
                "chatbot_TELEMETRY=true but chatbot_TELEMETRY_ENDPOINT is not set."
            )

        for w in warns:
            warnings.warn(f"[chatbot-sdk] {w}", stacklevel=3)

        if errors:
            raise OSError(
                "\n\n[chatbot-sdk] Configuration errors:\n\n"
                + "\n\n".join(f"  X {e}" for e in errors)
                + "\n\nFix the above and restart. See .env.example for all options.\n"
            )
