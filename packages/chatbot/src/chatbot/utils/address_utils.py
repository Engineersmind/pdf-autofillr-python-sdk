# chatbot/utils/address_utils.py
"""Address group detection and auto-copy logic."""
from __future__ import annotations
from typing import List, Optional, Tuple

ADDRESS_PATTERNS = [
    ("address_registered.", "registered"),
    ("address_mailing.", "mailing"),
    ("address_jurisdiction.", "jurisdiction"),
    ("wiring_details.wiring_address.", "wiring"),
    ("wiring_address.", "wiring"),
]


def is_address_field(field_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Return (is_address, address_type, sub_field_name).
    e.g. "address_registered.address_registered_city_id" -> (True, "registered", "city")
    """
    for pattern, addr_type in ADDRESS_PATTERNS:
        if pattern in field_path:
            field_name = field_path.split(".")[-1]
            for prefix in [
                "address_registered_", "address_mailing_",
                "address_jurisdiction_", "wiring_details_address_", "wiring_address_",
            ]:
                field_name = field_name.replace(prefix, "")
            field_name = field_name.replace("_id", "")
            return True, addr_type, field_name
    return False, None, None


def copy_registered_to_mailing(live_fill_flat: dict) -> dict:
    """
    Copy all registered address fields to their mailing equivalents.
    Returns a dict of newly copied fields.
    """
    copied = {}
    for key, value in list(live_fill_flat.items()):
        if "address_registered." in key:
            mailing_key = key.replace("address_registered.", "address_mailing.") \
                            .replace("address_registered_", "address_mailing_")
            if mailing_key in live_fill_flat and (live_fill_flat[mailing_key] is None or live_fill_flat[mailing_key] == ""):
                live_fill_flat[mailing_key] = value
                copied[mailing_key] = value
    return copied


def get_address_group_fields(field_path: str, all_fields: List[str]) -> List[str]:
    """Return all fields that belong to the same address group as field_path."""
    _, addr_type, _ = is_address_field(field_path)
    if not addr_type:
        return []

    pattern_map = {
        "registered": "address_registered.",
        "mailing": "address_mailing.",
        "jurisdiction": "address_jurisdiction.",
        "wiring": "wiring_address.",
    }
    prefix = pattern_map.get(addr_type, "")
    return [f for f in all_fields if prefix in f]


def check_mailing_fields(fields: dict) -> bool:
    """Return True if any mailing address fields exist in the dict."""
    return any("address_mailing" in k for k in fields)
