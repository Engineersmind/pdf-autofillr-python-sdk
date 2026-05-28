# chatbot/extraction/prompt_builder.py
"""
PromptBuilder — builds LLM extraction prompts dynamically from the schema.
"""

from __future__ import annotations

import json


class PromptBuilder:
    """
    Builds the extraction prompt from the developer's form schema.

    Subclass and override ``_base_rules()`` to add domain-specific rules::

        class HedgeFundPromptBuilder(PromptBuilder):
            def _base_rules(self):
                return super()._base_rules() + '''
                Additional rules for hedge fund docs:
                - ERISA fields only apply to US pension/benefit plans
                '''
    """

    def __init__(self, version: str = "v1"):
        self.version = version

    def build(
        self,
        form_keys: dict,
        meta_form_keys: dict,
        mandatory_flat: dict,
        investor_type: str,
        conversation_history: str,
        user_input: str,
    ) -> str:
        return (
            self._base_rules()
            + self._schema_section(form_keys)
            + self._boolean_section(meta_form_keys)
            + self._mandatory_section(mandatory_flat)
            + self._context_section(investor_type, conversation_history, user_input)
        )

    # ------------------------------------------------------------------

    def _base_rules(self) -> str:
        return """You are a precise data extraction assistant for investor onboarding forms.

EXTRACTION RULES:
1. Extract ONLY information the user has explicitly stated. Do NOT hallucinate or infer.
2. Boolean fields use 3-state system: true (confirmed yes), false (confirmed no), null (not mentioned).
3. For addresses: if the user gives a full address, populate all sub-fields you can.
4. For phone numbers: preserve the full number including country code if given.
5. Return ONLY a JSON object — no preamble, no explanation, no markdown fences.
6. Include ONLY fields where you extracted a value. Omit fields not mentioned.
7. Field keys must EXACTLY match the schema keys provided — no inventing new keys.
8. If the user says "skip" or "don't have" for a field, do NOT include that field.
9. Geographic inference: if country is clear from context (e.g., "NYC"), infer "USA".
10. Negative responses ("no", "n/a", "none") for text fields -> omit the field.

"""

    def _schema_section(self, form_keys: dict) -> str:
        schema_keys = list(form_keys.keys())
        return f"""AVAILABLE FIELD KEYS (extract only these):
{json.dumps(schema_keys, indent=2)}

"""

    def _boolean_section(self, meta_form_keys: dict) -> str:
        boolean_fields = self._collect_boolean_fields(meta_form_keys)
        if not boolean_fields:
            return ""
        return f"""BOOLEAN FIELDS (use true/false/null only):
{json.dumps(list(boolean_fields), indent=2)}

"""

    def _mandatory_section(self, mandatory_flat: dict) -> str:
        if not mandatory_flat:
            return ""
        keys = list(mandatory_flat.keys())[:50]
        return f"""MANDATORY FIELDS (prioritise extracting these):
{json.dumps(keys, indent=2)}

"""

    def _context_section(
        self, investor_type: str, conversation_history: str, user_input: str
    ) -> str:
        return f"""INVESTOR TYPE: {investor_type}

CONVERSATION HISTORY:
{conversation_history}

USER'S LATEST MESSAGE:
{user_input}

Respond with a single JSON object of extracted fields only.
"""

    def _collect_boolean_fields(self, meta_form_keys: dict) -> set:
        booleans = set()
        for key, value in meta_form_keys.items():
            if isinstance(value, dict):
                # Flat: {"individual_check": {"type": "boolean"}}
                if value.get("type") == "boolean":
                    booleans.add(key)
                else:
                    # Nested: {"section": {"field": {"type": "boolean"}}}
                    for field, meta in value.items():
                        if isinstance(meta, dict) and meta.get("type") == "boolean":
                            booleans.add(field)
        return booleans
