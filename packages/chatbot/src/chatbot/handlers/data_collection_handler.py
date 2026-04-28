# # chatbot/handlers/data_collection_handler.py
# from __future__ import annotations
# from typing import List
# from collections import OrderedDict

# from chatbot.core.states import State
# from chatbot.handlers.base_handler import BaseHandler
# from chatbot.utils.field_utils import (
#     get_missing_mandatory_keys,
#     format_field_name,
#     filter_form_pf_fields,
#     filter_user_facing_fields,
#     get_registered_country,
#     is_internal_split_field,
# )
# from chatbot.utils.address_utils import check_mailing_fields, copy_registered_to_mailing
# from chatbot.utils.intent_detection import is_exit_intent
# from chatbot.validation.field_validator import validate_field
# from chatbot.validation.phone_validator import split_phone_parts

# MAX_MISSING_DISPLAY = 6
# MIN_EXTRACTED = 1
# PHONE_FAX_FULL_FIELD_SUFFIXES = ("telephone", "phone", "mobile", "fax", "tel")

# # Boolean group sections — handled separately as numbered multi-select, never as text
# BOOLEAN_GROUP_SECTIONS = {"share_class", "investor_eligibility", "form_pf", "subscriber_type"}

# # Fields never shown to user — internal split fields + investor_type auto-set
# NEVER_ASK_PREFIXES = ("investor_type.",)


# class DataCollectionHandler(BaseHandler):

#     def handle(self, session, user_input, user_id, session_id, debug=None):
#         state = State.DATA_COLLECTION.value

#         if is_exit_intent(user_input):
#             msg = "Session ended. Your progress has been saved. Goodbye!"
#             self._log_turn(session, user_input, msg, state)
#             return msg, State.COMPLETE

#         # If we just showed the missing fields list, handle yes/no explicitly
#         if session.get("_after_missing_list"):
#             from chatbot.utils.intent_detection import is_negative
#             if is_negative(user_input) or is_exit_intent(user_input):
#                 session.pop("_after_missing_list", None)
#                 # User declined to provide missing fields — go to optional fields
#                 msg = "Alright! Please wait while the provided information is added to the uploaded PDF. For any additional information or updates, refer to the notifications panel."
#                 self._log_turn(session, user_input, msg, state)
#                 return msg, State.COMPLETE
#             # User said yes — go straight to sequential fill
#             session.pop("_after_missing_list", None)
#             from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
#             handler = MissingFieldsHandler(self.engine)
#             session["_missing_attempts"] = 2
#             return handler.handle(session, user_input, user_id, session_id, debug)

#         live_fill = session.setdefault("live_fill_flat", {})
#         mandatory_flat = session.get("mandatory_flat", {})
#         investor_type = session.get("investor_type", "")

#         history = self._build_history(session)
#         user_facing = filter_user_facing_fields(live_fill)

#         extracted, latency, method = self.extractor.extract(
#             user_input=user_input,
#             conversation_history=history,
#             live_fill_flat=user_facing,
#             meta_form_keys=self.form_config.meta_form_keys,
#             mandatory_flat=mandatory_flat,
#             investor_type=investor_type,
#         )

#         debug and debug.log(
#             "data_collection",
#             f"Extracted {len(extracted)} fields via {method} in {latency:.2f}s",
#             data={"fields": list(extracted.keys())},
#         )

#         merged_count = 0
#         for key, value in extracted.items():
#             if key not in live_fill:
#                 continue
#             if is_internal_split_field(key):
#                 continue
#             valid, err = validate_field(key, value)
#             if valid or value in (True, False, None):
#                 if live_fill.get(key) in (None, ""):
#                     live_fill[key] = value
#                     merged_count += 1
#                 elif value not in (None, ""):
#                     live_fill[key] = value
#                     merged_count += 1

#         self._populate_split_fields(live_fill, debug)

#         # form_pf filtering for non-US investors
#         registered_country = get_registered_country(live_fill)
#         if registered_country and not session.get("_form_pf_filtered"):
#             filtered = filter_form_pf_fields(live_fill, registered_country)
#             if len(filtered) < len(live_fill):
#                 live_fill.clear()
#                 live_fill.update(filtered)
#                 for key in list(mandatory_flat.keys()):
#                     if key not in live_fill:
#                         del mandatory_flat[key]
#                 session["mandatory_flat"] = mandatory_flat
#             session["_form_pf_filtered"] = True

