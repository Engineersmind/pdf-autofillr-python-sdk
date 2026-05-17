# src/ragpdf/correctors/openai_corrector.py
import json
import logging
from ragpdf.correctors.base import FieldCorrectorBackend

logger = logging.getLogger(__name__)


class OpenAICorrectorBackend(FieldCorrectorBackend):
    """
    OpenAI GPT-4 corrector backend (default).

    Install: pip install ragpdf-sdk[openai]

    Usage:
        corrector = OpenAICorrectorBackend(
            api_key="sk-...",
            model="gpt-4-turbo-preview",
            temperature=0.3,
        )
    """

    def __init__(self, api_key: str = "", model: str = "", temperature: float = 0.3, max_tokens: int = 500):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install ragpdf-sdk[openai]")
        from ragpdf.config.settings import OPENAI_API_KEY, RAGPDF_OPENAI_MODEL, RAGPDF_OPENAI_TEMPERATURE, RAGPDF_OPENAI_MAX_TOKENS
        self._client = OpenAI(api_key=api_key or OPENAI_API_KEY)
        self._model = model or RAGPDF_OPENAI_MODEL
        self._temperature = temperature or RAGPDF_OPENAI_TEMPERATURE
        self._max_tokens = max_tokens or RAGPDF_OPENAI_MAX_TOKENS

    def generate_corrected_field_name(self, error_data: dict) -> dict:
        prompt = f"""You are a form field mapping expert. Given the error report below, return a standardized snake_case field name.

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
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a field mapping expert. Respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            result = json.loads(content)
            logger.info(f"GPT-4 correction: {error_data.get('field_name')} -> {result.get('corrected_field_name')}")
            return result
        except Exception as e:
            logger.error(f"OpenAI corrector error: {e}")
            fallback = error_data.get("field_name", "unknown_field").lower().replace(" ", "_")
            return {"corrected_field_name": fallback, "confidence": 0.5, "reasoning": f"Fallback: {str(e)}"}
