# src/ragpdf/correctors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CorrectionResult:
    """
    Structured result from a corrector backend.

    Attributes:
        corrected_field_name : Standardized snake_case field name
        confidence           : Confidence score 0.0 – 1.0
        reasoning            : Brief explanation from the LLM
    """
    corrected_field_name: str
    confidence: float = 0.8
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "corrected_field_name": self.corrected_field_name,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


class FieldCorrectorBackend(ABC):
    """
    Abstract LLM corrector backend.
    Called during user feedback processing (API 4) to generate standardized
    corrected field names from user error reports.

    Implement this to use any LLM (Llama, Mistral, Gemini, etc.)

    Example:
        class MyCorrector(FieldCorrectorBackend):
            def generate_corrected_field_name(self, error_data: dict) -> dict:
                # Call your LLM
                return {
                    "corrected_field_name": "investor_full_legal_name",
                    "confidence": 0.92,
                    "reasoning": "Standard snake_case for investor name field"
                }
    """

    @abstractmethod
    def generate_corrected_field_name(self, error_data: dict) -> dict:
        """
        Given an error report, return a standardized field name.

        Input error_data:
            field_name  : str   — what the system predicted
            field_type  : str   — text / boolean / etc.
            value       : any   — the value that was filled
            feedback    : str   — user's feedback text
            page_number : int   — PDF page
            corners     : list  — bounding box coordinates
            error_type  : str   — wrong_field_name / wrong_value / etc.

        Returns dict OR CorrectionResult with:
            corrected_field_name : str   — snake_case correct name
            confidence           : float — 0.0 – 1.0
            reasoning            : str   — brief explanation
        """
