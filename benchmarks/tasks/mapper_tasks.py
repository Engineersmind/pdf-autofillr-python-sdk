"""
Benchmark tasks for pdf-autofillr-mapper.

Tasks:
  field_extraction — detect all form fields in a PDF
  field_mapping    — LLM maps fields to schema keys
  form_filling     — fill embedded PDF with user data
"""


def field_extraction(pdf_path: str, ground_truth: dict) -> dict:
    """
    Run field extraction and score against ground truth.

    Returns:
        {"precision": float, "recall": float, "f1": float,
         "extracted_fields": int, "expected_fields": int}
    """
    raise NotImplementedError


def field_mapping(
    pdf_path: str, schema_keys_path: str, ground_truth: dict, model: str
) -> dict:
    """
    Run field mapping via LLM and score against ground truth.

    Returns:
        {"accuracy_exact": float, "accuracy_fuzzy": float, "avg_confidence": float,
         "correct": int, "total_mappable": int,
         "latency_ms": float, "cost_usd": float, "tokens_used": int}
    """
    raise NotImplementedError


def form_filling(embedded_pdf_path: str, user_data: dict, ground_truth: dict) -> dict:
    """
    Fill an embedded PDF and score against expected values.

    Returns:
        {"fill_accuracy": float, "correct": int, "total_fields": int, "latency_ms": float}
    """
    raise NotImplementedError
