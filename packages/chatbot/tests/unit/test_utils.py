"""
Unit tests for utility modules:
    - dict_utils: flatten, unflatten, deep_update
    - field_utils: missing keys, optional fields, form_pf filtering
    - intent_detection: skip, exit, affirmative, negative
    - address_utils: is_address_field, copy_registered_to_mailing
    - phone_validator: validate_phone, split_phone_parts
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# dict_utils
# ─────────────────────────────────────────────────────────────────────────────

class TestFlattenDict:
    def test_flat_dict(self):
        from chatbot.utils.dict_utils import flatten_dict
        assert flatten_dict({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested_dict(self):
        from chatbot.utils.dict_utils import flatten_dict
        d = {"address": {"city": "NYC", "zip": "10001"}}
        assert flatten_dict(d) == {"address.city": "NYC", "address.zip": "10001"}

    def test_deeply_nested(self):
        from chatbot.utils.dict_utils import flatten_dict
        d = {"a": {"b": {"c": 42}}}
        assert flatten_dict(d) == {"a.b.c": 42}

    def test_empty(self):
        from chatbot.utils.dict_utils import flatten_dict
        assert flatten_dict({}) == {}


class TestUnflattenDict:
    def test_round_trip(self):
        from chatbot.utils.dict_utils import flatten_dict, unflatten_dict
        original = {"address": {"city": "NYC", "zip": "10001"}, "name": "Alice"}
        assert unflatten_dict(flatten_dict(original)) == original

    def test_simple_flat(self):
        from chatbot.utils.dict_utils import unflatten_dict
        assert unflatten_dict({"a": 1}) == {"a": 1}


class TestDeepUpdate:
    def test_shallow_update(self):
        from chatbot.utils.dict_utils import deep_update
        base = {"a": 1, "b": 2}
        assert deep_update(base, {"b": 99}) == {"a": 1, "b": 99}

    def test_nested_update(self):
        from chatbot.utils.dict_utils import deep_update
        base = {"addr": {"city": "NYC", "zip": "10001"}}
        deep_update(base, {"addr": {"zip": "10002"}})
        assert base == {"addr": {"city": "NYC", "zip": "10002"}}


# ─────────────────────────────────────────────────────────────────────────────
# field_utils
# ─────────────────────────────────────────────────────────────────────────────

class TestGetMissingMandatoryKeys:
    def test_all_filled(self):
        from chatbot.utils.field_utils import get_missing_mandatory_keys
        live = {"name": "Alice", "email": "a@b.com"}
        mandatory = {"name": None, "email": None}
        assert get_missing_mandatory_keys(live, mandatory) == []

    def test_some_missing(self):
        from chatbot.utils.field_utils import get_missing_mandatory_keys
        live = {"name": "Alice", "email": ""}
        mandatory = {"name": None, "email": None}
        assert get_missing_mandatory_keys(live, mandatory) == ["email"]

    def test_all_missing(self):
        from chatbot.utils.field_utils import get_missing_mandatory_keys
        live = {"name": None, "email": None}
        mandatory = {"name": None, "email": None}
        assert set(get_missing_mandatory_keys(live, mandatory)) == {"name", "email"}


class TestFilterFormPFFields:
    def test_us_investor_keeps_form_pf(self):
        from chatbot.utils.field_utils import filter_form_pf_fields
        live = {"name": "Alice", "form_pf.field1": "value"}
        result = filter_form_pf_fields(live, "USA")
        assert "form_pf.field1" in result

    def test_non_us_strips_form_pf(self):
        from chatbot.utils.field_utils import filter_form_pf_fields
        live = {"name": "Alice", "form_pf.field1": "value"}
        result = filter_form_pf_fields(live, "Canada")
        assert "form_pf.field1" not in result
        assert "name" in result

    def test_unknown_country_keeps_form_pf(self):
        from chatbot.utils.field_utils import filter_form_pf_fields
        live = {"name": "Alice", "form_pf.field1": "value"}
        result = filter_form_pf_fields(live, "")
        assert "form_pf.field1" in result


# ─────────────────────────────────────────────────────────────────────────────
# intent_detection
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentDetection:
    def test_affirmative(self):
        from chatbot.utils.intent_detection import is_affirmative
        for word in ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "1", "confirm"):
            assert is_affirmative(word), f"Expected affirmative: {word}"

    def test_negative(self):
        from chatbot.utils.intent_detection import is_negative
        for word in ("no", "n", "nope", "nah", "0", "2"):
            assert is_negative(word), f"Expected negative: {word}"

    def test_skip_intent(self):
        from chatbot.utils.intent_detection import is_skip_intent
        for word in ("skip", "n/a", "na", "not applicable", "none", "-"):
            assert is_skip_intent(word), f"Expected skip: {word}"

    def test_no_is_not_skip(self):
        """FIX: 'no' should NOT be a skip intent — it's a negative response."""
        from chatbot.utils.intent_detection import is_skip_intent
        assert not is_skip_intent("no")

    def test_exit_intent(self):
        from chatbot.utils.intent_detection import is_exit_intent
        for word in ("exit", "quit", "stop", "cancel", "bye", "done", "finish"):
            assert is_exit_intent(word), f"Expected exit: {word}"


