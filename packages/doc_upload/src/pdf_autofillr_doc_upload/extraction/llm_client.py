# pdf_autofillr_doc_upload/extraction/llm_client.py
"""
LLMClient — thin LiteLLM wrapper for document extraction.

Supports any model LiteLLM supports. Set DOC_UPLOAD_LLM_MODEL in .env.

Model string format (LiteLLM convention):
    openai/gpt-4.1-mini                             needs OPENAI_API_KEY
    openai/gpt-4o                                   needs OPENAI_API_KEY
    anthropic/claude-3-5-haiku-20241022             needs ANTHROPIC_API_KEY
    anthropic/claude-3-5-sonnet-20241022            needs ANTHROPIC_API_KEY
    bedrock/anthropic.claude-3-haiku-20240307-v1:0  needs AWS creds
    azure/gpt-4o                                    needs AZURE_API_KEY + AZURE_API_BASE
    vertex_ai/gemini-1.5-flash                      needs GOOGLE creds
    groq/llama-3.1-8b-instant                       needs GROQ_API_KEY
    ollama/llama3.1                                 needs Ollama running locally
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai/gpt-4.1-mini"


class LLMClient:
    """
    Thin wrapper around litellm.completion for structured extraction.

    Args:
        model:       LiteLLM model string.
        api_key:     Optional API key override.
        temperature: Sampling temperature (0.0 = deterministic).
        max_tokens:  Max tokens in response.
        timeout:     Seconds before timeout.
        max_retries: Retry attempts on transient failure.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.model = model or os.getenv("DOC_UPLOAD_LLM_MODEL", DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("DOC_UPLOAD_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the LLM and return the raw string response.

        Args:
            system_prompt: System instruction.
            user_prompt:   User turn (the document + schema).

        Returns:
            Raw string content from the model.
        """
        import litellm

        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "num_retries": self.max_retries,
        }

        # Inject API key if provided (works for OpenAI, Anthropic, Groq, etc.)
        if self.api_key:
            kwargs["api_key"] = self.api_key

        logger.debug("LLMClient: calling %s", self.model)
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content
