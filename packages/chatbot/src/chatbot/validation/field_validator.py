# chatbot/validation/field_validator.py
"""General field validation."""
from __future__ import annotations
import re
from chatbot.validation.phone_validator import validate_phone

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_field(field_key: str, value) -> tuple[bool, str]:
    """
    Validate a field value.
    Returns (is_valid, error_message).
    """
    if value is None or value == "":
        return False, "Value is empty"

    lk = field_key.lower()

    if "email" in lk:
        if not EMAIL_RE.match(str(value)):
            return False, f"'{value}' does not look like a valid email address."

    if any(w in lk for w in ("phone", "telephone", "mobile", "fax")):
        if not validate_phone(str(value)):
            return False, (
                f"'{value}' does not look like a valid phone number. "
                "Please include country code (e.g. +1 212 555 1234)."
            )

    # FIX F: removed "boolean" in lk — real boolean field keys end in "_check"
    # (e.g. "individual_check"), never "boolean_something". Dead code removed.
    if "_check" in lk:
        if value not in (True, False, None):
            return False, f"Boolean field expects true/false/null, got: {value!r}"

    return True, ""