"""
Benchmark tasks for pdf-autofillr-doc-upload.

Tasks:
  document_extraction — extract field values from an uploaded document
  end_to_end_fill     — extract + fill the PDF, score final output
"""

SUPPORTED_FORMATS = [
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "csv",
    "json",
    "txt",
    "md",
    "html",
    "xml",
]


def document_extraction(
    document_path: str,
    schema_keys: list[str],
    ground_truth: dict,
    model: str,
) -> dict:
    """
    Run LLM extraction on a document and score against ground truth.

    Args:
        document_path: Path to input document (any supported format).
        schema_keys: Field keys to extract.
        ground_truth: Expected extracted values.
        model: LLM model string.

    Returns:
        {"extraction_accuracy": float, "format": str,
         "correct": int, "total_fields": int,
         "latency_ms": float, "cost_usd": float, "tokens_used": int}
    """
    raise NotImplementedError


def end_to_end_fill(
    document_path: str,
    blank_pdf_path: str,
    schema_keys: list[str],
    ground_truth: dict,
    model: str,
) -> dict:
    """
    Full pipeline: extract from document → fill PDF → score filled output.

    Returns:
        {"extraction_accuracy": float, "fill_accuracy": float, "format": str,
         "latency_ms": float, "cost_usd": float}
    """
    raise NotImplementedError
