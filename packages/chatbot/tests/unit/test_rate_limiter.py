"""
Unit tests for RateLimiter.

Covers the Issue 6 fix: daily session counter now correctly increments
exactly once per session_id regardless of how many messages are sent.
"""

import pytest

from chatbot.limits.rate_limiter import RateLimitConfig, RateLimiter, RateLimitExceeded


@pytest.fixture
def cfg():
    return RateLimitConfig(
        messages_per_session=5,
        sessions_per_user_per_day=3,
        llm_calls_per_session=10,
    )


@pytest.fixture
def limiter(cfg):
    return RateLimiter(config=cfg, backend="local")


# ── messages_per_session ──────────────────────────────────────────────


def test_allows_messages_within_limit(limiter):
    for _ in range(5):
        limiter.check("u1", "s1")
        limiter.increment_message("s1")


def test_blocks_messages_over_limit(limiter):
    for _ in range(5):
        limiter.increment_message("s1")
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("u1", "s1")
    assert exc_info.value.limit_type == "messages_per_session"


# ── sessions_per_user_per_day ──────────────────────────────────────────


def test_allows_sessions_within_daily_limit(limiter):
    """Three distinct sessions for the same user should all pass."""
    for sid in ("s1", "s2", "s3"):
        limiter.check("u1", sid)
        limiter.increment_message(sid)


def test_blocks_fourth_session_same_day(limiter):
    """Fourth distinct session for the same user should be blocked."""
    for sid in ("s1", "s2", "s3"):
        limiter.check("u1", sid)
        limiter.increment_message(sid)

    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("u1", "s4")
    assert exc_info.value.limit_type == "sessions_per_user_per_day"


def test_daily_count_not_double_incremented(limiter):
    """
    FIX Issue 6: sending multiple messages in the same session must not
    count as multiple sessions toward the daily limit.

    Before the fix, after the first increment_message() call the session_id
    appeared in _session_turns so `session_id not in _session_turns` was False
    and the daily counter never incremented on turn 2+, breaking the check.
    After the fix with _seen_sessions, this is correct.
    """
    # Session s1: 3 messages — should count as exactly ONE session
    for _ in range(3):
        limiter.check("u1", "s1")
        limiter.increment_message("s1")

    # Sessions s2 and s3 should still be allowed (only 1 of 3 used so far)
    limiter.check("u1", "s2")
    limiter.check("u1", "s3")

    # Session s4 should be blocked (limit is 3)
    with pytest.raises(RateLimitExceeded):
        limiter.check("u1", "s4")


def test_different_users_have_independent_daily_counts(limiter):
    """Each user has their own daily session counter."""
    for sid in ("s1", "s2", "s3"):
        limiter.check("user_a", sid)
        limiter.increment_message(sid)

    # user_b should not be affected by user_a's sessions
    for sid in ("s1", "s2", "s3"):
        limiter.check("user_b", sid)


# ── llm_calls_per_session ─────────────────────────────────────────────


def test_blocks_excess_llm_calls(limiter):
    for _ in range(10):
        limiter.increment_llm("s1")
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("u1", "s1")
    assert exc_info.value.limit_type == "llm_calls_per_session"


# ── defaults ───────────────────────────────────────────────────────────


def test_default_config():
    limiter = RateLimiter(backend="local")
    # Should not raise with default limits
    limiter.check("u1", "s1")
    limiter.increment_message("s1")
    limiter.increment_llm("s1")
