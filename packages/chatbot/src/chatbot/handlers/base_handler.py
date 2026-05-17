# chatbot/handlers/base_handler.py
"""
BaseHandler — abstract class all state handlers extend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Tuple

from chatbot.core.states import State
from chatbot.logging.debug_logger import DebugLogger

if TYPE_CHECKING:
    from chatbot.core.engine import ConversationEngine


class BaseHandler(ABC):
    """
    Abstract base for all 13 state handlers.

    Each handler receives the full session dict, the user's input,
    and returns (response_text, next_state).
    """

    def __init__(self, engine: "ConversationEngine"):
        self.engine = engine
        self.storage = engine.storage
        self.form_config = engine.form_config
        self.extractor = engine.extractor
        self.settings = engine.settings

    @abstractmethod
    def handle(
        self,
        session: dict,
        user_input: str,
        user_id: str,
        session_id: str,
        debug: Optional[DebugLogger] = None,
    ) -> Tuple[str, State]:
        """
        Process one turn in this state.

        Args:
            session:    Full mutable session dict.
            user_input: Stripped user message.
            user_id:    User identifier.
            session_id: Session identifier.
            debug:      Debug logger (may be None).

        Returns:
            (response_text, next_state)
        """

    # ------------------------------------------------------------------
    # Shared helpers available to all handlers
    # ------------------------------------------------------------------

    def _log_turn(
        self,
        session: dict,
        user_input: str,
        bot_response: str,
        state: str,
    ) -> None:
        session.setdefault("conversation_log", []).append(
            {
                "turn": len(session["conversation_log"]) + 1,
                "state": state,
                "user": user_input,
                "bot": bot_response,
            }
        )

    def _get_greeting(self) -> str:
        return self.settings.greeting

    def _bot_name(self) -> str:
        return self.settings.bot_name
