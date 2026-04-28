# # chatbot/handlers/missing_fields_handler.py
# from __future__ import annotations
# from typing import List
# from collections import OrderedDict

# from chatbot.core.states import State, US_COUNTRY_VALUES
# from chatbot.handlers.base_handler import BaseHandler
# from chatbot.utils.field_utils import format_field_name

# SEQUENTIAL_THRESHOLD = 2

# LEGITIMATE_BOOLEAN_GROUPS = ["share_class", "investor_eligibility", "form_pf", "subscriber_type"]
# FORM_PF_SKIP_TYPES = {"Individual", "IRA"}

# # Single boolean fields that are mandatory but shown via sequential fill, NOT in the grouped list
# # These match original Lambda behaviour — pep_check and fatf check are asked inline via sequential
# SINGLE_BOOLEAN_MANDATORY = {"pep_check", "wiring_details.wiring_details_bank_in_fatf_country_check"}

# # Fields excluded from the grouped missing list display (asked sequentially instead)
# EXCLUDE_FROM_LIST_DISPLAY = {
#     "investor_date_of_birth_id",  # original didn't show DOB in the list
# }


# class MissingFieldsHandler(BaseHandler):

#     def handle(self, session, user_input, user_id, session_id, debug=None):
#         state = State.MISSING_FIELDS_PROMPT.value
#         live_fill = session.get("live_fill_flat", {})
#         mandatory_flat = session.get("mandatory_flat", {})
#         investor_type = session.get("investor_type", "")

#         # Try extraction on current input (only if it looks like real data, not "yes")
#         stripped = user_input.strip().lower()
#         if user_input.strip() and stripped not in ("yes", "y", "no", "n", "ok", "okay"):
#             missing_now = [k for k in mandatory_flat if live_fill.get(k) in (None, "")]
#             if missing_now:
#                 extracted, _, _ = self.extractor.extract(
#                     user_input=user_input,
#                     conversation_history=self._build_history(session),
#                     live_fill_flat={k: live_fill[k] for k in missing_now if k in live_fill},
#                     meta_form_keys=self.form_config.meta_form_keys,
#                     mandatory_flat=mandatory_flat,
#                     investor_type=investor_type,
#                 )
#                 for key, value in extracted.items():
#                     if key in live_fill and live_fill.get(key) in (None, "") and value not in (None, ""):
#                         live_fill[key] = value
#                 session["live_fill_flat"] = live_fill

#         # ── Check text fields first (in mandatory order) ───────────────
#         text_missing = self._get_missing_text(live_fill, mandatory_flat)

#         if text_missing:
#             attempts = session.get("_missing_attempts", 0) + 1
#             session["_missing_attempts"] = attempts
#             debug and debug.log("missing_fields", f"Still missing {len(text_missing)} text fields (attempt {attempts})")

#             if attempts >= SEQUENTIAL_THRESHOLD:
#                 session["_missing_attempts"] = 0
#                 session["fields_being_asked"] = text_missing[:1]
#                 field_key = text_missing[0]
#                 question = self.form_config.get_question(field_key)
#                 label = self.form_config.get_label(field_key) or format_field_name(field_key)
#                 msg = question or f"Could you please provide your {label.lower()}?"
#                 self._log_turn(session, user_input, msg, state)
#                 return msg, State.SEQUENTIAL_FILL

#             # Build grouped display — one item per section (matches original Lambda output)
#             grouped_labels = self._get_grouped_missing_labels(text_missing)
#             # Also add boolean groups as single items at the end
#             for group in LEGITIMATE_BOOLEAN_GROUPS:
#                 fields_in_group = [
#                     k for k in mandatory_flat
#                     if k.startswith(f"{group}.") and live_fill.get(k) is None
#                 ]
#                 if fields_in_group and not any(live_fill.get(f) in (True, False) for f in fields_in_group):
#                     grouped_labels.append(format_field_name(group))

#             lines = ["It appears that some mandatory information is missing, as listed below.\n"]
#             for i, label in enumerate(grouped_labels, 1):
#                 lines.append(f"{i}. {label}")
#             lines.append("\nWould you like to provide them now?")
#             msg = "\n".join(lines)
#             self._log_turn(session, user_input, msg, state)
#             # Route to sequential fill directly on next "yes" — set flag
#             session["_after_missing_list"] = True
#             return msg, State.DATA_COLLECTION

#         # ── All text done — now handle boolean groups in order ─────────
#         next_group_name, next_group_fields = self._next_boolean_group(live_fill, mandatory_flat, investor_type, session)

#         if next_group_fields:
#             session["current_group"] = next_group_name
#             session["fields_being_asked"] = next_group_fields

#             if len(next_group_fields) == 1:
#                 # Single boolean — ask as yes/no
#                 key = next_group_fields[0]
#                 question = self.form_config.get_question(key) or format_field_name(key)
#                 msg = f"{question}\nPlease answer YES or NO"
#                 self._log_turn(session, user_input, msg, state)
#                 return msg, State.BOOLEAN_GROUP_SELECT
#             else:
#                 # Multi boolean — numbered list
#                 lines = [f"Choose all applicable options for the Investor's {format_field_name(next_group_name)} (comma-separated). Select 'None' if not applicable.\n"]
#                 for i, key in enumerate(next_group_fields, 1):
#                     question = self.form_config.get_question(key) or format_field_name(key)
#                     lines.append(f"{i}. {question}")
#                 msg = "\n".join(lines)
#                 self._log_turn(session, user_input, msg, state)
#                 return msg, State.BOOLEAN_GROUP_SELECT

