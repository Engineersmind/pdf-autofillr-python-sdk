"""
Integration tests for the local entrypoint.

Tests the run_session() function end-to-end using temp storage
and a mocked LLM extractor.
"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def local_client(config_path, temp_dir):
    """chatbotClient wired for local entrypoint tests."""
    from chatbot import FormConfig, LocalStorage, chatbotClient

    storage = LocalStorage(
        data_path=str(temp_dir / "entrypoint_data"),
        config_path=config_path,
    )
    form_config = FormConfig.from_directory(config_path)

    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({"full_name": "Bob Test"}, 0.05, "llm"),
    ):
        client = chatbotClient(
            openai_api_key="sk-test",
            storage=storage,
            form_config=form_config,
            pdf_filler=None,
        )
        yield client


def test_run_session_returns_response(local_client):
    from entrypoints.local import run_session

    response, complete, data = run_session(
        user_id="u1",
        session_id="s1",
        message="",
        client=local_client,
    )
    assert isinstance(response, str)
    assert len(response) > 0
    assert isinstance(complete, bool)


def test_run_session_persists_state(local_client, temp_dir):
    from entrypoints.local import run_session

    run_session(user_id="u1", session_id="s2", message="", client=local_client)

    from pathlib import Path

    session_dir = Path(temp_dir) / "entrypoint_data" / "u1" / "sessions" / "s2"
    assert (session_dir / "session_state.json").exists()


def test_run_session_with_pdf_path(local_client, temp_dir):
    """pdf_path should be accepted without error even if file doesn't exist
    (file existence is validated by the PDF workflow, not the entrypoint)."""
    from entrypoints.local import run_session

    response, complete, data = run_session(
        user_id="u1",
        session_id="s3",
        message="",
        pdf_path="/tmp/blank_form.pdf",  # doesn't need to exist for this test
        client=local_client,
    )
    assert isinstance(response, str)


def test_run_session_multiple_turns(local_client):
    from entrypoints.local import run_session

    uid, sid = "multi_u", "multi_s"
    r1, c1, d1 = run_session(uid, sid, "", client=local_client)
    assert not c1  # session should not complete on first message

    r2, c2, d2 = run_session(uid, sid, "1", client=local_client)
    assert isinstance(r2, str)
