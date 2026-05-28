# chatbot/core/states.py
"""
State enum — the 13 conversation states.
"""

from enum import Enum


class State(str, Enum):
    INIT = "init"
    SAVED_INFO_CHECK = "saved_info_check"
    INVESTOR_TYPE_SELECT = "investor_type_select"
    DATA_COLLECTION = "data_collection"
    CONTINUE_PROMPT = "continue_prompt"
    UPDATE_EXISTING_PROMPT = "update_existing_prompt"
    ANOTHER_INFO_PROMPT = "another_info_prompt"
    MISSING_FIELDS_PROMPT = "missing_fields_prompt"
    MAILING_ADDRESS_CHECK = "mailing_address_check"
    SEQUENTIAL_FILL = "sequential_fill"
    BOOLEAN_GROUP_SELECT = "boolean_group_select"
    OPTIONAL_FIELDS_PROMPT = "optional_fields_prompt"
    COMPLETE = "complete"


# Investor types supported — matches Lambda exactly
INVESTOR_TYPES = [
    "Individual",
    "Partnership",
    "Corporation",
    "LLC",
    "Trust",
    "Non-Profit Organisations",
    "Fund/Fund of Funds",
    "IRA",
    "Government Bodies",
    "Education Institutions",
]

# Map investor type display name -> form_keys filename
INVESTOR_TYPE_FILES = {
    "Individual": "form_keys_individual.json",
    "Partnership": "form_keys_partnership.json",
    "Corporation": "form_keys_corporation.json",
    "LLC": "form_keys_llc.json",
    "Trust": "form_keys_trust.json",
    "Non-Profit Organisations": "form_keys_non_profit_organisations.json",
    "Fund/Fund of Funds": "form_keys_fund_or_fund_of_funds.json",
    "IRA": "form_keys_ira.json",
    "Government Bodies": "form_keys_government_bodies.json",
    "Education Institutions": "form_keys_education_institutions.json",
}

# Investor type -> boolean field auto-set in live_fill_flat
# Mirrors Lambda's auto-fill of e.g. investor_type.individual_check = True
INVESTOR_TYPE_BOOLEAN_FIELD = {
    "Individual": "investor_type.individual_check",
    "Partnership": "investor_type.partnership_check",
    "Corporation": "investor_type.corporation_check",
    "LLC": "investor_type.llc_check",
    "Trust": "investor_type.trust_check",
    "Non-Profit Organisations": "investor_type.non_profit_check",
    "Fund/Fund of Funds": "investor_type.fund_check",
    "IRA": "investor_type.ira_check",
    "Government Bodies": "investor_type.government_check",
    "Education Institutions": "investor_type.education_check",
}

# Fields that are split internally for PDF filling but NEVER shown to user
# Lambda: fax_part_ and telephone_part_ fields never shown to user
INTERNAL_SPLIT_FIELD_PREFIXES = (
    "telephone_part_",
    "fax_part_",
)

# form_pf fields are only applicable to US investors
FORM_PF_FIELD_PREFIX = "form_pf"

# Countries considered US for form_pf purposes
US_COUNTRY_VALUES = {
    "united states",
    "us",
    "usa",
    "u.s.a",
    "u.s.",
    "united states of america",
}
