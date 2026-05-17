"""
Benchmark tasks for pdf-autofillr-rag.

Tasks:
  field_prediction  — predict canonical key from field name using RAG
  feedback_loop     — measure accuracy improvement after correction cycle
  vector_retrieval  — precision/recall of vector store lookup
"""


def field_prediction(
    fields: list[str],
    vector_store_path: str,
    ground_truth: dict,
    model: str,
) -> dict:
    """
    Run RAG prediction for a list of raw field names and score.

    Args:
        fields: Raw PDF field names to predict canonical keys for.
        vector_store_path: Path to vector_database.json.
        ground_truth: {field_name: expected_canonical_key}
        model: Corrector model string.

    Returns:
        {"accuracy": float, "top3_accuracy": float, "mrr": float,
         "avg_confidence": float, "latency_ms": float, "cost_usd": float}
    """
    raise NotImplementedError


def feedback_loop(
    fields: list[str],
    vector_store_path: str,
    ground_truth: dict,
    corrections: dict,
    model: str,
) -> dict:
    """
    Run prediction → apply corrections → re-run prediction, measure improvement.

    Args:
        corrections: {field_name: correct_canonical_key}

    Returns:
        {"accuracy_before": float, "accuracy_after": float,
         "improvement": float, "vectors_updated": int}
    """
    raise NotImplementedError


def vector_retrieval(
    query_fields: list[str],
    vector_store_path: str,
    relevant_map: dict,
    top_k: int = 5,
) -> dict:
    """
    Measure precision and recall of vector store retrieval.

    Args:
        relevant_map: {field_name: [relevant_vector_ids]}

    Returns:
        {"precision": float, "recall": float, "f1": float, "avg_top_k": int}
    """
    raise NotImplementedError
