"""
Unit tests for state machine constants and enums.
"""
import pytest
from chatbot.core.states import (
    State,
    INVESTOR_TYPES,
    INVESTOR_TYPE_FILES,
    INVESTOR_TYPE_BOOLEAN_FIELD,
    INTERNAL_SPLIT_FIELD_PREFIXES,
    FORM_PF_FIELD_PREFIX,
    US_COUNTRY_VALUES,
)


def test_all_13_states_exist():
    expected = {
        "INIT",
        "UPDATE_EXISTING_PROMPT",
        "INVESTOR_TYPE_SELECT",
        "DATA_COLLECTION",
        "MISSING_FIELDS_PROMPT",
        "BOOLEAN_GROUP_SELECT",
        "SEQUENTIAL_FILL",
        "MAILING_ADDRESS_CHECK",
        "CONTINUE_PROMPT",
        "OPTIONAL_FIELDS_PROMPT",
        "ANOTHER_INFO_PROMPT",
        "SAVED_INFO_CHECK",
        "COMPLETE",
    }
    actual = {s.name for s in State}
    assert expected == actual, f"Missing states: {expected - actual}"


def test_investor_types_count():
    assert len(INVESTOR_TYPES) == 10


def test_investor_type_files_has_entry_per_type():
    for investor_type in INVESTOR_TYPES:
        assert investor_type in INVESTOR_TYPE_FILES, (
            f"No file mapping for investor type: {investor_type}"
        )


def test_investor_type_boolean_field_has_entry_per_type():
    for investor_type in INVESTOR_TYPES:
        assert investor_type in INVESTOR_TYPE_BOOLEAN_FIELD, (
            f"No boolean field for investor type: {investor_type}"
        )


def test_form_pf_prefix():
    assert FORM_PF_FIELD_PREFIX.startswith("form_pf")


def test_us_country_values_contains_usa():
    assert "usa" in US_COUNTRY_VALUES or "united states" in US_COUNTRY_VALUES


def test_internal_split_prefixes_non_empty():
    assert len(INTERNAL_SPLIT_FIELD_PREFIXES) > 0
