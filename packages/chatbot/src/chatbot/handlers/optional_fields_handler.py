# chatbot/handlers/optional_fields_handler.py
from __future__ import annotations
from typing import List

from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.field_utils import format_field_name
from chatbot.utils.intent_detection import is_affirmative, is_negative, is_skip_intent

# Never show these in optional list — internal, auto-set or irrelevant for Individual
NEVER_OPTIONAL_KEYS = {
    "investor_type_id",
    "inception_date_id",
    "directors_ids",
    "managing_partners_ids",
    "managing_director_ids",
    "trustees_ids",
    "beneficial_owners_ids",
    "domicile_or_country_of_incorporation_id",   # not in Lambda optional list
}
NEVER_OPTIONAL_PREFIXES = (
    "investor_type.",
    "telephone_part_",
    "fax_part_",
    "address_jurisdiction.",   # jurisdiction auto-copied from registered
    "entity_representative.",
    "form_pf.",                # excluded for Individual (non-US)
)
NEVER_OPTIONAL_SUFFIXES = ("_part_1_id", "_part_2_id", "_part_3_id", "_country_code_id")

# Friendly group labels — matches original Lambda output exactly
OPTIONAL_GROUP_LABELS = {
    "address_mailing": "Mailing Address",
    "co_investor": "Co-Investor Details",
    "custodian_details": "Custodian Details",
    "investor_eligibility": "Investor Eligibility",
}

# Top-level field labels matching original Lambda output
OPTIONAL_FIELD_LABELS = {
    "investor_ein_tax_id":               "Employer Identification Number Or Tax Identification Number",
    "investor_fax_id":                    "Fax Number",
    "investor_occupation_id":             "Investor Occupation",
    "nature_of_business_id":              "Nature Of Business",
    "principal_place_of_business_id":     "Principal Place Of Business",
    "point_of_contact_information_id":    "Point Of Contact Information",
    "currency_id":                        "Currency",
    "minimum_investment_amount_id":       "Minimum Investment Amount",
    "joint_owner_ids":                    "Joint Owners",
    "restricted_domicile_check":          "Is the investor's domicile in a restricted jurisdiction?",
    "aml_kyc_clearance_check":            "Anti-Money Laundering / Know Your Customer Clearance",
    "self_certification_check":           "Self Certification",
}


class OptionalFieldsHandler(BaseHandler):

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.OPTIONAL_FIELDS_PROMPT.value
        live_fill = session.get("live_fill_flat", {})
        mandatory_flat = session.get("mandatory_flat", {})

        optional_empty = self._get_optional_fields(live_fill, mandatory_flat)

        if not optional_empty:
            return self._go_to_complete(session, user_input, state)

        # First visit — show list and ask
        if not session.get("_optional_prompted"):
            session["_optional_prompted"] = True
            msg = self._build_optional_prompt(optional_empty)
            self._log_turn(session, user_input, msg, state)
            return msg, State.OPTIONAL_FIELDS_PROMPT

        # User responded
        if is_negative(user_input) or is_skip_intent(user_input):
            return self._go_to_complete(session, user_input, state)

        if is_affirmative(user_input):
            # Queue all optional fields for sequential fill with N/A suffix
            all_fields = optional_empty
            session["fields_being_asked"] = all_fields
            session["_in_sequential"] = True
            session["_in_optional"] = True
            if all_fields:
                from chatbot.handlers.sequential_fill_handler import SequentialFillHandler
                handler = SequentialFillHandler(self.engine)
                first = all_fields[0]
                msg = handler._ask_question(first, in_optional=True)
                self._log_turn(session, user_input, msg, state)
                return msg, State.SEQUENTIAL_FILL
            return self._go_to_complete(session, user_input, state)

        # Inline data provided
        extracted, _, _ = self.extractor.extract(
            user_input=user_input,
            conversation_history=self._build_history(session),
            live_fill_flat={k: live_fill[k] for k in optional_empty if k in live_fill},
            meta_form_keys=self.form_config.meta_form_keys,
            investor_type=session.get("investor_type", ""),
        )
        if extracted:
            for key, value in extracted.items():
                if key in live_fill and value not in (None, ""):
                    live_fill[key] = value
            session["live_fill_flat"] = live_fill
            return self._go_to_complete(session, user_input, state)

        msg = "Would you like to fill in optional information? (yes / no)"
        self._log_turn(session, user_input, msg, state)
        return msg, State.OPTIONAL_FIELDS_PROMPT

    def _get_optional_fields(self, live_fill: dict, mandatory_flat: dict) -> list:
        """All non-mandatory empty fields, filtered to user-facing only."""
        mandatory_keys = set(mandatory_flat.keys())
        result = []
        for key, val in live_fill.items():
            if key in mandatory_keys:
                continue
            if val not in (None, ""):
                continue
            if key in NEVER_OPTIONAL_KEYS:
                continue
            if any(key.startswith(p) for p in NEVER_OPTIONAL_PREFIXES):
                continue
            if any(key.endswith(s) for s in NEVER_OPTIONAL_SUFFIXES):
                continue
            if key.startswith("_"):
                continue
            result.append(key)
        return result

    def _build_optional_prompt(self, optional_empty: list) -> str:
        """Build numbered optional list matching original Lambda output."""
        seen_sections = set()
        display_items = []

        for key in optional_empty:
            if "." in key:
                section = key.split(".")[0]
                if section in seen_sections:
                    continue
                seen_sections.add(section)
                label = OPTIONAL_GROUP_LABELS.get(section) or format_field_name(section)
                display_items.append(label)
            else:
                label = OPTIONAL_FIELD_LABELS.get(key) or self.form_config.get_label(key) or format_field_name(key)
                display_items.append(label)

        lines = ["Here are some optional fields you can fill:\n"]
        for i, label in enumerate(display_items, 1):
            lines.append(f"{i}. {label}")
        lines.append("\nWould you like to fill these now? (yes/no):")
        return "\n".join(lines)

    def _go_to_complete(self, session, user_input, state):
        """Final message — matches original Lambda output exactly."""
        msg = "Alright! Please wait while the provided information is added to the uploaded PDF. For any additional information or updates, refer to the notifications panel."
        self._log_turn(session, user_input, msg, state)
        return msg, State.COMPLETE

    def _build_history(self, session: dict) -> str:
        log = session.get("conversation_log", [])
        lines = []
        for entry in log[-4:]:
            lines.append(f"User: {entry.get('user', '')}")
            lines.append(f"Bot: {entry.get('bot', '')}")
        return "\n".join(lines)