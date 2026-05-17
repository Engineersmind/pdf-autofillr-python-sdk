"""
Metrics for pdf-autofillr-rag benchmark tasks.

Covers: prediction_accuracy, feedback_improvement, vector_store_quality
"""


def prediction_accuracy(predictions: dict, ground_truth: dict) -> float:
    """
    % of field predictions where predicted canonical key == expected key.

    Args:
        predictions: {field_name: {"canonical_key": str, "confidence": float}}
        ground_truth: {field_name: {"expected_key": str}}
    """
    raise NotImplementedError


def top_k_accuracy(predictions: dict, ground_truth: dict, k: int = 3) -> float:
    """
    % of fields where the correct key appears in the top-k candidates.

    Args:
        predictions: {field_name: {"candidates": [{"key": str, "score": float}]}}
        ground_truth: {field_name: {"expected_key": str}}
    """
    raise NotImplementedError


def avg_confidence(predictions: dict) -> float:
    """Mean confidence score across all RAG predictions."""
    raise NotImplementedError


def feedback_improvement(before: float, after: float) -> float:
    """
    Accuracy improvement after one feedback cycle.

    Returns: after - before (positive = improvement)
    """
    return after - before


def vector_retrieval_precision(retrieved: list[str], relevant: list[str]) -> float:
    """
    % of retrieved vectors that are relevant to the query.

    Args:
        retrieved: list of retrieved field_ids / vector_ids
        relevant: list of known-relevant field_ids
    """
    raise NotImplementedError


def mrr(predictions: dict, ground_truth: dict) -> float:
    """
    Mean Reciprocal Rank — measures how high the correct key ranks.

    Args:
        predictions: {field_name: {"candidates": [{"key": str}]}}  (ordered)
        ground_truth: {field_name: {"expected_key": str}}
    """
    raise NotImplementedError
