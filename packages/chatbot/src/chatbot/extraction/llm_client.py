# chatbot/src/chatbot/extraction/llm_client.py
"""
LLMClient — thin LiteLLM wrapper for chatbot field extraction.

Supports any model LiteLLM supports. Set CHATBOT_LLM_MODEL in .env.

Model string format (LiteLLM convention):
    openai/gpt-4o-mini                              needs OPENAI_API_KEY
    openai/gpt-4o                                   needs OPENAI_API_KEY
    anthropic/claude-3-5-haiku-20241022             needs ANTHROPIC_API_KEY
    anthropic/claude-3-5-sonnet-20241022            needs ANTHROPIC_API_KEY
    bedrock/anthropic.claude-3-haiku-20240307-v1:0  needs AWS creds
    azure/gpt-4o                                    needs AZURE_API_KEY + AZURE_API_BASE
    vertex_ai/gemini-1.5-flash                      needs GOOGLE creds
    groq/llama-3.1-8b-instant                       needs GROQ_API_KEY
    ollama/llama3.1                                 needs Ollama running locally

The correct API key env var is determined by the provider prefix.
Set CHATBOT_LLM_API_KEY as a universal override (maps to the right
provider key automatically via LiteLLM's key resolution).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Default model — fast, cheap, good enough for structured extraction
DEFAULT_MODEL = "openai/gpt-4o-mini"


class LLMClient:
    """
    Thin wrapper around litellm.completion for chatbot field extraction.

    Args:
        model:       LiteLLM model string. Defaults to CHATBOT_LLM_MODEL env var,
                     then falls back to openai/gpt-4o-mini.
        api_key:     Optional API key override. When set, passed as api_key to
                     litellm (works for OpenAI, Anthropic, Groq etc.)
                     For AWS Bedrock or Vertex AI, leave None and set the
                     provider-specific env vars instead.
        temperature: Sampling temperature. 0.0 = deterministic.
        max_tokens:  Max tokens in response.
        timeout:     Seconds before giving up on an LLM call.
        max_retries: Retry attempts on transient failure.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 60,
        max_retries: int = 2,
    ):
        self.model = model or os.getenv("CHATBOT_LLM_MODEL", DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("CHATBOT_LLM_API_KEY") or _infer_api_key(self.model)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

        logger.info("LLMClient initialised with model=%s", self.model)

    def call(self, prompt: str) -> str:
        """
        Send a prompt and return the text response.

        Raises:
            Exception — any litellm error bubbles up so Extractor can catch
            it and fall back to FallbackExtractor.
        """
        import litellm

        kwargs: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "num_retries": self.max_retries,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        # Azure needs base URL
        azure_base = os.getenv("AZURE_API_BASE") or os.getenv("AZURE_OPENAI_ENDPOINT")
        if azure_base and self.model.startswith("azure/"):
            kwargs["api_base"] = azure_base
            kwargs["api_version"] = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")

        response = litellm.completion(**kwargs)
        return response.choices[0].message.content or ""


def _infer_api_key(model: str) -> Optional[str]:
    """
    Try to find the right API key from env vars based on the model prefix.
    Returns None if nothing found — LiteLLM will try its own resolution.
    """
    m = model.lower()
    if m.startswith("openai/") or m.startswith("gpt-"):
        return os.getenv("OPENAI_API_KEY")
    if m.startswith("anthropic/") or m.startswith("claude-"):
        return os.getenv("ANTHROPIC_API_KEY")
    if m.startswith("groq/"):
        return os.getenv("GROQ_API_KEY")
    if m.startswith("gemini/"):
        return os.getenv("GEMINI_API_KEY")
    # bedrock, vertex_ai, ollama — no simple key, use env vars directly
    return None
