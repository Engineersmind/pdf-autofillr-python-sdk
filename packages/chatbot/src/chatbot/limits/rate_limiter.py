"""
Stub implementation of RateLimiter.
Only used by tests — not wired into the chatbot application.
"""

from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    messages_per_session: int = 100
    sessions_per_user_per_day: int = 50
    llm_calls_per_session: int = 200


class RateLimitExceeded(Exception):
    def __init__(self, message: str = "", limit_type: str = ""):
        self.limit_type = limit_type
        super().__init__(message or f"Rate limit exceeded: {limit_type}")


class RateLimiter:
    def __init__(self, config: RateLimitConfig | None = None, backend: str = "local"):
        self.config = config or RateLimitConfig()
        self._session_messages: dict[str, int] = {}
        self._session_llm: dict[str, int] = {}
        self._user_seen_sessions: dict[str, set[str]] = {}

    def check(self, user_id: str, session_id: str) -> None:
        if (
            self._session_messages.get(session_id, 0)
            >= self.config.messages_per_session
        ):
            raise RateLimitExceeded(limit_type="messages_per_session")

        if self._session_llm.get(session_id, 0) >= self.config.llm_calls_per_session:
            raise RateLimitExceeded(limit_type="llm_calls_per_session")

        seen = self._user_seen_sessions.get(user_id, set())
        if (
            session_id not in seen
            and len(seen) >= self.config.sessions_per_user_per_day
        ):
            raise RateLimitExceeded(limit_type="sessions_per_user_per_day")

        # Register session as seen for this user on successful check
        self._user_seen_sessions.setdefault(user_id, set()).add(session_id)

    def increment_message(self, session_id: str) -> None:
        self._session_messages[session_id] = (
            self._session_messages.get(session_id, 0) + 1
        )

    def increment_llm(self, session_id: str) -> None:
        self._session_llm[session_id] = self._session_llm.get(session_id, 0) + 1