#         session["live_fill_flat"] = live_fill

#         # Mailing address check — after registered address filled
#         if (
#             check_mailing_fields(live_fill)
#             and not session.get("_mailing_checked")
#             and self._registered_address_filled(live_fill)
#         ):
#             msg = "Is your mailing address the same as your registered address? (yes / no)"
#             self._log_turn(session, user_input, msg, state)
#             return msg, State.MAILING_ADDRESS_CHECK

#         # Get missing mandatory — excluding boolean group fields (handled separately)
#         # and excluding investor_type (auto-set)
#         missing_text = self._get_missing_text_mandatory(live_fill, mandatory_flat)
#         missing_bool_groups = self._get_missing_bool_groups(live_fill, mandatory_flat, investor_type, session)

#         # If all mandatory done -> missing_fields_prompt (which handles bool groups then optional)
#         if not missing_text and not missing_bool_groups:
#             msg = "Thank you! I have all the required information. Let me review everything."
#             self._log_turn(session, user_input, msg, state)
#             return msg, State.MISSING_FIELDS_PROMPT

#         # Still have fields missing — ask yes/no for more info (matches original Lambda behaviour)
#         msg = "Do you have any other information you'd like to provide? (yes/no):"
#         self._log_turn(session, user_input, msg, state)
#         return msg, State.ANOTHER_INFO_PROMPT

#     # ------------------------------------------------------------------

#     def _get_missing_text_mandatory(self, live_fill: dict, mandatory_flat: dict) -> list:
#         """Missing mandatory fields that are TEXT fields (not boolean group fields, not investor_type)."""
#         missing = []
#         for key in mandatory_flat:
#             # Skip boolean group fields — handled separately
#             section = key.split(".")[0] if "." in key else ""
#             if section in BOOLEAN_GROUP_SECTIONS:
#                 continue
#             # Skip investor_type fields — auto-set
#             if any(key.startswith(p) for p in NEVER_ASK_PREFIXES):
#                 continue
#             val = live_fill.get(key)
#             if val is None or val == "":
#                 missing.append(key)
#         return missing

#     def _get_missing_bool_groups(self, live_fill: dict, mandatory_flat: dict, investor_type: str, session: dict) -> dict:
#         """Returns {section: [field_keys]} for boolean groups that still have unanswered mandatory fields."""
#         from collections import defaultdict
#         groups = defaultdict(list)
#         for key in mandatory_flat:
#             section = key.split(".")[0] if "." in key else ""
#             if section not in BOOLEAN_GROUP_SECTIONS:
#                 continue
#             val = live_fill.get(key)
#             if val is None:  # null = unanswered
#                 groups[section].append(key)
#         return dict(groups)

#     def _populate_split_fields(self, live_fill: dict, debug) -> None:
#         for key, value in list(live_fill.items()):
#             if not value or not isinstance(value, str):
#                 continue
#             leaf = key.split(".")[-1]
#             if not any(leaf.endswith(s) or leaf == s for s in PHONE_FAX_FULL_FIELD_SUFFIXES):
#                 continue
#             parts = split_phone_parts(value)
#             prefix = key.rsplit(".", 1)[0] if "." in key else ""
#             split_prefix = "fax_part_" if "fax" in leaf else "telephone_part_"
#             mapping = {
#                 f"{split_prefix}country_code": parts["country_code"],
#                 f"{split_prefix}1": parts["part1"],
#                 f"{split_prefix}2": parts["part2"],
#                 f"{split_prefix}3": parts["part3"],
#             }
#             for split_leaf, split_val in mapping.items():
#                 full_key = f"{prefix}.{split_leaf}" if prefix else split_leaf
#                 if full_key in live_fill:
#                     live_fill[full_key] = split_val

#     def _build_history(self, session: dict) -> str:
#         log = session.get("conversation_log", [])
#         lines = []
#         for entry in log[-6:]:
#             lines.append(f"User: {entry.get('user', '')}")
#             lines.append(f"Bot: {entry.get('bot', '')}")
#         return "\n".join(lines)

#     def _registered_address_filled(self, live_fill: dict) -> bool:
#         for key in ("address_registered.address_registered_city_id",
#                     "address_registered.address_registered_line1_id"):
#             if live_fill.get(key):
#                 return True
#         return False

