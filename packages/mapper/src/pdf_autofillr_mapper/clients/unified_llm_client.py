"""
Unified LLM Client using LiteLLM.

This module provides a single interface for all LLM providers:
- Anthropic (Direct API or AWS Bedrock)
- OpenAI (Direct or Azure)
- Google (Vertex AI, Gemini)
- Local models (Ollama)
- 100+ other providers

Features:
- Token counting before/after API calls
- Cost tracking per request
- Async support
- Automatic retries and fallbacks
- Rate limiting
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import litellm
from litellm import acompletion, completion, completion_cost, token_counter

# Configure LiteLLM
litellm.drop_params = True  # Drop unsupported params instead of erroring
litellm.set_verbose = False  # Set to True for debugging

logger = logging.getLogger(__name__)


@dataclass
class LLMUsage:
    """Token usage and cost information for an LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    model: str
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


@dataclass
class LLMResponse:
    """Response from LLM with usage tracking."""

    content: str
    usage: LLMUsage
    raw_response: Any  # Full LiteLLM response object


class UnifiedLLMClient:
    """
    Unified client for all LLM providers using LiteLLM.

    Model name format: {provider}/{model-name}

    Examples:
        - "claude-3-5-sonnet-20241022" (Anthropic Direct)
        - "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0" (AWS Bedrock)
        - "gpt-4o" (OpenAI)
        - "azure/gpt-4" (Azure OpenAI)
        - "vertex_ai/gemini-pro" (Google)
        - "ollama/llama2" (Local)

    Credentials:
        Set environment variables based on provider:
        - Anthropic: ANTHROPIC_API_KEY
        - OpenAI: OPENAI_API_KEY
        - Azure: AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
        - AWS Bedrock: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME
        - Vertex AI: GOOGLE_APPLICATION_CREDENTIALS, VERTEX_PROJECT, VERTEX_LOCATION
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
        max_retries: int = 3,
        fallback_models: Optional[list[str]] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize LLM client.

        Args:
            model: Model identifier (e.g., "claude-3-5-sonnet-20241022", "gpt-4o")
            api_key: Optional API key override. If not set, litellm reads the
                     provider-specific env var (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
            fallback_models: List of fallback models if primary fails
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.fallback_models = fallback_models or []
        self.api_key = api_key or None

        # Track cumulative usage
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.total_calls = 0

        logger.info(f"Initialized LLM client with model: {model}")

    def estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """
        Estimate token count for messages before making API call.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Estimated token count
        """
        try:
            count = token_counter(model=self.model, messages=messages)
            return count
        except Exception as e:
            logger.warning(f"Token estimation failed: {e}, using character count / 4")
            # Fallback: rough estimate (1 token ≈ 4 chars)
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            return total_chars // 4

    def complete(
        self,
        messages,  # Can be str or List[Dict[str, str]]
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Synchronous completion (blocking).

        Args:
            messages: Either a string prompt OR list of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional parameters for LiteLLM

        Returns:
            LLMResponse with content and usage info
        """
        # Convert string prompt to messages list format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        # Build request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "timeout": self.timeout,
            "num_retries": self.max_retries,
        }

        if max_tok:
            params["max_tokens"] = max_tok

        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        if self.api_key:
            params["api_key"] = self.api_key

        params.update(kwargs)

        # Log estimated tokens
        estimated_tokens = self.estimate_tokens(messages)
        logger.info(
            f"LLM call - Model: {self.model}, Estimated tokens: {estimated_tokens}"
        )

        # Make API call
        try:
            response = completion(**params)

            # Extract usage
            usage = self._extract_usage(response)

            # Update cumulative stats
            self.total_prompt_tokens += usage.prompt_tokens
            self.total_completion_tokens += usage.completion_tokens
            self.total_cost_usd += usage.cost_usd
            self.total_calls += 1

            cache_info = (
                f", cache_read={usage.cache_read_tokens}"
                f", cache_created={usage.cache_creation_tokens}"
                if usage.cache_read_tokens or usage.cache_creation_tokens
                else ""
            )
            logger.info(
                f"LLM response - Tokens: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens}"
                f"{cache_info}), Cost: ${usage.cost_usd:.6f}"
            )

            # Extract content
            content = response.choices[0].message.content

            return LLMResponse(content=content, usage=usage, raw_response=response)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def acomplete(
        self,
        messages,  # Can be str or List[Dict[str, str]]
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Async completion (non-blocking).

        Args:
            messages: Either a string prompt OR list of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional parameters for LiteLLM

        Returns:
            LLMResponse with content and usage info
        """
        # Convert string prompt to messages list format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        # Build request parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "timeout": self.timeout,
            "num_retries": self.max_retries,
        }

        if max_tok:
            params["max_tokens"] = max_tok

        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        if self.api_key:
            params["api_key"] = self.api_key

        params.update(kwargs)

        # Log estimated tokens
        estimated_tokens = self.estimate_tokens(messages)
        logger.info(
            f"LLM call - Model: {self.model}, Estimated tokens: {estimated_tokens}"
        )

        # Make async API call
        try:
            response = await acompletion(**params)

            # Extract usage
            usage = self._extract_usage(response)

            # Update cumulative stats
            self.total_prompt_tokens += usage.prompt_tokens
            self.total_completion_tokens += usage.completion_tokens
            self.total_cost_usd += usage.cost_usd
            self.total_calls += 1

            cache_info = (
                f", cache_read={usage.cache_read_tokens}"
                f", cache_created={usage.cache_creation_tokens}"
                if usage.cache_read_tokens or usage.cache_creation_tokens
                else ""
            )
            logger.info(
                f"LLM response - Tokens: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens}"
                f"{cache_info}), Cost: ${usage.cost_usd:.6f}"
            )

            # Extract content
            content = response.choices[0].message.content

            return LLMResponse(content=content, usage=usage, raw_response=response)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _extract_usage(self, response: Any) -> LLMUsage:
        """Extract usage and cost from LiteLLM response."""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens or 0
        completion_tokens = usage.completion_tokens or 0
        total_tokens = usage.total_tokens or (prompt_tokens + completion_tokens)

        # Anthropic prompt caching tokens
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        # OpenAI cached tokens (different field name)
        if not cache_read:
            cache_read = getattr(usage, "cached_tokens", 0) or 0

        # Calculate cost
        try:
            cost = completion_cost(completion_response=response)
        except Exception as e:
            logger.warning(f"Could not calculate cost: {e}")
            cost = 0.0

        return LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            model=self.model,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )

    def get_cumulative_stats(self) -> dict[str, Any]:
        """
        Get cumulative statistics for all LLM calls made with this client.

        Returns:
            Dict with total tokens, cost, and number of calls
        """
        return {
            "total_calls": self.total_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost_usd": self.total_cost_usd,
            "model": self.model,
        }

    def reset_stats(self):
        """Reset cumulative statistics."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.total_calls = 0


def create_llm_client(
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> UnifiedLLMClient:
    """
    Factory function to create LLM client from config or parameters.

    Args:
        model: Model identifier (if None, reads from environment/config)
        temperature: Sampling temperature
        max_tokens: Maximum response tokens
        **kwargs: Additional parameters for UnifiedLLMClient

    Returns:
        Configured UnifiedLLMClient instance
    """
    # If model not provided, try to get from environment
    if not model:
        model = os.getenv("LLM_MODEL", "gpt-4o")
        logger.info(f"Using model from environment: {model}")

    return UnifiedLLMClient(
        model=model, temperature=temperature, max_tokens=max_tokens, **kwargs
    )


# ── Prompt caching helpers ────────────────────────────────────────────────────

_CACHE_SPLIT_MARKER = "##CACHE_SPLIT##"


def _is_claude(model: str) -> bool:
    """Return True for any Anthropic / Bedrock Claude model."""
    m = model.lower()
    return "claude" in m or "anthropic" in m


def build_messages(model: str, prompt: str, system: Optional[str] = None) -> list:
    """
    Build an LLM messages list with prompt caching for Claude and OpenAI models.

    For Claude (Anthropic direct or Bedrock):
      - System message gets cache_control so it is cached once.
      - User prompt is split at ##CACHE_SPLIT## into a cached static block
        (instructions) and an uncached dynamic block (per-job data).

    For OpenAI / other models (gpt-4.1, gpt-4o, etc.):
      - System message gets cache_control (ephemeral) — supported since Nov 2024
      - User prompt is split at ##CACHE_SPLIT## into cached static + dynamic blocks
      - Note: litellm.drop_params=True no longer removes cache_control for OpenAI

    If ##CACHE_SPLIT## is absent the full prompt is sent as a single message.
    """
    msgs = []

    if system:
        # Both Claude and OpenAI support prompt caching now
        msgs.append(
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        )

    # Split prompt caching for both Claude and OpenAI
    if _CACHE_SPLIT_MARKER in prompt:
        static, dynamic = prompt.split(_CACHE_SPLIT_MARKER, 1)
        msgs.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": static.rstrip(),
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": dynamic.lstrip()},
                ],
            }
        )
    else:
        msgs.append(
            {"role": "user", "content": prompt.replace(_CACHE_SPLIT_MARKER, "")}
        )

    return msgs
