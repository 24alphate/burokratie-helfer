"""Unit tests for ValidationService."""
import json
import pytest
from unittest.mock import MagicMock
from app.services.validation_service import ValidationService


def make_rule(rule_type: str, rule_value=None, msg_en="Error."):
    r = MagicMock()
    r.rule_type = rule_type
    r.rule_value = rule_value
    r.error_message = json.dumps({"en": msg_en, "de": "Fehler."})
    return r


class TestValidationService:
    svc = ValidationService()

    def test_required_empty_fails(self):
        rules = [make_rule("required")]
        result = self.svc.validate_answer("", rules)
        assert not result.is_valid
        assert len(result.errors) == 1

    def test_required_whitespace_fails(self):
        rules = [make_rule("required")]
        result = self.svc.validate_answer("   ", rules)
        assert not result.is_valid

    def test_required_with_value_passes(self):
        rules = [make_rule("required")]
        result = self.svc.validate_answer("Ahmed", rules)
        assert result.is_valid

    def test_max_length_passes(self):
        rules = [make_rule("max_length", "10")]
        result = self.svc.validate_answer("Hello", rules)
        assert result.is_valid

    def test_max_length_fails(self):
        rules = [make_rule("max_length", "3")]
        result = self.svc.validate_answer("Hello", rules)
        assert not result.is_valid

    def test_regex_postal_code_valid(self):
        rules = [make_rule("regex", r"^\d{5}$")]
        result = self.svc.validate_answer("10117", rules)
        assert result.is_valid

    def test_regex_postal_code_invalid(self):
        rules = [make_rule("regex", r"^\d{5}$")]
        result = self.svc.validate_answer("101", rules)
        assert not result.is_valid

    def test_regex_income_valid(self):
        rules = [make_rule("regex", r"^\d+(\.\d{1,2})?$")]
        assert self.svc.validate_answer("800", rules).is_valid
        assert self.svc.validate_answer("1250.50", rules).is_valid

    def test_regex_income_invalid(self):
        rules = [make_rule("regex", r"^\d+(\.\d{1,2})?$")]
        assert not self.svc.validate_answer("abc", rules).is_valid
        assert not self.svc.validate_answer("1250.123", rules).is_valid

    def test_iban_valid_german(self):
        rules = [make_rule("iban", "DE")]
        result = self.svc.validate_answer("DE89370400440532013000", rules)
        assert result.is_valid

    def test_iban_with_spaces_valid(self):
        rules = [make_rule("iban", "DE")]
        result = self.svc.validate_answer("DE89 3704 0044 0532 0130 00", rules)
        assert result.is_valid

    def test_iban_wrong_prefix_fails(self):
        rules = [make_rule("iban", "DE")]
        result = self.svc.validate_answer("GB29NWBK60161331926819", rules)
        assert not result.is_valid

    def test_date_range_valid(self):
        rules = [make_rule("date_range", json.dumps({"min_age": 16, "max_age": 120}))]
        result = self.svc.validate_answer("15.03.1985", rules)
        assert result.is_valid

    def test_date_range_too_young(self):
        rules = [make_rule("date_range", json.dumps({"min_age": 16, "max_age": 120}))]
        result = self.svc.validate_answer("01.01.2020", rules)
        assert not result.is_valid

    def test_multiple_rules_all_pass(self):
        rules = [make_rule("required"), make_rule("max_length", "50")]
        result = self.svc.validate_answer("Ahmed", rules)
        assert result.is_valid
        assert result.errors == []

    def test_multiple_rules_first_fails(self):
        rules = [make_rule("required"), make_rule("max_length", "50")]
        result = self.svc.validate_answer("", rules)
        assert not result.is_valid
        assert len(result.errors) >= 1

    def test_localized_error_message(self):
        rules = [make_rule("required", msg_en="First name is required.")]
        result = self.svc.validate_answer("", rules, language="en")
        assert "First name is required." in result.errors
