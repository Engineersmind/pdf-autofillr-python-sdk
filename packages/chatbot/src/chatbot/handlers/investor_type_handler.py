# chatbot/handlers/investor_type_handler.py
"""Handles INVESTOR_TYPE_SELECT state."""
from __future__ import annotations
from typing import Optional, Tuple

from fuzzywuzzy import process as fuzz_process

from chatbot.core.states import (
    State,
    INVESTOR_TYPES,
    INVESTOR_TYPE_BOOLEAN_FIELD,
    INTERNAL_SPLIT_FIELD_PREFIXES,
    FORM_PF_FIELD_PREFIX,
    US_COUNTRY_VALUES,
)
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.dict_utils import flatten_dict


class InvestorTypeHandler(BaseHandler):
    def handle(self, session, user_input, user_id, session_id, debug=None):
        investor_type = self._parse_selection(user_input)
        if not investor_type:
            lines = ["I didn't recognise that. Please choose a number or type the investor type:\n"]
            for i, t in enumerate(INVESTOR_TYPES, 1):
                lines.append(f"  {i}. {t}")
            msg = "\n".join(lines)
            self._log_turn(session, user_input, msg, State.INVESTOR_TYPE_SELECT.value)
            return msg, State.INVESTOR_TYPE_SELECT

        form_keys = self.form_config.get_form_keys_for_type(investor_type)
        mandatory = self.form_config.get_mandatory_fields_for_type(investor_type)
        session["investor_type"] = investor_type

        # Flatten, strip private keys and internal split fields (never shown to user)
        live_fill_flat = {
            k: v for k, v in flatten_dict(form_keys).items()
            if not k.startswith("_")
            and not any(k.split(".")[-1].startswith(p) for p in INTERNAL_SPLIT_FIELD_PREFIXES)
        }
        mandatory_flat = {
            k: v for k, v in flatten_dict(mandatory).items()
            if not k.startswith("_")
        }

        session["live_fill_flat"] = live_fill_flat
        session["mandatory_flat"] = mandatory_flat

        # Auto-set the investor_type boolean field — mirrors Lambda behaviour
        # e.g. investor_type.individual_check = True
        bool_field = INVESTOR_TYPE_BOOLEAN_FIELD.get(investor_type)
        if bool_field and bool_field in live_fill_flat:
            live_fill_flat[bool_field] = True
            debug and debug.log(
                "investor_type",
                f"Auto-set boolean field {bool_field} = True",
            )

        # Merge existing (pre-fill) data if user accepted it
        existing = session.pop("_pending_existing_data", None)
        if existing:
            for k, v in existing.items():
                if k in live_fill_flat and v not in (None, ""):
                    live_fill_flat[k] = v

        # Trigger PDF preparation in background if configured
        if self.engine.pdf_workflow and session.get("pdf_path"):
            self.engine.pdf_workflow.trigger_prepare_async(
                user_id=user_id,
                session_id=session_id,
                pdf_path=session["pdf_path"],
                investor_type=investor_type,
            )

        debug and debug.log(
            "investor_type",
            f"Investor type set: {investor_type} | "
            f"live_fill keys: {len(live_fill_flat)} | mandatory keys: {len(mandatory_flat)}",
        )

        msg = (
            f"Alright, '{investor_type} Investor' is selected.\n\n"
            "Let's get started! Please enter the details you'd like to fill in the PDF.\n"
            "For best results, separate multiple details using a semicolon (;), "
            "an ampersand (&), or place each on a new line."
        )
        self._log_turn(session, user_input, msg, State.INVESTOR_TYPE_SELECT.value)
        return msg, State.DATA_COLLECTION

    def _parse_selection(self, user_input):
        txt = user_input.strip()
        if txt.isdigit():
            idx = int(txt) - 1
            if 0 <= idx < len(INVESTOR_TYPES):
                return INVESTOR_TYPES[idx]
            return None
        match, score = fuzz_process.extractOne(txt, INVESTOR_TYPES)
        return match if score >= 70 else None