#     def _build_continue_prompt(self, missing: list, merged_count: int) -> str:
#         header = "Got it, thank you! I still need a few more details.\n\n" if merged_count > 0 else "I still need some information from you.\n\n"
#         lines = [header + "Still needed:"]
#         for key in missing[:MAX_MISSING_DISPLAY]:
#             question = self.form_config.get_question(key)
#             label = self.form_config.get_label(key) or format_field_name(key)
#             lines.append(f"  • {question or label}")
#         if len(missing) > MAX_MISSING_DISPLAY:
#             lines.append(f"  • ... and {len(missing) - MAX_MISSING_DISPLAY} more")
#         lines.append("\nFeel free to share multiple fields at once.")
#         return "\n".join(lines)

#     def _build_sequential_prompt(self, field_key: str) -> str:
#         question = self.form_config.get_question(field_key)
#         if question:
#             return question
#         label = self.form_config.get_label(field_key) or format_field_name(field_key)
#         return f"Please provide your {label.lower()}."



























# chatbot/handlers/data_collection_handler.py
from __future__ import annotations
from typing import List
from collections import OrderedDict

from chatbot.core.states import State
from chatbot.handlers.base_handler import BaseHandler
from chatbot.utils.field_utils import (
    get_missing_mandatory_keys,
    format_field_name,
    filter_form_pf_fields,
    filter_user_facing_fields,
    get_registered_country,
    is_internal_split_field,
)
from chatbot.utils.address_utils import check_mailing_fields, copy_registered_to_mailing
from chatbot.utils.intent_detection import is_exit_intent
from chatbot.validation.field_validator import validate_field
from chatbot.validation.phone_validator import split_phone_parts

MAX_MISSING_DISPLAY = 6
MIN_EXTRACTED = 1
PHONE_FAX_FULL_FIELD_SUFFIXES = ("telephone", "phone", "mobile", "fax", "tel")

BOOLEAN_GROUP_SECTIONS = {"share_class", "investor_eligibility", "form_pf", "subscriber_type"}
NEVER_ASK_PREFIXES = ("investor_type.",)


