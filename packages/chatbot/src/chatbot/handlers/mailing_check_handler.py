# chatbot/handlers/mailing_check_handler.py
"""
Handles MAILING_ADDRESS_CHECK state.

Asks the user whether their mailing address is the same as their
registered address. If yes, copies all registered -> mailing fields.
If no, returns to DATA_COLLECTION for the user to provide mailing details.
"""
from __future__ import annotations
from typing import Optional, Tuple

from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.logging.debug_logger import DebugLogger
from chatbot.utils.address_utils import copy_registered_to_mailing
from chatbot.utils.intent_detection import is_affirmative, is_negative


class MailingCheckHandler(BaseHandler):
    """
    Session keys read:   live_fill_flat
    Session keys set:    live_fill_flat (mailing fields), _mailing_checked
    """

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.MAILING_ADDRESS_CHECK.value
        live_fill = session.get("live_fill_flat", {})

        if is_affirmative(user_input):
            # Copy registered -> mailing
            copied = copy_registered_to_mailing(live_fill)
            session["live_fill_flat"] = live_fill
            session["_mailing_checked"] = True

            debug and debug.log(
                "mailing_check",
                f"Mailing = registered. Copied {len(copied)} fields.",
                data={"copied_keys": list(copied.keys())},
            )

            msg = "Got it — I've used your registered address as your mailing address."
            self._log_turn(session, user_input, msg, state)
            return msg, State.DATA_COLLECTION

        if is_negative(user_input):
            session["_mailing_checked"] = True
            debug and debug.log("mailing_check", "User will provide separate mailing address")

            # Build a prompt listing the mailing address fields needed
            mailing_keys = [k for k in live_fill if "address_mailing" in k]
            if mailing_keys:
                lines = ["Please provide your mailing address:\n"]
                for key in mailing_keys:
                    label = self.form_config.get_label(key)
                    question = self.form_config.get_question(key)
                    lines.append(f"  • {question or label}")
                msg = "\n".join(lines)
            else:
                msg = "Please provide your mailing address (street, city, state, zip, country)."

            self._log_turn(session, user_input, msg, state)
            return msg, State.DATA_COLLECTION

        # Unrecognised response — re-ask
        msg = (
            "Is your mailing address the same as your registered address? "
            "Please reply yes or no."
        )
        self._log_turn(session, user_input, msg, state)
        return msg, State.MAILING_ADDRESS_CHECK