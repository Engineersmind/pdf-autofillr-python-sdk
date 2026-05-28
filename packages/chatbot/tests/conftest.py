"""
Shared pytest fixtures for the chatbot module test suite.

Provides:
    - temp_dir          — isolated tmp directory
    - config_path       — temp dir populated with minimal JSON config files
    - local_storage     — LocalStorage wired to temp_dir
    - minimal_client    — chatbotClient with mocked LLM, no PDF filler
    - sample_session    — ready-to-use session dict at INIT state
    - investor_types    — all 10 investor type strings
    - mock_openai       — patches LLMExtractor so no real API calls happen
    - fastapi_client    — TestClient for the FastAPI api_server app
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# Ensure module root is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
os.environ.setdefault("chatbot_STORAGE", "local")
os.environ.setdefault("chatbot_PDF_FILLER", "none")


# ─────────────────────────────────────────────────────────────────────────────
# Minimal form-config JSON fixtures
# ─────────────────────────────────────────────────────────────────────────────

MINIMAL_FORM_KEYS = {
    "full_name": None,
    "email": None,
    "address_registered": {
        "address_registered_country_id": None,
        "address_registered_city_id": None,
    },
}

MINIMAL_META_FORM_KEYS = {
    "full_name": {"type": "text", "label": "Full Name"},
    "email": {"type": "text", "label": "Email"},
    "address_registered": {
        "address_registered_country_id": {"type": "text", "label": "Country"},
        "address_registered_city_id": {"type": "text", "label": "City"},
    },
}

MINIMAL_MANDATORY = {
    "full_name": None,
    "email": None,
    "address_registered.address_registered_country_id": None,
}

MINIMAL_FIELD_QUESTIONS = {
    "full_name": "What is your full legal name?",
    "email": "What is your email address?",
    "address_registered.address_registered_country_id": "What country are you registered in?",
}

MINIMAL_FORM_KEYS_LABEL = {
    "full_name": "Full Name",
    "email": "Email Address",
    "address_registered.address_registered_country_id": "Country",
}

MINIMAL_INDIVIDUAL_KEYS = {
    "full_name": None,
    "email": None,
}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_dir():
    """Isolated temporary directory, cleaned up after each test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def config_path(temp_dir):
    """Temporary config directory populated with minimal JSON files."""
    cfg = temp_dir / "configs"
    cfg.mkdir()
    investor_type_dir = cfg / "global_investor_type_keys"
    investor_type_dir.mkdir()

    (cfg / "form_keys.json").write_text(json.dumps(MINIMAL_FORM_KEYS))
    (cfg / "meta_form_keys.json").write_text(json.dumps(MINIMAL_META_FORM_KEYS))
    (cfg / "mandatory.json").write_text(json.dumps(MINIMAL_MANDATORY))
    (cfg / "field_questions.json").write_text(json.dumps(MINIMAL_FIELD_QUESTIONS))
    (cfg / "form_keys_label.json").write_text(json.dumps(MINIMAL_FORM_KEYS_LABEL))
    (investor_type_dir / "form_keys_individual.json").write_text(
        json.dumps(MINIMAL_INDIVIDUAL_KEYS)
    )

    return str(cfg)


@pytest.fixture
def local_storage(temp_dir):
    """LocalStorage backed by temp_dir."""
    from chatbot.storage.local_storage import LocalStorage

    return LocalStorage(
        data_path=str(temp_dir / "data"),
        config_path=str(temp_dir / "configs"),
    )


@pytest.fixture
def form_config(config_path):
    """FormConfig loaded from minimal config fixtures."""
    from chatbot.config.form_config import FormConfig

    return FormConfig.from_directory(config_path)


@pytest.fixture
def mock_openai():
    """
    Patch LLMExtractor so it returns a predictable extraction dict
    without making real OpenAI calls.
    """
    fake_response = {"full_name": "Alice Test", "email": "alice@test.com"}
    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=(fake_response, 0.05, "llm"),
    ):
        yield fake_response


@pytest.fixture
def minimal_client(local_storage, form_config, mock_openai):
    """
    chatbotClient with no PDF filler and mocked LLM.
    Safe to use in unit tests — never calls OpenAI or touches the filesystem
    outside temp_dir.
    """
    from chatbot import chatbotClient

    return chatbotClient(
        openai_api_key="sk-test-key",
        storage=local_storage,
        form_config=form_config,
        pdf_filler=None,
    )


@pytest.fixture
def user_id():
    return "test_user_001"


@pytest.fixture
def session_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_session(user_id, session_id):
    """A minimal session dict at INIT state."""
    from chatbot.core.states import State

    return {
        "user_id": user_id,
        "session_id": session_id,
        "state": State.INIT.value,
        "investor_type": None,
        "live_fill_flat": {},
        "mandatory_flat": {},
        "fields_being_asked": [],
        "current_group": None,
        "pdf_path": None,
        "pdf_doc_id": None,
        "pdf_workflow_status": None,
        "conversation_log": [],
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.fixture
def investor_types():
    """All 10 investor type strings from states.py."""
    from chatbot.core.states import INVESTOR_TYPES

    return list(INVESTOR_TYPES)


@pytest.fixture
def fastapi_client(config_path, temp_dir):
    """
    httpx TestClient for the FastAPI api_server app.
    Uses temp_dir for storage.
    """

    from fastapi.testclient import TestClient

    os.environ["chatbot_CONFIG_PATH"] = config_path
    os.environ["chatbot_DATA_PATH"] = str(temp_dir / "api_data")
    os.environ["chatbot_PDF_FILLER"] = "none"

    # Re-import api_server fresh with patched env
    import api_server

    # Reset the singleton so it picks up new config_path
    api_server._client = None

    with patch(
        "chatbot.extraction.llm_extractor.LLMExtractor.extract",
        return_value=({"full_name": "API Test User"}, 0.1, "llm"),
    ):
        with TestClient(api_server.app) as tc:
            yield tc


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def make_session(
    user_id: str, session_id: str, state: str = "INIT", **kwargs
) -> dict[str, Any]:
    """Convenience factory for building test session dicts."""
    base: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "state": state,
        "investor_type": None,
        "live_fill_flat": {},
        "mandatory_flat": {},
        "fields_being_asked": [],
        "current_group": None,
        "pdf_path": None,
        "conversation_log": [],
    }
    base.update(kwargs)
    return base


def create_minimal_pdf(path: str) -> None:
    """Write a minimal valid-looking PDF header to path (for path-existence tests)."""
    Path(path).write_bytes(b"%PDF-1.4\n%%EOF\n")


def write_json(path: str, data: Any) -> None:
    Path(path).write_text(json.dumps(data, indent=2))
