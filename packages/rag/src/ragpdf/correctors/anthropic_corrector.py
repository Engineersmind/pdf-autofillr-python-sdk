# src/ragpdf/correctors/anthropic_corrector.py
import json
import logging
from ragpdf.correctors.base import FieldCorrectorBackend

logger = logging.getLogger(__name__)


class AnthropicCorrectorBackend(FieldCorrectorBackend):
    """
    Anthropic Claude corrector backend.

    Install: pip install ragpdf-sdk[anthropic]

    Usage:
        corrector = AnthropicCorrectorBackend(
            api_key="sk-ant-...",
            model="claude-sonnet-4-20250514",
        )
    """

    def __init__(self, api_key: str = "", model: str = ""):
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install ragpdf-sdk[anthropic]")
        from ragpdf.config.settings import ANTHROPIC_API_KEY, RAGPDF_ANTHROPIC_MODEL
        self._client = anthropic.Anthropic(api_key=api_key or ANTHROPIC_API_KEY)
        self._model = model or RAGPDF_ANTHROPIC_MODEL

    def generate_corrected_field_name(self, error_data: dict) -> dict:
        prompt = f"""Given this form field error report, return a standardized snake_case field name.

Field Name: {error_data.get("field_name", "Unknown")}
Field Type: {error_data.get("field_type", "Unknown")}
Value:      {error_data.get("value", "N/A")}
Feedback:   {error_data.get("feedback", "None")}
Error Type: {error_data.get("error_type", "Unknown")}

Return JSON only: {{"corrected_field_name": "name", "confidence": 0.95, "reasoning": "explanation"}}"""
        try:
            msg = self._client.messages.create(
                model=self._model, max_tokens=256,
                messages=[{"role": "user", "content": prompt}]
            )
            content = msg.content[0].text.strip()
            if "```" in content:
                content = content.split("```")[1].lstrip("json").strip()
            result = json.loads(content)
            logger.info(f"Anthropic correction: {error_data.get('field_name')} -> {result.get('corrected_field_name')}")
            return result
        except Exception as e:
            logger.error(f"Anthropic corrector error: {e}")
            fallback = error_data.get("field_name", "unknown_field").lower().replace(" ", "_")
            return {"corrected_field_name": fallback, "confidence": 0.5, "reasoning": f"Fallback: {str(e)}"}
