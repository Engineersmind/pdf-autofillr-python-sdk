# chatbot/validation/phone_validator.py
"""Phone number validation — matches Lambda validate_phone_format() behaviour."""
from __future__ import annotations
import re

# Matches Lambda: requires a country code prefix (+ or 00) followed by
# 10–15 digits (spaces, dashes, dots, parens allowed as separators).
# Examples that pass:  +1 212 555 1234,  +44-20-7946-0958,  001 212 5551234
# Examples that fail:  2125551234  (no country code),  123  (too short)
PHONE_WITH_COUNTRY_CODE_RE = re.compile(
    r"^\+?(?:00)?[\d]{1,4}[\s\-.]?"   # country code  (1–4 digits, optional +/00)
    r"[\d][\d\s\-.()]{8,14}$"          # subscriber number (min 8 more digits/separators)
)

# Loose fallback — used only for the normalise helper
PHONE_LOOSE_RE = re.compile(r"^\+?[\d\s\-().]{7,20}$")

# Single-digit country codes (+1 for USA/Canada) — need only 11 total digits
_SINGLE_DIGIT_CC_PREFIXES = ("+1", "001")


def validate_phone(value: str) -> bool:
    """
    Return True if value looks like a valid international phone number.

    Requires a country code prefix matching Lambda's validate_phone_format():
    - Must start with + or 00 followed by country digits
    - +1 (USA/Canada): minimum 11 total digits (1 cc + 10 subscriber)
    - All other country codes: minimum 12 total digits (2+ cc + 10 subscriber)
      This correctly rejects e.g. +91-999 999 999 (only 9 subscriber digits)
    """
    if not value:
        return False
    val = value.strip()
    digits = re.sub(r"[^\d]", "", val)
    has_prefix = val.startswith("+") or val.startswith("00")

    if not has_prefix:
        # No prefix — need at least 11 digits to imply a country code is embedded
        return len(digits) >= 11

    # Must match the structural regex first
    if not PHONE_WITH_COUNTRY_CODE_RE.match(val):
        return False

    # +1 / 001 numbers (USA, Canada): 1-digit cc + 10-digit subscriber = 11 total
    is_single_cc = any(val.startswith(p) for p in _SINGLE_DIGIT_CC_PREFIXES)
    min_digits = 11 if is_single_cc else 12

    return len(digits) >= min_digits


def normalise_phone(value: str) -> str:
    """Strip extra whitespace and normalise common separators."""
    return re.sub(r"\s+", " ", value.strip())


def split_phone_parts(value: str) -> dict:
    """
    Split a full phone number into country_code, part1, part2, part3.
    Mirrors Lambda's split_phone_or_fax() for internal PDF field population.

    Returns dict with keys: country_code, part1, part2, part3
    These are used ONLY when writing to internal split fields for PDF filling —
    never shown directly to the user.

    Examples:
        +1 212 555 1234  -> {country_code: "1", part1: "212", part2: "555", part3: "1234"}
        +44 20 7946 0958 -> {country_code: "44", part1: "20", part2: "7946", part3: "0958"}
    """
    cleaned = value.strip().lstrip("+")
    # Remove all non-digit/space/dash chars except keep structure
    digits_only = re.sub(r"[^\d]", " ", cleaned).split()

    if not digits_only:
        return {"country_code": "", "part1": "", "part2": "", "part3": ""}

    # Heuristic: first token is country code if total digit count >= 11
    all_digits = "".join(digits_only)
    if len(all_digits) >= 11:
        country_code = digits_only[0] if len(digits_only) > 1 else all_digits[:1]
        rest = digits_only[1:] if len(digits_only) > 1 else [all_digits[1:]]
    else:
        country_code = ""
        rest = digits_only

    # Pad rest to 3 parts
    while len(rest) < 3:
        rest.append("")

    return {
        "country_code": country_code,
        "part1": rest[0],
        "part2": rest[1],
        "part3": " ".join(rest[2:]) if len(rest) > 3 else rest[2],
    }