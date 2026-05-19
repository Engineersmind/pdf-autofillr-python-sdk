# chatbot/src/chatbot/extraction/llm_extractor.py
"""
LLMExtractor — extracts form field values using any LiteLLM-supported model.

Replaces the previous hardcoded ChatOpenAI / GPT-4o-mini implementation.
Model is configured via CHATBOT_LLM_MODEL in .env.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from chatbot.extraction.llm_client import LLMClient
from chatbot.extraction.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class LLMExtractor:
    """
    Extracts structured form field values using any LiteLLM-supported model.

    Args:
        api_key:        Optional API key. Passed to LLMClient which resolves
                        the right provider key automatically.
        prompt_builder: Optional PromptBuilder subclass for custom prompts.
        model:          Optional model override. Defaults to CHATBOT_LLM_MODEL env var.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_builder=None,
        model: Optional[str] = None,
    ):
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm = LLMClient(model=model, api_key=api_key)

    def extract(
        self,
        user_input: str,
        conversation_history: str,
        live_fill_flat: dict,
        meta_form_keys: dict,
        mandatory_flat: Optional[dict] = None,
        investor_type: Optional[str] = None,
    ) -> tuple:
        """
        Call the configured LLM with the full form schema and return extracted fields.

        Returns:
            (extracted_dict, latency_seconds, method)
        """
        start = time.time()

        prompt = self.prompt_builder.build(
            form_keys=live_fill_flat,
            meta_form_keys=meta_form_keys,
            mandatory_flat=mandatory_flat or {},
            investor_type=investor_type or "Not yet specified",
            conversation_history=conversation_history,
            user_input=user_input,
        )

        raw = self.llm.call(prompt)

        extracted = self._parse_json(raw)
        known_keys = set(live_fill_flat.keys())
        filtered = {k: v for k, v in extracted.items() if k in known_keys}
        latency = time.time() - start

        logger.debug(
            "LLMExtractor: model=%s extracted=%d fields latency=%.2fs",
            self.llm.model, len(filtered), latency,
        )

        return filtered, latency, "llm"

    def _parse_json(self, raw: str) -> dict:
        raw = raw.strip()
        for fence in ("```json", "```"):
            if raw.startswith(fence):
                raw = raw[len(fence):]
        if raw.endswith("```"):
            raw = raw[:-3]
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            logger.warning("LLMExtractor: could not parse JSON from model response")
            return {}
