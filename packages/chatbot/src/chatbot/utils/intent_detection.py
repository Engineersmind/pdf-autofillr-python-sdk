# chatbot/utils/intent_detection.py
"""Skip and exit intent detection."""
from __future__ import annotations

# FIX B: removed "no" — it belongs only in is_negative(), not skip detection.
# Having "no" in SKIP_PHRASES caused any yes/no prompt (update existing data,
# optional fields, mailing check) to be misrouted as a skip.
SKIP_PHRASES = {"skip", "n/a", "na", "not applicable", "don't have", "do not have", "none", "-"}
EXIT_PHRASES = {"exit", "quit", "stop", "cancel", "bye", "goodbye", "done", "finish"}


def is_skip_intent(text: str) -> bool:
    return text.strip().lower() in SKIP_PHRASES


def is_exit_intent(text: str) -> bool:
    return text.strip().lower() in EXIT_PHRASES


def is_affirmative(text: str) -> bool:
    return text.strip().lower() in {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "1", "confirm"}


def is_negative(text: str) -> bool:
    return text.strip().lower() in {"no", "n", "nope", "nah", "0", "2"}