class DataCollectionHandler(BaseHandler):

    def handle(self, session, user_input, user_id, session_id, debug=None):
        state = State.DATA_COLLECTION.value

        if is_exit_intent(user_input):
            msg = "Session ended. Your progress has been saved. Goodbye!"
            self._log_turn(session, user_input, msg, state)
            return msg, State.COMPLETE

        # After showing missing list, handle yes/no
        if session.get("_after_missing_list"):
            from chatbot.utils.intent_detection import is_negative
            if is_negative(user_input) or is_exit_intent(user_input):
                session.pop("_after_missing_list", None)
                msg = "Alright! Please wait while the provided information is added to the uploaded PDF. For any additional information or updates, refer to the notifications panel."
                self._log_turn(session, user_input, msg, state)
                return msg, State.COMPLETE
            session.pop("_after_missing_list", None)
            from chatbot.handlers.missing_fields_handler import MissingFieldsHandler
            handler = MissingFieldsHandler(self.engine)
            return handler.handle(session, user_input, user_id, session_id, debug)

        live_fill = session.setdefault("live_fill_flat", {})
        mandatory_flat = session.get("mandatory_flat", {})
        investor_type = session.get("investor_type", "")

        history = self._build_history(session)
        user_facing = filter_user_facing_fields(live_fill)

        extracted, latency, method = self.extractor.extract(
            user_input=user_input,
            conversation_history=history,
            live_fill_flat=user_facing,
            meta_form_keys=self.form_config.meta_form_keys,
            mandatory_flat=mandatory_flat,
            investor_type=investor_type,
        )

        debug and debug.log(
            "data_collection",
            f"Extracted {len(extracted)} fields via {method} in {latency:.2f}s",
            data={"fields": list(extracted.keys())},
        )

        merged_count = 0
        for key, value in extracted.items():
            if key not in live_fill:
                continue
            if is_internal_split_field(key):
                continue
            valid, err = validate_field(key, value)
            if valid or value in (True, False, None):
                if live_fill.get(key) in (None, ""):
                    live_fill[key] = value
                    merged_count += 1
                elif value not in (None, ""):
                    live_fill[key] = value
                    merged_count += 1

        self._populate_split_fields(live_fill, debug)

        # form_pf filtering for non-US investors
        registered_country = get_registered_country(live_fill)
        if registered_country and not session.get("_form_pf_filtered"):
            filtered = filter_form_pf_fields(live_fill, registered_country)
            if len(filtered) < len(live_fill):
                live_fill.clear()
                live_fill.update(filtered)
                for key in list(mandatory_flat.keys()):
                    if key not in live_fill:
                        del mandatory_flat[key]
                session["mandatory_flat"] = mandatory_flat
            session["_form_pf_filtered"] = True

        session["live_fill_flat"] = live_fill

        # Mailing address check — matches Lambda: fires when line1 OR city is filled,
        # but NOT during sequential fill (one field at a time can't reliably trigger it).
        # _in_sequential flag is set by SequentialFillHandler to suppress this check.
        if (
            check_mailing_fields(live_fill)
            and not session.get("_mailing_checked")
            and not session.get("_in_sequential")
            and self._registered_address_started(live_fill)
        ):
            msg = "Is your mailing address the same as your registered address? (yes / no)"
            self._log_turn(session, user_input, msg, state)
            return msg, State.MAILING_ADDRESS_CHECK

        missing_text = self._get_missing_text_mandatory(live_fill, mandatory_flat)
        missing_bool_groups = self._get_missing_bool_groups(live_fill, mandatory_flat, investor_type, session)

        # All mandatory done — go straight to MISSING_FIELDS_PROMPT (no "Thank you" message)
        if not missing_text and not missing_bool_groups:
            return self.engine.router.get_handler(State.MISSING_FIELDS_PROMPT).handle(
                session, user_input, user_id, session_id, debug
            )

        msg = "Do you have any other information you'd like to provide? (yes/no):"
        self._log_turn(session, user_input, msg, state)
        return msg, State.ANOTHER_INFO_PROMPT

    # ------------------------------------------------------------------

    def _get_missing_text_mandatory(self, live_fill: dict, mandatory_flat: dict) -> list:
        missing = []
        for key in mandatory_flat:
            section = key.split(".")[0] if "." in key else ""
            if section in BOOLEAN_GROUP_SECTIONS:
                continue
            if any(key.startswith(p) for p in NEVER_ASK_PREFIXES):
                continue
            val = live_fill.get(key)
            if val is None or val == "":
                missing.append(key)
        return missing

    def _get_missing_bool_groups(self, live_fill: dict, mandatory_flat: dict, investor_type: str, session: dict) -> dict:
        from collections import defaultdict
        groups = defaultdict(list)
        for key in mandatory_flat:
            section = key.split(".")[0] if "." in key else ""
            if section not in BOOLEAN_GROUP_SECTIONS:
                continue
            val = live_fill.get(key)
            if val is None:
                groups[section].append(key)
        return dict(groups)

    def _populate_split_fields(self, live_fill: dict, debug) -> None:
        for key, value in list(live_fill.items()):
            if not value or not isinstance(value, str):
                continue
            leaf = key.split(".")[-1]
            if not any(leaf.endswith(s) or leaf == s for s in PHONE_FAX_FULL_FIELD_SUFFIXES):
                continue
            parts = split_phone_parts(value)
            prefix = key.rsplit(".", 1)[0] if "." in key else ""
            split_prefix = "fax_part_" if "fax" in leaf else "telephone_part_"
            mapping = {
                f"{split_prefix}country_code": parts["country_code"],
                f"{split_prefix}1": parts["part1"],
                f"{split_prefix}2": parts["part2"],
                f"{split_prefix}3": parts["part3"],
            }
            for split_leaf, split_val in mapping.items():
                full_key = f"{prefix}.{split_leaf}" if prefix else split_leaf
                if full_key in live_fill:
                    live_fill[full_key] = split_val

    def _build_history(self, session: dict) -> str:
        log = session.get("conversation_log", [])
        lines = []
        for entry in log[-6:]:
            lines.append(f"User: {entry.get('user', '')}")
            lines.append(f"Bot: {entry.get('bot', '')}")
        return "\n".join(lines)

    def _registered_address_started(self, live_fill: dict) -> bool:
        """Fires when user has provided at least line1 or city — matches Lambda trigger."""
        for key in ("address_registered.address_registered_line1_id",
                    "address_registered.address_registered_city_id"):
            if live_fill.get(key):
                return True
        return False