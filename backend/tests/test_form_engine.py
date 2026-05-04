"""Unit tests for FormEngine — pure function, no DB needed."""
import pytest
from unittest.mock import MagicMock
from app.services.form_engine import FormEngine


def make_question(field_key: str, order_index: int, condition=None):
    q = MagicMock()
    q.field_key = field_key
    q.order_index = order_index
    q.condition = None
    if condition:
        import json
        q.condition = json.dumps(condition)
    return q


class TestEvaluateCondition:
    engine = FormEngine()

    def test_null_condition_always_true(self):
        assert self.engine.evaluate_condition(None, {}) is True

    def test_field_equals_match(self):
        cond = {"type": "field_equals", "field_key": "has_partner", "value": "yes"}
        assert self.engine.evaluate_condition(cond, {"has_partner": "yes"}) is True

    def test_field_equals_no_match(self):
        cond = {"type": "field_equals", "field_key": "has_partner", "value": "yes"}
        assert self.engine.evaluate_condition(cond, {"has_partner": "no"}) is False

    def test_field_equals_missing_field(self):
        cond = {"type": "field_equals", "field_key": "has_partner", "value": "yes"}
        assert self.engine.evaluate_condition(cond, {}) is False

    def test_field_not_equals_match(self):
        cond = {"type": "field_not_equals", "field_key": "employment_status", "value": "unemployed"}
        assert self.engine.evaluate_condition(cond, {"employment_status": "part_time"}) is True

    def test_field_not_equals_same_value(self):
        cond = {"type": "field_not_equals", "field_key": "employment_status", "value": "unemployed"}
        assert self.engine.evaluate_condition(cond, {"employment_status": "unemployed"}) is False

    def test_field_not_equals_missing_returns_false(self):
        cond = {"type": "field_not_equals", "field_key": "employment_status", "value": "unemployed"}
        assert self.engine.evaluate_condition(cond, {}) is False

    def test_field_in_match(self):
        cond = {"type": "field_in", "field_key": "status", "values": ["a", "b"]}
        assert self.engine.evaluate_condition(cond, {"status": "b"}) is True

    def test_field_in_no_match(self):
        cond = {"type": "field_in", "field_key": "status", "values": ["a", "b"]}
        assert self.engine.evaluate_condition(cond, {"status": "c"}) is False

    def test_and_all_true(self):
        cond = {
            "type": "and",
            "conditions": [
                {"type": "field_equals", "field_key": "a", "value": "1"},
                {"type": "field_equals", "field_key": "b", "value": "2"},
            ],
        }
        assert self.engine.evaluate_condition(cond, {"a": "1", "b": "2"}) is True

    def test_and_one_false(self):
        cond = {
            "type": "and",
            "conditions": [
                {"type": "field_equals", "field_key": "a", "value": "1"},
                {"type": "field_equals", "field_key": "b", "value": "2"},
            ],
        }
        assert self.engine.evaluate_condition(cond, {"a": "1", "b": "X"}) is False

    def test_unknown_type_defaults_true(self):
        cond = {"type": "unknown_future_type"}
        assert self.engine.evaluate_condition(cond, {}) is True


class TestGetNextQuestion:
    engine = FormEngine()

    def test_returns_first_unanswered(self):
        qs = [make_question("first_name", 1), make_question("last_name", 2)]
        result = self.engine.get_next_question(qs, {})
        assert result.field_key == "first_name"

    def test_skips_answered(self):
        qs = [make_question("first_name", 1), make_question("last_name", 2)]
        result = self.engine.get_next_question(qs, {"first_name": "Ahmed"})
        assert result.field_key == "last_name"

    def test_returns_none_when_complete(self):
        qs = [make_question("first_name", 1), make_question("last_name", 2)]
        result = self.engine.get_next_question(qs, {"first_name": "Ahmed", "last_name": "Ali"})
        assert result is None

    def test_conditional_question_skipped(self):
        qs = [
            make_question("has_partner", 1),
            make_question("partner_name", 2, condition={"type": "field_equals", "field_key": "has_partner", "value": "yes"}),
            make_question("iban", 3),
        ]
        # has_partner=no → partner_name should be skipped
        answers = {"has_partner": "no"}
        result = self.engine.get_next_question(qs, answers)
        assert result.field_key == "iban"

    def test_conditional_question_shown_when_condition_met(self):
        qs = [
            make_question("has_partner", 1),
            make_question("partner_name", 2, condition={"type": "field_equals", "field_key": "has_partner", "value": "yes"}),
            make_question("iban", 3),
        ]
        answers = {"has_partner": "yes"}
        result = self.engine.get_next_question(qs, answers)
        assert result.field_key == "partner_name"


class TestGetInvalidatedKeys:
    engine = FormEngine()

    def test_partner_questions_invalidated_on_no(self):
        qs = [
            make_question("has_partner", 1),
            make_question("partner_name", 2, condition={"type": "field_equals", "field_key": "has_partner", "value": "yes"}),
        ]
        old_answers = {"has_partner": "yes", "partner_name": "Sara"}
        new_answers = {"has_partner": "no"}
        invalidated = self.engine.get_invalidated_field_keys(qs, old_answers, new_answers)
        assert "partner_name" in invalidated

    def test_no_invalidation_on_same_value(self):
        qs = [
            make_question("has_partner", 1),
            make_question("partner_name", 2, condition={"type": "field_equals", "field_key": "has_partner", "value": "yes"}),
        ]
        old_answers = {"has_partner": "yes", "partner_name": "Sara"}
        new_answers = {"has_partner": "yes", "partner_name": "Sara"}
        invalidated = self.engine.get_invalidated_field_keys(qs, old_answers, new_answers)
        assert "partner_name" not in invalidated
