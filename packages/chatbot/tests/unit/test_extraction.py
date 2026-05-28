"""
Unit tests for extraction layer:
    - FallbackExtractor: regex-based email/phone/zip extraction
    - PromptBuilder: prompt generation
    - Extractor: LLM-first with fallback
"""

from unittest.mock import patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# FallbackExtractor
# ─────────────────────────────────────────────────────────────────────────────


class TestFallbackExtractor:
    @pytest.fixture
    def extractor(self):
        from chatbot.extraction.fallback_extractor import FallbackExtractor

        return FallbackExtractor()

    def test_extracts_email(self, extractor):
        live = {"email": None}
        result = extractor.extract("Please contact alice@example.com", live)
        assert result.get("email") == "alice@example.com"

    def test_extracts_phone(self, extractor):
        live = {"phone_number": None}
        result = extractor.extract("My phone is +1 212 555 1234", live)
        assert "phone_number" in result

    def test_extracts_zip(self, extractor):
        live = {"zip_code": None}
        result = extractor.extract("I live in 10001", live)
        assert result.get("zip_code") == "10001"

    def test_no_match_returns_empty(self, extractor):
        live = {"full_name": None}
        result = extractor.extract("My name is Alice Johnson", live)
        assert result == {}

    def test_email_not_matched_to_non_email_field(self, extractor):
        live = {"full_name": None}
        result = extractor.extract("alice@example.com", live)
        assert "full_name" not in result


# ─────────────────────────────────────────────────────────────────────────────
# PromptBuilder
# ─────────────────────────────────────────────────────────────────────────────


class TestPromptBuilder:
    @pytest.fixture
    def builder(self):
        from chatbot.extraction.prompt_builder import PromptBuilder

        return PromptBuilder()

    def test_build_returns_string(self, builder):
        prompt = builder.build(
            form_keys={"full_name": None, "email": None},
            meta_form_keys={},
            mandatory_flat={"full_name": None},
            investor_type="Individual",
            conversation_history="",
            user_input="Alice Johnson",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_build_includes_field_keys(self, builder):
        prompt = builder.build(
            form_keys={"full_name": None, "email": None},
            meta_form_keys={},
            mandatory_flat={},
            investor_type="Individual",
            conversation_history="",
            user_input="test",
        )
        assert "full_name" in prompt
        assert "email" in prompt

    def test_build_includes_investor_type(self, builder):
        prompt = builder.build(
            form_keys={},
            meta_form_keys={},
            mandatory_flat={},
            investor_type="Corporation",
            conversation_history="",
            user_input="test",
        )
        assert "Corporation" in prompt

    def test_build_includes_boolean_fields(self, builder):
        meta = {"individual_check": {"type": "boolean"}}
        prompt = builder.build(
            form_keys={},
            meta_form_keys=meta,
            mandatory_flat={},
            investor_type="Individual",
            conversation_history="",
            user_input="test",
        )
        assert "individual_check" in prompt


# ─────────────────────────────────────────────────────────────────────────────
# Extractor (integration of LLM + fallback)
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractor:
    @pytest.fixture
    def extractor(self):
        from chatbot.extraction.extractor import Extractor

        return Extractor(openai_api_key="sk-test")

    # def test_llm_success_returns_llm_result(self, extractor):
    #     with patch(
    #         "chatbot.extraction.extractor.LLMExtractor.extract",
    #         return_value=({"full_name": "Alice"}, 0.05, "llm"),
    #     ):
    #         result, latency, method = extractor.extract(
    #             user_input="Alice Johnson",
    #             conversation_history="",
    #             live_fill_flat={"full_name": None},
    #             meta_form_keys={},
    #             investor_type="Individual",
    #         )
    #     assert result == {"full_name": "Alice"}
    #     assert method == "llm"

    def test_llm_success_returns_llm_result(self, extractor):
        with patch(
            "chatbot.extraction.extractor.LLMExtractor.extract",
            return_value=({"full_name": "Alice"}, 0.05, "llm"),
        ):
            result, latency, method = extractor.extract(
                user_input="Alice Johnson",
                conversation_history="",
                live_fill_flat={"full_name": None},
                meta_form_keys={},
                investor_type="Individual",
            )
            assert result == {
                "full_name": "Alice"
            }  # <-- move assert INSIDE the with block
            assert method == "llm"

    def test_fallback_used_when_llm_empty(self, extractor):
        with patch(
            "chatbot.extraction.extractor.LLMExtractor.extract",
            return_value=({}, 0.05, "llm"),
        ):
            result, latency, method = extractor.extract(
                user_input="alice@test.com",
                conversation_history="",
                live_fill_flat={"email": None},
                meta_form_keys={},
                investor_type="Individual",
            )
        assert method == "fallback"
        assert "email" in result

    def test_fallback_used_when_llm_raises(self, extractor):
        with patch(
            "chatbot.extraction.extractor.LLMExtractor.extract",
            side_effect=Exception("OpenAI error"),
        ):
            result, latency, method = extractor.extract(
                user_input="alice@test.com",
                conversation_history="",
                live_fill_flat={"email": None},
                meta_form_keys={},
                investor_type="Individual",
            )
        assert method == "fallback"
