"""
LiteLLM corrector backend.

Used during feedback processing (API 4) to generate corrected snake_case
field names from user error reports. Works with any LiteLLM provider:
  openai/gpt-4o-mini
  anthropic/claude-3-haiku-20240307
  groq/llama-3.1-8b-instant
  bedrock/anthropic.claude-3-haiku-20240307-v1:0
  azure/my-gpt4-deployment
  ollama/llama3.1

Install: pip install ragpdf-sdk[litellm]
"""
import json
import logging
from ragpdf.correctors.base import FieldCorrectorBackend

logger = logging.getLogger(__name__)


class LiteLLMCorrectorBackend(FieldCorrectorBackend):
    """
    LiteLLM corrector — use any provider for field name correction during feedback.
    """

    def __init__(self, model: str = "", temperature: float = None, max_tokens: int = None):
        try:
            import litellm
            self._litellm = litellm
        except ImportError:
            raise ImportError(
                "LiteLLMCorrectorBackend requires litellm. "
                "Install with: pip install ragpdf-sdk[litellm]"
            )
        from ragpdf.config.settings import (
            RAGPDF_LITELLM_CORRECTOR_MODEL,
            RAGPDF_LITELLM_CORRECTOR_TEMP,
            RAGPDF_LITELLM_CORRECTOR_TOKENS,
        )
        self._model       = model or RAGPDF_LITELLM_CORRECTOR_MODEL
        self._temperature = temperature if temperature is not None else RAGPDF_LITELLM_CORRECTOR_TEMP
        self._max_tokens  = max_tokens or RAGPDF_LITELLM_CORRECTOR_TOKENS
        logger.info(f"LiteLLMCorrectorBackend initialized: model={self._model}")

    def generate_corrected_field_name(self, error_data: dict) -> dict:
        prompt = f"""You are a form field mapping expert. Given this error report, return a standardized snake_case field name.

Field Name:    {error_data.get("field_name", "Unknown")}
Field Type:    {error_data.get("field_type", "Unknown")}
Value:         {error_data.get("value", "N/A")}
User Feedback: {error_data.get("feedback", "None")}
Error Type:    {error_data.get("error_type", "Unknown")}
Page:          {error_data.get("page_number", "Unknown")}

Rules:
1. Use snake_case (lowercase with underscores)
2. Be descriptive but concise
3. Follow standard field naming conventions

Respond with JSON only, no markdown:
{{"corrected_field_name": "your_name", "confidence": 0.95, "reasoning": "brief explanation"}}"""

        try:
            response = self._litellm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a field mapping expert. Respond with valid JSON only."},
                    {"role": "user",   "content": prompt},
                ],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            content = response.choices[0].message.content.strip()
            if "```" in content:
                content = content.split("```")[1].lstrip("json").strip()
            result = json.loads(content)
            logger.info(f"LiteLLM correction: {error_data.get('field_name')} -> {result.get('corrected_field_name')}")
            return result
        except Exception as e:
            logger.error(f"LiteLLM corrector error: {e}")
            fallback = error_data.get("field_name", "unknown_field").lower().replace(" ", "_")
            return {"corrected_field_name": fallback, "confidence": 0.5, "reasoning": f"Fallback due to error: {str(e)}"}
