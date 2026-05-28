# chatbot/handlers/continue_prompt_handler.py
"""
Handles CONTINUE_PROMPT state.

A lightweight "do you want to keep going?" checkpoint, used when
the conversation has been going for many turns or after a natural
pause. The user can:
  - yes / continue -> go back to DATA_COLLECTION
  - no / done / exit -> go to OPTIONAL_FIELDS_PROMPT to wrap up
"""

from __future__ import annotations

from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.intent_detection import is_affirmative, is_exit_intent, is_negative


class ContinuePromptHandler(BaseHandler):
    """
    Simple yes/no checkpoint — keeps the conversation from going stale.

    Session keys read:  (none — purely intent-based)
    Session keys set:   (none)
    """

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.CONTINUE_PROMPT.value

        if is_negative(user_input) or is_exit_intent(user_input):
            debug and debug.log("continue_prompt", "User wants to wrap up")
            msg = "Understood — let me wrap things up for you."
            self._log_turn(session, user_input, msg, state)
            return msg, State.OPTIONAL_FIELDS_PROMPT

        if is_affirmative(user_input):
            debug and debug.log("continue_prompt", "User wants to continue")
            msg = "Great! Please continue sharing your information."
            self._log_turn(session, user_input, msg, state)
            return msg, State.DATA_COLLECTION

        # Treat any other input as wanting to continue and try to extract from it
        debug and debug.log("continue_prompt", "Ambiguous input — treating as continue")
        msg = "Let's keep going. Please share any remaining details."
        self._log_turn(session, user_input, msg, state)
        return msg, State.DATA_COLLECTION
