"""
Metrics for pdf-autofillr-doc-upload benchmark tasks.

Covers: extraction_accuracy per document format, fill_accuracy
"""


def extraction_accuracy_by_format(results: list[dict]) -> dict:
    """
    Per-format extraction accuracy.

    Args:
        results: list of {"format": str, "extracted": dict, "expected": dict}

    Returns:
        {"pdf": float, "docx": float, "xlsx": float, ...}
    """
    raise NotImplementedError


def overall_extraction_accuracy(extracted: dict, expected: dict) -> float:
    """% of fields correctly extracted from the uploaded document."""
    raise NotImplementedError


def fill_accuracy(filled: dict, expected: dict) -> float:
    """% of PDF fields filled with the correct extracted value."""
    raise NotImplementedError


def format_support_coverage(formats_tested: list[str]) -> float:
    """
    % of supported formats present in the test suite.
    Supported: pdf, docx, pptx, xlsx, csv, json, txt, md, html, xml
    """
    raise NotImplementedError
