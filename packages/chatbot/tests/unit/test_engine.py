"""
Unit tests for ConversationEngine.

Covers Issue 8 fix: conversation_log is persisted via save_conversation_log
after each turn (not just embedded in session_state.json).
"""

from unittest.mock import patch

import pytest


@pytest.fixture
def engine(local_storage, form_config):
    """ConversationEngine with mocked LLM."""
    from chatbot.core.engine import ConversationEngine
    from chatbot.telemetry.collector import TelemetryCollector

    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({"full_name": "Alice"}, 0.1, "llm"),
    ):
        engine = ConversationEngine(
            storage=local_storage,
            form_config=form_config,
            openai_api_key="sk-test",
            pdf_filler=None,
            telemetry=TelemetryCollector(config=None),
        )
        yield engine


def test_process_message_returns_string_and_bool(engine, user_id, session_id):
    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({}, 0.1, "llm"),
    ):
        response, complete = engine.process_message(user_id, session_id, "")
    assert isinstance(response, str)
    assert isinstance(complete, bool)


def test_process_message_saves_session_state(
    engine, local_storage, user_id, session_id
):
    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({}, 0.1, "llm"),
    ):
        engine.process_message(user_id, session_id, "")
    state = local_storage.get_session_state(user_id, session_id)
    assert state is not None
    assert "state" in state


def test_process_message_saves_conversation_log(
    engine, local_storage, user_id, session_id
):
    """
    FIX Issue 8: conversation_log.json must be written independently of
    session_state.json after each turn.
    """
    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({}, 0.1, "llm"),
    ):
        engine.process_message(user_id, session_id, "")

    # Verify save_conversation_log was called — check via the storage file
    from pathlib import Path

    session_dir = Path(local_storage.data_path) / user_id / "sessions" / session_id
    log_file = session_dir / "conversation_log.json"
    assert log_file.exists(), (
        "conversation_log.json not written — save_conversation_log() "
        "is still not being called in engine.process_message()"
    )


def test_multiple_turns_accumulate_log(engine, local_storage, user_id, session_id):
    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({}, 0.1, "llm"),
    ):
        engine.process_message(user_id, session_id, "")
        engine.process_message(user_id, session_id, "hello")

    state = local_storage.get_session_state(user_id, session_id)
    assert len(state.get("conversation_log", [])) >= 1


def test_state_transitions_on_each_turn(engine, local_storage, user_id, session_id):
    from chatbot.core.states import State

    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({}, 0.1, "llm"),
    ):
        # First turn from INIT -> sends greeting and stays in INIT (waiting for yes/no)
        engine.process_message(user_id, session_id, "")
        state = local_storage.get_session_state(user_id, session_id)
        assert state["state"] == State.INIT.value  # stays INIT until user says yes

        # Second turn: user says "yes" -> should move to INVESTOR_TYPE_SELECT (no saved data)
        engine.process_message(user_id, session_id, "yes")
        state = local_storage.get_session_state(user_id, session_id)
        assert state["state"] == State.INVESTOR_TYPE_SELECT.value
