"""
Benchmark tasks for pdf-autofillr-chatbot.

Tasks:
  conversation_extraction — chatbot collects correct field values through dialogue
  session_completion      — measures how often sessions reach PDF fill
  field_coverage          — what % of required fields are collected
"""


def conversation_extraction(
    transcript_path: str,
    form_keys: list[str],
    ground_truth: dict,
    model: str,
) -> dict:
    """
    Simulate a chatbot session from a transcript and score field extraction.

    Args:
        transcript_path: Path to a JSON conversation transcript.
        form_keys: Required form field keys.
        ground_truth: Expected values for each field key.
        model: LLM model string.

    Returns:
        {"extraction_accuracy": float, "field_coverage": float,
         "turns": int, "completed": bool,
         "latency_ms": float, "cost_usd": float, "tokens_used": int}
    """
    raise NotImplementedError


def session_completion(sessions_dir: str) -> dict:
    """
    Aggregate session completion across a directory of session result files.

    Returns:
        {"completion_rate": float, "avg_turns": float, "total_sessions": int}
    """
    raise NotImplementedError
