# chatbot/handlers/update_existing_handler.py
"""
Handles UPDATE_EXISTING_PROMPT state.

Asked when the user has data from a previous session.
"Would you like to use it to pre-fill this form? (yes / no)"
"""
from __future__ import annotations
from typing import Optional, Tuple
from chatbot.core.states import State, INVESTOR_TYPES
from chatbot.handlers.base_handler import BaseHandler
from chatbot.logging.debug_logger import DebugLogger
from chatbot.utils.intent_detection import is_affirmative, is_negative


class UpdateExistingHandler(BaseHandler):
    """
    User is asked whether to load their previously saved profile data.

    - yes  -> keep _pending_existing_data in session, go to investor type select
    - no   -> clear it, go to investor type select
    - anything else -> re-prompt
    """

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.UPDATE_EXISTING_PROMPT.value

        if is_affirmative(user_input):
            # Data stays in session["_pending_existing_data"].
            # InvestorTypeHandler will merge it after type is confirmed.
            debug and debug.log("update_existing", "User accepted existing data")
            return self._show_investor_type_menu(session, user_input, state)

        if is_negative(user_input):
            session.pop("_pending_existing_data", None)
            debug and debug.log("update_existing", "User declined existing data")
            return self._show_investor_type_menu(session, user_input, state)

        # Unrecognised — re-ask
        msg = (
            "I didn't catch that. Would you like to use your saved information "
            "to pre-fill this form? Please reply yes or no."
        )
        self._log_turn(session, user_input, msg, state)
        return msg, State.UPDATE_EXISTING_PROMPT

    def _show_investor_type_menu(self, session, user_input, state):
        lines = ["Please select your investor type:\n"]
        for i, t in enumerate(INVESTOR_TYPES, 1):
            lines.append(f"  {i}. {t}")
        msg = "\n".join(lines)
        self._log_turn(session, user_input, msg, state)
        return msg, State.INVESTOR_TYPE_SELECT