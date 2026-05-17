# src/ragpdf/correctors/noop_corrector.py
"""
No-op corrector — pass-through that returns the original field name cleaned up.
Use when you don't want LLM calls during feedback processing.
"""
from ragpdf.correctors.base import FieldCorrectorBackend


class NoOpCorrectorBackend(FieldCorrectorBackend):
    """
    Pass-through corrector. Cleans the field name to snake_case without any LLM call.
    Useful for offline deployments or when you want to disable LLM correction.
    """

    def generate_corrected_field_name(self, error_data: dict) -> dict:
        name = error_data.get("field_name", "unknown_field")
        cleaned = name.lower().replace(" ", "_").replace("-", "_")
        return {
            "corrected_field_name": cleaned,
            "confidence": 0.6,
            "reasoning": "NoOpCorrector: original name cleaned to snake_case",
        }
