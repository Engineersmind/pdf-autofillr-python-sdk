# chatbot/utils/field_utils.py
"""Missing fields detection, field classification, resolution, and form_pf filtering."""
from __future__ import annotations
from typing import List, Tuple

from chatbot.core.states import (
    FORM_PF_FIELD_PREFIX,
    INTERNAL_SPLIT_FIELD_PREFIXES,
    US_COUNTRY_VALUES,
)


def get_missing_mandatory_keys(live_fill_flat: dict, mandatory_flat: dict) -> List[str]:
    """Return mandatory field keys that have not been filled yet."""
    missing = []
    for key in mandatory_flat:
        val = live_fill_flat.get(key)
        if val is None or val == "":
            missing.append(key)
    return missing


def get_optional_fields(live_fill_flat: dict, mandatory_flat: dict) -> List[str]:
    """Return fields present in live_fill_flat but not mandatory and still empty."""
    mandatory_keys = set(mandatory_flat.keys())
    return [
        k for k, v in live_fill_flat.items()
        if k not in mandatory_keys and (v is None or v == "")
    ]


def classify_fields_by_type(field_keys: List[str], meta_form_keys: dict) -> Tuple[List[str], List[str]]:
    """
    Split field_keys into (boolean_fields, text_fields).
    Uses meta_form_keys to determine type.
    """
    booleans, texts = [], []
    for key in field_keys:
        ftype = _get_field_type(key, meta_form_keys)
        if ftype == "boolean":
            booleans.append(key)
        else:
            texts.append(key)
    return booleans, texts


def _get_field_type(field_key: str, meta_form_keys: dict) -> str:
    """Lookup field type in meta_form_keys. Defaults to 'text'."""
    parts = field_key.split(".")
    node = meta_form_keys
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part, {})
        else:
            return "text"
    if isinstance(node, dict):
        return node.get("type", "text")
    return "text"


def format_field_name(key: str) -> str:
    """Convert a field path to a human-readable label."""
    parts = key.split(".")
    last = parts[-1].replace("_id", "").replace("_check", "")
    return last.replace("_", " ").title()


def is_internal_split_field(field_key: str) -> bool:
    """
    Return True for fields that are split parts for PDF filling only.
    These are NEVER shown to the user — mirrors Lambda behaviour.
    e.g. telephone_part_country_code, fax_part_1, fax_part_2, fax_part_3
    """
    leaf = field_key.split(".")[-1]
    return any(leaf.startswith(prefix) for prefix in INTERNAL_SPLIT_FIELD_PREFIXES)


def filter_user_facing_fields(live_fill_flat: dict) -> dict:
    """
    Return a copy of live_fill_flat with internal split fields removed.
    Use this when building prompts or displaying fields to the user.
    """
    return {k: v for k, v in live_fill_flat.items() if not is_internal_split_field(k)}


def filter_form_pf_fields(live_fill_flat: dict, registered_country: str) -> dict:
    """
    Remove form_pf fields for non-US investors.
    Mirrors Lambda: form_pf fields are filtered out if registered country != US.

    Args:
        live_fill_flat:     The full flat form dict.
        registered_country: The investor's registered country value (may be empty).

    Returns:
        A copy of live_fill_flat with form_pf fields removed for non-US investors.
    """
    if not registered_country:
        # Country not yet known — keep all fields
        return live_fill_flat

    is_us = registered_country.strip().lower() in US_COUNTRY_VALUES
    if is_us:
        return live_fill_flat

    # Non-US — strip all form_pf fields
    filtered = {
        k: v for k, v in live_fill_flat.items()
        if not k.startswith(FORM_PF_FIELD_PREFIX)
    }
    return filtered


def get_registered_country(live_fill_flat: dict) -> str:
    """
    Extract the registered country value from live_fill_flat.
    Tries common field path patterns used in the form schemas.
    """
    candidates = [
        "address_registered.address_registered_country_id",
        "address_registered.country",
        "registered_country",
        "country_of_registration",
    ]
    for key in candidates:
        val = live_fill_flat.get(key)
        if val and isinstance(val, str):
            return val
    return ""