#         # ── All mandatory done ─────────────────────────────────────────
#         debug and debug.log("missing_fields", "All mandatory fields complete")
#         msg = "All required information for the selected investor has been received. Would you like to include additional optional information?(yes/no):"
#         self._log_turn(session, user_input, msg, state)
#         return msg, State.OPTIONAL_FIELDS_PROMPT

#     # ------------------------------------------------------------------

#     def _get_missing_text(self, live_fill: dict, mandatory_flat: dict) -> list:
#         """Missing mandatory TEXT fields in mandatory.json order, excluding boolean groups,
#         investor_type, and single booleans (handled via sequential fill)."""
#         missing = []
#         for key in mandatory_flat:
#             section = key.split(".")[0] if "." in key else ""
#             # Skip boolean group fields — handled separately
#             if section in LEGITIMATE_BOOLEAN_GROUPS:
#                 continue
#             # Skip investor_type fields — auto-set
#             if key.startswith("investor_type."):
#                 continue
#             # Skip single booleans like pep_check — handled inline via sequential fill
#             if key in SINGLE_BOOLEAN_MANDATORY:
#                 continue
#             val = live_fill.get(key)
#             if val is None or val == "":
#                 missing.append(key)
#         return missing

#     def _next_boolean_group(self, live_fill: dict, mandatory_flat: dict, investor_type: str, session: dict):
#         """Return (group_name, [field_keys]) for the next unanswered boolean group in order."""
#         asked = session.get("_asked_boolean_groups", [])

#         # Determine if form_pf applies
#         registered_country = ""
#         for key, val in live_fill.items():
#             if "address_registered_country" in key and val:
#                 registered_country = str(val).strip().lower()
#                 break
#         is_us = registered_country in US_COUNTRY_VALUES
#         show_form_pf = investor_type not in FORM_PF_SKIP_TYPES and is_us

#         for group_name in LEGITIMATE_BOOLEAN_GROUPS:
#             if group_name == "form_pf" and not show_form_pf:
#                 continue
#             if group_name in asked:
#                 continue

#             # Get fields for this group from mandatory_flat in order
#             fields = [k for k in mandatory_flat if k.startswith(f"{group_name}.") and live_fill.get(k) is None]

#             if not fields:
#                 continue

#             # Skip if any field already answered (True/False)
#             if any(live_fill.get(f) in (True, False) for f in fields):
#                 continue

#             session.setdefault("_asked_boolean_groups", []).append(group_name)
#             return group_name, fields

#         return None, []

#     # Friendly group labels matching original Lambda output
#     SECTION_LABELS = {
#         "address_registered": "Registered Address",
#         "address_mailing":    "Mailing Address",
#         "wiring_details":     "Wiring Details",
#         "co_investor":        "Co-Investor Details",
#         "custodian_details":  "Custodian Details",
#         "form_pf":            "Form PF (Investor Type)",
#         "investor_eligibility": "Investor Eligibility",
#         "share_class":        "Share Class",
#     }

#     # Top-level field labels matching original Lambda output
#     FIELD_LABELS = {
#         "investor_telephone_id":    "Telephone Number",
#         "investor_email_id":        "Email Address",
#         "investor_ssn_id":          "Social Security Number",
#         "authorized_signatory_id":  "Authorized Signatory",
#         "commitment_amount_id":     "Commitment Amount",
#         "investor_ein_tax_id":      "Employer Identification Number Or Tax Identification Number",
#         "investor_date_of_birth_id":"Date Of Birth",
#     }

#     def _get_grouped_missing_labels(self, missing_keys: list) -> list:
#         """Convert list of flat field keys to grouped display labels (one per section),
#         excluding fields that should not appear in the list."""
#         seen_sections = set()
#         labels = []
#         for key in missing_keys:
#             # Skip fields excluded from list display
#             if key in EXCLUDE_FROM_LIST_DISPLAY:
#                 continue
#             # Skip single boolean mandatory fields — they appear via sequential fill
#             if key in SINGLE_BOOLEAN_MANDATORY:
#                 continue
#             if "." in key:
#                 section = key.split(".")[0]
#                 if section in seen_sections:
#                     continue
#                 seen_sections.add(section)
#                 labels.append(self.SECTION_LABELS.get(section) or format_field_name(section))
#             else:
#                 label = self.FIELD_LABELS.get(key) or self.form_config.get_label(key) or format_field_name(key)
#                 labels.append(label)
#         return labels

#     def _build_history(self, session: dict) -> str:
#         log = session.get("conversation_log", [])
#         lines = []
#         for entry in log[-4:]:
#             lines.append(f"User: {entry.get('user', '')}")
#             lines.append(f"Bot: {entry.get('bot', '')}")
#         return "\n".join(lines)





















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