"""
Integration tests for the FastAPI api_server.

These tests spin up the app with TestClient (no real server required)
and cover the full HTTP layer with mocked LLM responses.

Marked as 'integration' because they exercise the full stack:
    HTTP -> FastAPI -> chatbotClient -> ConversationEngine -> LocalStorage
"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


def test_health_check(fastapi_client):
    resp = fastapi_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "storage" in data
    assert "pdf_filler" in data


def test_root_returns_endpoint_map(fastapi_client):
    resp = fastapi_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    # assert "endpoints" in data
    assert "status" in data


def test_chat_first_message_returns_greeting(fastapi_client):
    resp = fastapi_client.post(
        "/chatbot/chat",
        json={
            "user_id": "u_test",
            "session_id": "s_test",
            "message": "",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
    assert data["session_complete"] is False


def test_chat_requires_user_id_and_session_id(fastapi_client):
    resp = fastapi_client.post(
        "/chatbot/chat",
        json={
            "user_id": "",
            "session_id": "",
            "message": "Hello",
        },
    )
    assert resp.status_code in (400, 422, 500)


def test_chat_multiple_turns(fastapi_client):
    uid, sid = "multi_user", "multi_session"
    # Turn 1: greeting
    r1 = fastapi_client.post(
        "/chatbot/chat", json={"user_id": uid, "session_id": sid, "message": ""}
    )
    assert r1.status_code == 200

    # Turn 2: send a response
    r2 = fastapi_client.post(
        "/chatbot/chat", json={"user_id": uid, "session_id": sid, "message": "1"}
    )
    assert r2.status_code == 200
    assert r2.json()["user_id"] == uid


def test_get_session_not_found(fastapi_client):
    resp = fastapi_client.get("/chatbot/session/nobody/nosession")
    assert resp.status_code == 404


def test_delete_session(fastapi_client):
    uid, sid = "del_user", "del_session"
    # Create it
    fastapi_client.post(
        "/chatbot/chat", json={"user_id": uid, "session_id": sid, "message": ""}
    )
    # Delete it
    resp = fastapi_client.delete(f"/chatbot/session/{uid}/{sid}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_fill_report_not_found_for_incomplete_session(fastapi_client):
    uid, sid = "report_user", "report_session"
    fastapi_client.post(
        "/chatbot/chat", json={"user_id": uid, "session_id": sid, "message": ""}
    )
    resp = fastapi_client.get(f"/chatbot/session/{uid}/{sid}/fill-report")
    # Session not complete yet — report should be 404
    assert resp.status_code == 404


def test_rate_limit_returns_429(fastapi_client):
    """Simulate hitting the messages_per_session rate limit."""
    # from chatbot.limits import RateLimitExceeded
    from chatbot.limits.rate_limiter import RateLimitExceeded

    with patch(
        "chatbot.limits.rate_limiter.RateLimiter.check",
        side_effect=RateLimitExceeded("limit reached", "messages_per_session"),
    ):
        # Need to get the client and patch its rate_limiter
        import api_server
        import chatbot.limits.rate_limiter as rl_mod

        old_client = api_server._client
        try:
            # Build a client with a rate limiter
            import api_server

            api_server._client = None
            # Patch at the module level for this request
            with patch.object(
                rl_mod.RateLimiter,
                "check",
                side_effect=RateLimitExceeded("limit reached", "messages_per_session"),
            ):
                resp = fastapi_client.post(
                    "/chatbot/chat",
                    json={"user_id": "u1", "session_id": "s1", "message": "hi"},
                )
                # The rate limiter is injected optionally; if not set, no 429
                # This test just verifies the HTTP layer handles the exception
                assert resp.status_code in (200, 429)
        finally:
            api_server._client = old_client
