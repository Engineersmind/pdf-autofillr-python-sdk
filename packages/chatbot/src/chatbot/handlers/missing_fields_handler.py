# chatbot/handlers/missing_fields_handler.py
from __future__ import annotations
from chatbot.core.states import State, US_COUNTRY_VALUES
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.field_utils import format_field_name

LEGITIMATE_BOOLEAN_GROUPS = ["share_class", "investor_eligibility", "form_pf", "subscriber_type"]
FORM_PF_SKIP_TYPES = {"Individual", "IRA"}

# pep_check IS shown in the missing list AND asked via sequential fill yes/no
# fatf check is asked inline during wiring sequential fill — not shown in list
SINGLE_BOOLEAN_MANDATORY = {"wiring_details.wiring_details_bank_in_fatf_country_check"}


class MissingFieldsHandler(BaseHandler):

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.MISSING_FIELDS_PROMPT.value
        live_fill = session.get("live_fill_flat", {})
        mandatory_flat = session.get("mandatory_flat", {})
        investor_type = session.get("investor_type", "")

        # Try extraction on current input if it looks like real data
        stripped = user_input.strip().lower()
        if user_input.strip() and stripped not in ("yes", "y", "no", "n", "ok", "okay"):
            missing_now = [k for k in mandatory_flat if live_fill.get(k) in (None, "")]
            if missing_now:
                extracted, _, _ = self.extractor.extract(
                    user_input=user_input,
                    conversation_history=self._build_history(session),
                    live_fill_flat={k: live_fill[k] for k in missing_now if k in live_fill},
                    meta_form_keys=self.form_config.meta_form_keys,
                    mandatory_flat=mandatory_flat,
                    investor_type=investor_type,
                )
                for key, value in extracted.items():
                    if key in live_fill and live_fill.get(key) in (None, "") and value not in (None, ""):
                        live_fill[key] = value
                session["live_fill_flat"] = live_fill

        # ── Text fields: always immediately go to SEQUENTIAL_FILL ──────
        text_missing = self._get_missing_text(live_fill, mandatory_flat)

        if text_missing:
            debug and debug.log("missing_fields", f"Still missing {len(text_missing)} text fields (attempt 1)")
            session["fields_being_asked"] = text_missing
            field_key = text_missing[0]
            question = self.form_config.get_question(field_key)
            label = self.form_config.get_label(field_key) or format_field_name(field_key)
            msg = question or f"Please provide the {label.lower()}."
            self._log_turn(session, user_input, msg, state)
            return msg, State.SEQUENTIAL_FILL

        # ── Boolean groups ─────────────────────────────────────────────
        next_group_name, next_group_fields = self._next_boolean_group(
            live_fill, mandatory_flat, investor_type, session
        )

        if next_group_fields:
            session["current_group"] = next_group_name
            session["fields_being_asked"] = next_group_fields

            if len(next_group_fields) == 1:
                key = next_group_fields[0]
                question = self.form_config.get_question(key) or format_field_name(key)
                msg = f"{question}\nPlease answer YES or NO"
                self._log_turn(session, user_input, msg, state)
                return msg, State.BOOLEAN_GROUP_SELECT
            else:
                lines = [f"Choose all applicable options for the Investor's {format_field_name(next_group_name)} (comma-separated). Select 'None' if not applicable.\n"]
                for i, key in enumerate(next_group_fields, 1):
                    question = self.form_config.get_question(key) or format_field_name(key)
                    lines.append(f"{i}. {question}")
                msg = "\n".join(lines)
                self._log_turn(session, user_input, msg, state)
                return msg, State.BOOLEAN_GROUP_SELECT

        # ── All mandatory done ─────────────────────────────────────────
        debug and debug.log("missing_fields", "All mandatory fields complete")
        msg = "All required information for the selected investor has been received. Would you like to include additional optional information?(yes/no):"
        self._log_turn(session, user_input, msg, state)
        return msg, State.OPTIONAL_FIELDS_PROMPT

    # ------------------------------------------------------------------

    def _get_missing_text(self, live_fill: dict, mandatory_flat: dict) -> list:
        missing = []
        for key in mandatory_flat:
            section = key.split(".")[0] if "." in key else ""
            if section in LEGITIMATE_BOOLEAN_GROUPS:
                continue
            if key.startswith("investor_type."):
                continue
            if key in SINGLE_BOOLEAN_MANDATORY:
                continue
            val = live_fill.get(key)
            if val is None or val == "":
                missing.append(key)
        return missing

    def _next_boolean_group(self, live_fill, mandatory_flat, investor_type, session):
        asked = session.get("_asked_boolean_groups", [])
        registered_country = ""
        for key, val in live_fill.items():
            if "address_registered_country" in key and val:
                registered_country = str(val).strip().lower()
                break
        is_us = registered_country in US_COUNTRY_VALUES
        show_form_pf = investor_type not in FORM_PF_SKIP_TYPES and is_us

        for group_name in LEGITIMATE_BOOLEAN_GROUPS:
            if group_name == "form_pf" and not show_form_pf:
                continue
            if group_name in asked:
                continue
            fields = [k for k in mandatory_flat if k.startswith(f"{group_name}.") and live_fill.get(k) is None]
            if not fields:
                continue
            if any(live_fill.get(f) in (True, False) for f in fields):
                continue
            session.setdefault("_asked_boolean_groups", []).append(group_name)
            return group_name, fields
        return None, []

    # Labels matching Lambda output exactly
    SECTION_LABELS = {
        "address_registered": "Registered Address",
        "address_mailing":    "Mailing Address",
        "wiring_details":     "Wiring Details",
        "co_investor":        "Co-Investor Details",
        "custodian_details":  "Custodian Details",
        "form_pf":            "Form PF (Investor Type)",
        "investor_eligibility": "Investor Eligibility",
        "share_class":        "Share Class",
    }

    FIELD_LABELS = {
        "investor_telephone_id":     "Telephone Number",
        "investor_email_id":         "Email Address",
        "investor_ssn_id":           "Social Security Number",
        "investor_date_of_birth_id": "Investor Date Of Birth",
        "authorized_signatory_id":   "Authorized Signatory",
        "commitment_amount_id":      "Commitment Amount",
        "investor_ein_tax_id":       "Employer Identification Number Or Tax Identification Number",
        "pep_check":                 "Is the investor a Politically Exposed Person?",
    }

    def _get_grouped_missing_labels(self, missing_keys: list) -> list:
        seen_sections = set()
        labels = []
        for key in missing_keys:
            if key in SINGLE_BOOLEAN_MANDATORY:
                continue
            if "." in key:
                section = key.split(".")[0]
                if section in seen_sections:
                    continue
                seen_sections.add(section)
                labels.append(self.SECTION_LABELS.get(section) or format_field_name(section))
            else:
                label = self.FIELD_LABELS.get(key) or self.form_config.get_label(key) or format_field_name(key)
                labels.append(label)
        return labels

    def _build_history(self, session: dict) -> str:
        log = session.get("conversation_log", [])
        lines = []
        for entry in log[-4:]:
            lines.append(f"User: {entry.get('user', '')}")
            lines.append(f"Bot: {entry.get('bot', '')}")
        return "\n".join(lines)