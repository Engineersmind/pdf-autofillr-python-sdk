# chatbot/handlers/sequential_fill_handler.py
from __future__ import annotations
from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.field_utils import format_field_name
from chatbot.utils.intent_detection import is_skip_intent, is_affirmative, is_negative
from chatbot.validation.field_validator import validate_field
from chatbot.validation.phone_validator import validate_phone


class SequentialFillHandler(BaseHandler):

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.SEQUENTIAL_FILL.value
        live_fill = session.get("live_fill_flat", {})
        mandatory_flat = session.get("mandatory_flat", {})
        fields = session.get("fields_being_asked", [])
        in_optional = session.get("_in_optional", False)

        # Suppress mailing check while we are filling fields one by one
        session["_in_sequential"] = True

        if not fields:
            session["_in_sequential"] = False
            return self._done(session, user_input, user_id, session_id, debug, in_optional)

        current_field = fields[0]
        is_bool = "_check" in current_field
        is_phone = any(w in current_field.lower() for w in ("telephone", "phone", "mobile"))

        # Skip — only allowed for optional fields
        if is_skip_intent(user_input):
            if current_field in mandatory_flat:
                msg = f"This field is required. {self._ask_question(current_field, in_optional)}"
                self._log_turn(session, user_input, msg, state)
                return msg, State.SEQUENTIAL_FILL
            return self._advance(session, user_input, state, live_fill, mandatory_flat, fields, user_id, session_id, debug, in_optional)

        # ── Boolean fields ─────────────────────────────────────────────
        if is_bool:
            if is_affirmative(user_input):
                live_fill[current_field] = True
            elif is_negative(user_input):
                live_fill[current_field] = False
            else:
                # Try LLM
                extracted = self._extract_single(user_input, current_field, session, live_fill)
                value = extracted.get(current_field)
                if value in (True, False):
                    live_fill[current_field] = value
                else:
                    question = self.form_config.get_question(current_field) or format_field_name(current_field)
                    msg = f"Oops! I didn't get that. Could you please provide the details once more?\n{question}\nPlease answer YES or NO"
                    self._log_turn(session, user_input, msg, state)
                    return msg, State.SEQUENTIAL_FILL
            session["live_fill_flat"] = live_fill
            debug and debug.log("sequential_fill", f"Boolean: {current_field} = {live_fill[current_field]}")
            return self._advance(session, user_input, state, live_fill, mandatory_flat, fields, user_id, session_id, debug, in_optional)

        # ── Phone fields ───────────────────────────────────────────────
        if is_phone:
            val = user_input.strip()
            if not validate_phone(val):
                digits = ''.join(c for c in val if c.isdigit())
                has_prefix = val.startswith('+') or val.startswith('00')
                if has_prefix and len(digits) < 10:
                    msg = "It appears that the country code entered is invalid. Please ensure it is a numeric value consisting of 1 to 4 digits, and enter it before the phone number (e.g., USA: +1 000 000 0000)."
                elif not has_prefix and len(digits) == 10:
                    msg = "It looks like the entered phone number is missing the country code. Please enter it with the code (e.g., USA: +1 000 000 0000)."
                else:
                    msg = "Unable to read the phone number. Please resend it with the country code followed by the number (e.g., USA: +1 000 000 0000)."
                self._log_turn(session, user_input, msg, state)
                return msg, State.SEQUENTIAL_FILL
            live_fill[current_field] = val
            session["live_fill_flat"] = live_fill
            return self._advance(session, user_input, state, live_fill, mandatory_flat, fields, user_id, session_id, debug, in_optional)

        # Extract — pass full schema so LLM strips "my address is..." phrases
        extracted = self._extract_single(user_input, current_field, session, live_fill)
        value = extracted.get(current_field)

        if value is not None and value != "":
            valid, err = validate_field(current_field, value)
            if valid or "_check" in current_field:
                live_fill[current_field] = value
                session["live_fill_flat"] = live_fill
                debug and debug.log("sequential_fill", f"Filled {current_field} = {value!r}")
                return self._advance(session, user_input, state, live_fill, mandatory_flat, fields, user_id, session_id, debug, in_optional)
            else:
                msg = f"{err}\n\n{self._ask_question(current_field, in_optional)}"
                self._log_turn(session, user_input, msg, state)
                return msg, State.SEQUENTIAL_FILL
        else:
            # Raw fallback for text fields
            if "_check" not in current_field:
                raw = user_input.strip()
                if raw:
                    live_fill[current_field] = raw
                    session["live_fill_flat"] = live_fill
                    debug and debug.log("sequential_fill", f"Raw fill: {current_field} = {raw!r}")
                    return self._advance(session, user_input, state, live_fill, mandatory_flat, fields, user_id, session_id, debug, in_optional)
            msg = f"I couldn't get that. {self._ask_question(current_field, in_optional)}"
            self._log_turn(session, user_input, msg, state)
            return msg, State.SEQUENTIAL_FILL

    # ------------------------------------------------------------------

    def _extract_single(self, user_input, field_key, session, live_fill):
        try:
            extracted, _, _ = self.extractor.extract(
                user_input=user_input,
                conversation_history=self._build_history(session),
                live_fill_flat=live_fill,
                meta_form_keys=self.form_config.meta_form_keys,
                investor_type=session.get("investor_type", ""),
                mandatory_flat={field_key: live_fill.get(field_key)},
            )
            if field_key in extracted:
                return {field_key: extracted[field_key]}
            return {}
        except Exception:
            return {}

    def _ask_question(self, field_key: str, in_optional: bool = False) -> str:
        question = self.form_config.get_question(field_key)
        if question:
            return question
        label = self.form_config.get_label(field_key) or format_field_name(field_key)
        question = f"Please provide your {label.lower()}."
        if "_check" in field_key:
            return f"{question}\nPlease answer YES or NO"
        if in_optional:
            return f'{question} If this is not applicable, please respond with "N/A".'
        return question

    def _advance(self, session, user_input, state, live_fill, mandatory_flat, fields, user_id, session_id, debug, in_optional):
        """Move to the next queued field, or finish sequential fill."""
        remaining = fields[1:]
        session["fields_being_asked"] = remaining

        if remaining:
            next_field = remaining[0]
            msg = self._ask_question(next_field, in_optional)
            self._log_turn(session, user_input, msg, state)
            return msg, State.SEQUENTIAL_FILL

        # All queued fields done
        return self._done(session, user_input, user_id, session_id, debug, in_optional)

    def _done(self, session, user_input, user_id, session_id, debug, in_optional=False):
        """All sequential fields complete — hand back to MissingFieldsHandler."""
        session["_in_sequential"] = False
        session["fields_being_asked"] = []
        if in_optional:
            session["_in_optional"] = False
            msg = "Alright! Please wait while the provided information is added to the uploaded PDF. For any additional information or updates, refer to the notifications panel."
            self._log_turn(session, user_input, msg, State.SEQUENTIAL_FILL.value)
            return msg, State.COMPLETE
        from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
        handler = MissingFieldsHandler(self.engine)
        return handler.handle(session, user_input, user_id, session_id, debug)

    def _build_history(self, session: dict) -> str:
        log = session.get("conversation_log", [])
        lines = []
        for entry in log[-4:]:
            lines.append(f"User: {entry.get('user', '')}")
            lines.append(f"Bot: {entry.get('bot', '')}")
        return "\n".join(lines)