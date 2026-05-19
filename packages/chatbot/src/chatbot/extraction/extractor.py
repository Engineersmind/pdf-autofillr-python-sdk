# chatbot/src/chatbot/extraction/extractor.py
"""
Extractor — tries LLM extraction, falls back to regex if it fails.
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from chatbot.extraction.llm_extractor import LLMExtractor
from chatbot.extraction.fallback_extractor import FallbackExtractor

logger = logging.getLogger(__name__)


class Extractor:
    """
    Unified extraction interface.

    Tries LLM first. If the LLM call raises or returns empty,
    falls back to FallbackExtractor (regex-based, no network call).

    Args:
        api_key:        API key passed through to LLMExtractor / LLMClient.
                        Optional — LLMClient reads CHATBOT_LLM_API_KEY from env if unset.
        prompt_builder: Optional PromptBuilder subclass.
        model:          Optional model override.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        prompt_builder=None,
        model: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        api_key = api_key or openai_api_key
        self.llm = LLMExtractor(
            api_key=api_key,
            prompt_builder=prompt_builder,
            model=model,
        )
        self.fallback = FallbackExtractor()

    def extract(
        self,
        user_input: str,
        conversation_history: str,
        live_fill_flat: dict,
        meta_form_keys: dict,
        mandatory_flat: Optional[dict] = None,
        investor_type: Optional[str] = None,
    ) -> Tuple[dict, float, str]:
        """
        Extract structured field values from user input.

        Returns:
            (extracted_dict, latency_seconds, method)
            method is either "llm" or "fallback"
        """
        start = time.time()

        try:
            result, latency, method = self.llm.extract(
                user_input=user_input,
                conversation_history=conversation_history,
                live_fill_flat=live_fill_flat,
                meta_form_keys=meta_form_keys,
                mandatory_flat=mandatory_flat,
                investor_type=investor_type,
            )
            if result:
                return result, latency, method

        except Exception as e:
            logger.warning("LLM extraction failed, using fallback: %s", e)

        result = self.fallback.extract(user_input=user_input, live_fill_flat=live_fill_flat)
        latency = time.time() - start
        return result, latency, "fallback"
