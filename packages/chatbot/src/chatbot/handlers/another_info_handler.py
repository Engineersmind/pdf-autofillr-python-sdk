# # chatbot/handlers/another_info_handler.py
# """
# Handles ANOTHER_INFO_PROMPT state.

# Mid-collection yes/no checkpoint after every DATA_COLLECTION turn.

#   yes  -> "Alright! Please enter details..." -> DATA_COLLECTION
#   no   -> delegate directly to MissingFieldsHandler (no intermediate message)
#   free-form text -> extract, loop back
# """
# from __future__ import annotations

# from chatbot.core.states import State
# from chatbot.handlers.base_handler import BaseHandler
# from chatbot.utils.intent_detection import is_affirmative, is_negative, is_exit_intent


# class AnotherInfoHandler(BaseHandler):

#     def handle(self, session, user_input, user_id, session_id, debug=None):
#         state = State.ANOTHER_INFO_PROMPT.value
#         live_fill = session.get("live_fill_flat", {})
#         mandatory_flat = session.get("mandatory_flat", {})
#         investor_type = session.get("investor_type", "")

#         if is_exit_intent(user_input):
#             msg = "Session ended. Your progress has been saved. Goodbye!"
#             self._log_turn(session, user_input, msg, state)
#             return msg, State.COMPLETE

#         if is_affirmative(user_input):
#             debug and debug.log("another_info", "User wants to add more info")
#             msg = "Alright! Please enter details in the chat whenever you're ready."
#             self._log_turn(session, user_input, msg, state)
#             return msg, State.DATA_COLLECTION

#         if is_negative(user_input):
#             debug and debug.log("another_info", "User said no — delegating to MissingFieldsHandler")
#             # Delegate directly to MissingFieldsHandler — no intermediate message shown
#             from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
#             handler = MissingFieldsHandler(self.engine)
#             return handler.handle(session, user_input, user_id, session_id, debug)

#         # Free-form text — try to extract additional data then ask again
#         extracted, _, _ = self.extractor.extract(
#             user_input=user_input,
#             conversation_history=self._build_history(session),
#             live_fill_flat=live_fill,
#             meta_form_keys=self.form_config.meta_form_keys,
#             mandatory_flat=mandatory_flat,
#             investor_type=investor_type,
#         )

#         if extracted:
#             for key, value in extracted.items():
#                 if key in live_fill and value not in (None, ""):
#                     live_fill[key] = value
#             session["live_fill_flat"] = live_fill
#             debug and debug.log(
#                 "another_info",
#                 f"Extracted {len(extracted)} fields from free-form",
#                 data={"fields": list(extracted.keys())},
#             )

#         msg = "Do you have any other information you'd like to provide? (yes/no):"
#         self._log_turn(session, user_input, msg, state)
#         return msg, State.ANOTHER_INFO_PROMPT

#     def _build_history(self, session: dict) -> str:
#         log = session.get("conversation_log", [])
#         lines = []
#         for entry in log[-4:]:
#             lines.append(f"User: {entry.get('user', '')}")
#             lines.append(f"Bot: {entry.get('bot', '')}")
#         return "\n".join(lines)
























# chatbot/handlers/another_info_handler.py
from __future__ import annotations
from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.intent_detection import is_affirmative, is_negative, is_exit_intent
from chatbot.utils.field_utils import format_field_name


class AnotherInfoHandler(BaseHandler):

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.ANOTHER_INFO_PROMPT.value
        live_fill = session.get("live_fill_flat", {})
        mandatory_flat = session.get("mandatory_flat", {})
        investor_type = session.get("investor_type", "")

        if is_exit_intent(user_input):
            msg = "Session ended. Your progress has been saved. Goodbye!"
            self._log_turn(session, user_input, msg, state)
            return msg, State.COMPLETE

        if is_affirmative(user_input):
            debug and debug.log("another_info", "User wants to add more info")
            msg = "Alright! Please enter details in the chat whenever you're ready."
            self._log_turn(session, user_input, msg, state)
            return msg, State.DATA_COLLECTION

        if is_negative(user_input):
            debug and debug.log("another_info", "User said no — checking missing fields")
            from chatbot.handlers.missing_fields_handler import (
                MissingFieldsHandler, SINGLE_BOOLEAN_MANDATORY, LEGITIMATE_BOOLEAN_GROUPS
            )
            handler = MissingFieldsHandler(self.engine)
            text_missing = handler._get_missing_text(live_fill, mandatory_flat)

            # Check unanswered boolean groups
            missing_bool_groups = []
            for group_name in LEGITIMATE_BOOLEAN_GROUPS:
                fields = [k for k in mandatory_flat if k.startswith(f"{group_name}.") and live_fill.get(k) is None]
                if fields and not any(live_fill.get(f) in (True, False) for f in fields):
                    missing_bool_groups.append(group_name)

            if text_missing or missing_bool_groups:
                grouped_labels = handler._get_grouped_missing_labels(text_missing)
                for group_name in missing_bool_groups:
                    label = handler.SECTION_LABELS.get(group_name) or format_field_name(group_name)
                    if label not in grouped_labels:
                        grouped_labels.append(label)

                lines = ["Okay.\nIt appears that some mandatory information is missing, as listed below.\n"]
                for i, label in enumerate(grouped_labels, 1):
                    lines.append(f"{i}. {label}")
                lines.append("\nWould you like to provide them now?")
                msg = "\n".join(lines)
                self._log_turn(session, user_input, msg, state)
                session["_after_missing_list"] = True
                return msg, State.DATA_COLLECTION
            else:
                msg = "All required information for the selected investor has been received. Would you like to include additional optional information?(yes/no):"
                self._log_turn(session, user_input, msg, state)
                return msg, State.OPTIONAL_FIELDS_PROMPT

        # Free-form text — extract and ask again
        extracted, _, _ = self.extractor.extract(
            user_input=user_input,
            conversation_history=self._build_history(session),
            live_fill_flat=live_fill,
            meta_form_keys=self.form_config.meta_form_keys,
            mandatory_flat=mandatory_flat,
            investor_type=investor_type,
        )
        if extracted:
            for key, value in extracted.items():
                if key in live_fill and value not in (None, ""):
                    live_fill[key] = value
            session["live_fill_flat"] = live_fill

        msg = "Do you have any other information you'd like to provide? (yes/no):"
        self._log_turn(session, user_input, msg, state)
        return msg, State.ANOTHER_INFO_PROMPT

    def _build_history(self, session: dict) -> str:
        log = session.get("conversation_log", [])
        lines = []
        for entry in log[-4:]:
            lines.append(f"User: {entry.get('user', '')}")
            lines.append(f"Bot: {entry.get('bot', '')}")
        return "\n".join(lines)