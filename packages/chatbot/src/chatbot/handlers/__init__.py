# chatbot/handlers/init_handler.py
"""
Handles INIT and SAVED_INFO_CHECK states.
"""
from __future__ import annotations
from typing import Optional, Tuple
from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.logging.debug_logger import DebugLogger
from chatbot.utils.intent_detection import is_affirmative, is_negative


class InitHandler(BaseHandler):
    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = session.get("state", State.INIT.value)

        # First ever call — send greeting with yes/no gate, stay in INIT
        if state == State.INIT.value and not session.get("conversation_log"):
            bot_name = self.settings.bot_name
            greeting = (
                f"Hi there, I'm {bot_name}, your Finance Form Assistant.\n"
                "I can help you fill out your information in PDF documents quickly and accurately.\n"
                "Would you like to get started now? (yes/no):"
            )
            self._log_turn(session, user_input, greeting, state)
            return greeting, State.INIT

        # INIT with conversation log = waiting for yes/no response to greeting
        if state == State.INIT.value and session.get("conversation_log"):
            if is_negative(user_input):
                msg = "Alright! Feel free to come back whenever you're ready. Goodbye!"
                self._log_turn(session, user_input, msg, state)
                return msg, State.COMPLETE
            # Any affirmative or unclear -> proceed to saved info check
            return self._proceed_to_saved_info(session, user_input, state, user_id)

        # SAVED_INFO_CHECK state
        if state == State.SAVED_INFO_CHECK.value:
            return self._proceed_to_saved_info(session, user_input, state, user_id)

        return self._show_investor_type_menu(session, user_input, state)

    def _proceed_to_saved_info(self, session, user_input, state, user_id):
        existing = self.storage.get_user_integrated_info(user_id)
        if existing:
            msg = (
                "Welcome back! I have some information from your previous session. "
                "Would you like to use it to pre-fill this form? (yes / no)"
            )
            session["_pending_existing_data"] = existing
            self._log_turn(session, user_input, msg, state)
            return msg, State.UPDATE_EXISTING_PROMPT

        # No existing data — go straight to investor type selection
        return self._show_investor_type_menu(session, user_input, state)

    def _show_investor_type_menu(self, session, user_input, state):
        from chatbot.core.states import INVESTOR_TYPES
        lines = ["Could you tell me what type of investor category best describes you?\n"]
        for i, t in enumerate(INVESTOR_TYPES, 1):
            lines.append(f"{i}. {t}")
        lines.append("\nEnter Investor Type (number or name):")
        msg = "\n".join(lines)
        self._log_turn(session, user_input, msg, state)
        return msg, State.INVESTOR_TYPE_SELECT