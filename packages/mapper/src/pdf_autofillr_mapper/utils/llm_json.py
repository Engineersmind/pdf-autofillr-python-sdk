"""
Utilities for parsing and validating JSON responses from LLMs.

LLMs often wrap JSON in markdown code fences (```json ... ```) or include
preamble text. This module handles that uniformly across all call sites.
"""

import json
import re
import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, RootModel, field_validator

logger = logging.getLogger(__name__)

# Matches opening/closing markdown code fences (with or without 'json' language tag)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_llm_json(text: str) -> Any:
    """
    Parse JSON from an LLM response, tolerating markdown code fences and
    leading/trailing prose.

    Strategy:
      1. Strip ```json ... ``` fences and try json.loads directly.
      2. Find the first {...} block in the text and try json.loads on that.
      3. Raise json.JSONDecodeError if nothing works.
    """
    stripped = _FENCE_RE.sub("", text).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Fall back: find the first JSON object in the response
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError("No valid JSON object found in LLM response", text, 0)


# ---------------------------------------------------------------------------
# Pydantic models for semantic mapper output
# ---------------------------------------------------------------------------

class FieldMatch(BaseModel):
    """A single field mapping returned by the semantic mapper LLM."""
    key: Optional[str] = None
    con: float = 0.0

    @field_validator("con", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float:
        """Accept numeric strings, clamp to [0, 1]."""
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("key", mode="before")
    @classmethod
    def normalise_key(cls, v: Any) -> Optional[str]:
        """Treat empty strings and the literal string 'null' as None."""
        if v is None or v == "" or (isinstance(v, str) and v.strip().lower() == "null"):
            return None
        return v


class MappingOutput(RootModel):
    """Full LLM response for one prompt chunk: fid (str) → FieldMatch."""
    root: Dict[str, FieldMatch]

    def items(self):
        return self.root.items()

    def __len__(self):
        return len(self.root)
