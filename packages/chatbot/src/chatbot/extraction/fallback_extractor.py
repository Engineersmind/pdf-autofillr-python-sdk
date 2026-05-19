# chatbot/extraction/fallback_extractor.py
"""
FallbackExtractor — regex-based extraction. No LLM, no network call.
Used when LLM is unavailable or returns empty.
"""
from __future__ import annotations

import re
from typing import Optional


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?[\d\s\-().]{7,20})")
ZIP_RE   = re.compile(r"\b(\d{5}(?:-\d{4})?)\b")


class FallbackExtractor:
    """
    Regex-based fallback extractor.

    Extracts common patterns (email, phone, zip) without LLM calls.
    Only populates fields whose names suggest the pattern.
    """

    def extract(self, user_input: str, live_fill_flat: dict) -> dict:
        result: dict = {}
        lc = user_input.lower()

        # Email
        emails = EMAIL_RE.findall(user_input)
        if emails:
            for key in live_fill_flat:
                if "email" in key:
                    result[key] = emails[0]
                    break

        # Phone
        phones = PHONE_RE.findall(user_input)
        if phones:
            for key in live_fill_flat:
                if any(w in key for w in ("phone", "telephone", "mobile", "fax")):
                    result[key] = phones[0].strip()
                    break

        # ZIP / postal code
        zips = ZIP_RE.findall(user_input)
        if zips:
            for key in live_fill_flat:
                if any(w in key for w in ("zip", "postal")):
                    result[key] = zips[0]
                    break

        return result