# ─────────────────────────────────────────────────────────────────────────────
# address_utils
# ─────────────────────────────────────────────────────────────────────────────

class TestAddressUtils:
    def test_is_address_field_registered(self):
        from chatbot.utils.address_utils import is_address_field
        is_addr, addr_type, sub = is_address_field("address_registered.address_registered_city_id")
        assert is_addr
        assert addr_type == "registered"

    def test_is_address_field_mailing(self):
        from chatbot.utils.address_utils import is_address_field
        is_addr, addr_type, _ = is_address_field("address_mailing.address_mailing_city_id")
        assert is_addr
        assert addr_type == "mailing"

    def test_is_not_address_field(self):
        from chatbot.utils.address_utils import is_address_field
        is_addr, addr_type, _ = is_address_field("full_name")
        assert not is_addr

    def test_copy_registered_to_mailing(self):
        from chatbot.utils.address_utils import copy_registered_to_mailing
        live = {
            "address_registered.address_registered_city_id": "NYC",
            "address_mailing.address_mailing_city_id": None,
        }
        copied = copy_registered_to_mailing(live)
        assert live["address_mailing.address_mailing_city_id"] == "NYC"
        assert "address_mailing.address_mailing_city_id" in copied

    def test_copy_does_not_overwrite_existing_mailing(self):
        from chatbot.utils.address_utils import copy_registered_to_mailing
        live = {
            "address_registered.address_registered_city_id": "NYC",
            "address_mailing.address_mailing_city_id": "LA",
        }
        copy_registered_to_mailing(live)
        assert live["address_mailing.address_mailing_city_id"] == "LA"


# ─────────────────────────────────────────────────────────────────────────────
# phone_validator
# ─────────────────────────────────────────────────────────────────────────────

class TestPhoneValidator:
    def test_valid_us_phone(self):
        from chatbot.validation.phone_validator import validate_phone
        assert validate_phone("+1 212 555 1234")

    def test_valid_uk_phone(self):
        from chatbot.validation.phone_validator import validate_phone
        assert validate_phone("+44 20 7946 0958")

    def test_invalid_no_country_code(self):
        from chatbot.validation.phone_validator import validate_phone
        assert not validate_phone("2125551234")

    def test_invalid_too_short(self):
        from chatbot.validation.phone_validator import validate_phone
        assert not validate_phone("123")

    def test_split_us_phone(self):
        from chatbot.validation.phone_validator import split_phone_parts
        parts = split_phone_parts("+1 212 555 1234")
        assert parts["country_code"] == "1"
        assert parts["part1"] == "212"
