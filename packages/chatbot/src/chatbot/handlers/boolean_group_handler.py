# chatbot/handlers/boolean_group_handler.py
from __future__ import annotations
from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.field_utils import format_field_name
from chatbot.utils.intent_detection import is_affirmative, is_negative, is_skip_intent


class BooleanGroupHandler(BaseHandler):

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.BOOLEAN_GROUP_SELECT.value
        live_fill = session.get("live_fill_flat", {})
        fields = session.get("fields_being_asked", [])

        if not fields:
            return self._back_to_missing(session, user_input)

        any_filled = False

        # ── Single boolean (pep_check, fatf_check) ─────────────────────
        if len(fields) == 1:
            key = fields[0]
            if is_affirmative(user_input):
                live_fill[key] = True
                any_filled = True
            elif is_negative(user_input) or is_skip_intent(user_input):
                live_fill[key] = False
                any_filled = True
            else:
                extracted, _, _ = self.extractor.extract(
                    user_input=user_input,
                    conversation_history=self._build_history(session),
                    live_fill_flat={key: live_fill.get(key)},
                    meta_form_keys=self.form_config.meta_form_keys,
                    investor_type=session.get("investor_type", ""),
                )
                if key in extracted and extracted[key] in (True, False):
                    live_fill[key] = extracted[key]
                    any_filled = True

            if not any_filled:
                question = self.form_config.get_question(key) or format_field_name(key)
                msg = f"Oops! I didn't get that. Could you please provide the details once more?\n{question}\nPlease answer YES or NO"
                self._log_turn(session, user_input, msg, state)
                return msg, State.BOOLEAN_GROUP_SELECT

            session["live_fill_flat"] = live_fill
            return self._back_to_missing(session, user_input)

        # ── Multi-field group (share_class, investor_eligibility) ───────
        numbered = self._parse_numbered(user_input, fields)

        if numbered is not None:
            for i, key in enumerate(fields):
                live_fill[key] = (i in numbered)
            any_filled = True
        elif is_negative(user_input) or user_input.strip().lower() == "none":
            for key in fields:
                live_fill[key] = False
            any_filled = True
        elif is_affirmative(user_input):
            for key in fields:
                live_fill[key] = True
            any_filled = True
        else:
            extracted, _, method = self.extractor.extract(
                user_input=user_input,
                conversation_history=self._build_history(session),
                live_fill_flat={k: live_fill[k] for k in fields if k in live_fill},
                meta_form_keys=self.form_config.meta_form_keys,
                investor_type=session.get("investor_type", ""),
            )
            for key in fields:
                if key in extracted and extracted[key] in (True, False):
                    live_fill[key] = extracted[key]
                    any_filled = True

        session["live_fill_flat"] = live_fill

        if not any_filled:
            lines = ["Oops! I didn't get that. Could you please provide the details once more?\nPlease select valid option numbers.\n"]
            for i, key in enumerate(fields, 1):
                question = self.form_config.get_question(key) or format_field_name(key)
                lines.append(f"{i}. {question}")
            msg = "\n".join(lines)
            self._log_turn(session, user_input, msg, state)
            return msg, State.BOOLEAN_GROUP_SELECT

        return self._back_to_missing(session, user_input)

    def _parse_numbered(self, user_input: str, fields: list):
        txt = user_input.strip().replace(" ", ",")
        parts = [p.strip().rstrip(".,);: ") for p in txt.split(",") if p.strip()]
        if not parts:
            return None
        indices = set()
        for p in parts:
            if not p.isdigit():
                return None
            idx = int(p) - 1
            if 0 <= idx < len(fields):
                indices.add(idx)
        return indices if indices else None

    def _back_to_missing(self, session, user_input):
        """Silently delegate to MissingFieldsHandler — no intermediate message, matches Lambda."""
        session["fields_being_asked"] = []
        session["current_group"] = None
        from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
        handler = MissingFieldsHandler(self.engine)
        return handler.handle(session, user_input, None, None, None)

    def _build_history(self, session: dict) -> str:
        log = session.get("conversation_log", [])
        lines = []
        for entry in log[-4:]:
            lines.append(f"User: {entry.get('user', '')}")
            lines.append(f"Bot: {entry.get('bot', '')}")
        return "\n".join(lines)