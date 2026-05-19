"""
Metrics for pdf-autofillr-chatbot benchmark tasks.

Covers: conversation_quality, extraction_accuracy, session_completion
"""


def extraction_accuracy(extracted: dict, expected: dict) -> float:
    """
    % of form fields correctly extracted from the conversation transcript.

    Args:
        extracted: {field_key: extracted_value}
        expected:  {field_key: expected_value}
    """
    raise NotImplementedError


def session_completion_rate(sessions: list[dict]) -> float:
    """
    % of sessions that reached the PDF-fill step without aborting.

    Args:
        sessions: list of session result dicts each with {"completed": bool}
    """
    raise NotImplementedError


def avg_turns_to_completion(sessions: list[dict]) -> float:
    """
    Mean number of conversation turns for completed sessions.

    Args:
        sessions: list with {"completed": bool, "turns": int}
    """
    raise NotImplementedError


def field_coverage(extracted: dict, form_keys: list[str]) -> float:
    """
    % of required form fields collected at end of session.

    Args:
        extracted: fields the chatbot collected
        form_keys: the full list of required keys
    """
    raise NotImplementedError
