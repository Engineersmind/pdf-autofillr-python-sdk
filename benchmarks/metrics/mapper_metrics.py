"""
Metrics for pdf-autofillr-mapper benchmark tasks.

Covers: field_extraction, field_mapping, form_filling
"""

import re

# ── field_extraction ─────────────────────────────────────────────────────────


def extraction_precision(extracted: set, expected: set) -> float:
    """Fraction of extracted fields that are real fields."""
    if not extracted:
        return 0.0
    raise NotImplementedError


def extraction_recall(extracted: set, expected: set) -> float:
    """Fraction of real fields that were found."""
    if not expected:
        return 0.0
    raise NotImplementedError


def extraction_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    raise NotImplementedError


# ── field_mapping ────────────────────────────────────────────────────────────


def mapping_exact_accuracy(predictions: dict, ground_truth: dict) -> float:
    """% of fields where predicted_key == expected_key (exact match)."""
    raise NotImplementedError


def mapping_fuzzy_accuracy(
    predictions: dict, ground_truth: dict, threshold: float = 0.5
) -> float:
    """% of fields with token overlap >= threshold between predicted and expected key."""
    raise NotImplementedError


def mapping_avg_confidence(predictions: dict) -> float:
    """Mean model confidence score across all predicted mappings."""
    raise NotImplementedError


# ── form_filling ─────────────────────────────────────────────────────────────


def fill_accuracy(filled: dict, expected: dict) -> float:
    """% of fields filled with the correct value (normalised string match)."""
    raise NotImplementedError


def _normalize(v: str) -> str:
    return re.sub(r"[^\w\s]", "", v.lower().strip())


# ── performance (shared) ─────────────────────────────────────────────────────

MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "llama3.1": {"input": 0.0, "output": 0.0},
    "mistral": {"input": 0.0, "output": 0.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    MODEL_PRICING.get(model, {"input": 0, "output": 0})
    raise NotImplementedError
