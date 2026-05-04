"""
Deterministic validation service. No AI involvement.
All rules are defined in the form template JSON.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


class ValidationService:
    def validate_answer(
        self,
        raw_answer: str,
        rules: list,  # list of ValidationRule ORM objects
        language: str = "en",
    ) -> ValidationResult:
        errors: list[str] = []
        for rule in rules:
            error = self._check_rule(rule, raw_answer, language)
            if error:
                errors.append(error)
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _check_rule(self, rule, value: str, language: str) -> Optional[str]:
        rule_type = rule.rule_type
        rule_value = rule.rule_value
        try:
            error_messages = json.loads(rule.error_message)
        except (json.JSONDecodeError, TypeError):
            error_messages = {}
        msg = error_messages.get(language) or error_messages.get("en", "Invalid value.")

        if rule_type == "required":
            if not value or not value.strip():
                return msg

        elif rule_type == "max_length":
            max_len = int(rule_value)
            if len(value) > max_len:
                return msg

        elif rule_type == "min_length":
            min_len = int(rule_value)
            if len(value) < min_len:
                return msg

        elif rule_type == "regex":
            pattern = rule_value
            if not re.fullmatch(pattern, value):
                return msg

        elif rule_type == "date_range":
            return self._check_date_range(value, rule_value, msg)

        elif rule_type == "iban":
            return self._check_iban(value, rule_value, msg)

        return None

    def _check_date_range(self, value: str, rule_value_json: Optional[str], msg: str) -> Optional[str]:
        try:
            parsed = self._parse_date(value)
        except ValueError:
            return msg

        if not rule_value_json:
            return None

        try:
            config = json.loads(rule_value_json)
        except (json.JSONDecodeError, TypeError):
            return None

        today = date.today()
        if "min_age" in config:
            max_birth_year = today.year - config["min_age"]
            if parsed.year > max_birth_year:
                return msg
        if "max_age" in config:
            min_birth_year = today.year - config["max_age"]
            if parsed.year < min_birth_year:
                return msg

        return None

    def _parse_date(self, value: str) -> date:
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {value}")

    def _check_iban(self, value: str, country_prefix: Optional[str], msg: str) -> Optional[str]:
        iban = value.replace(" ", "").upper()
        prefix = (country_prefix or "DE").upper()
        if not iban.startswith(prefix):
            return msg
        # German IBAN is 22 chars: DE + 2 check digits + 18 digits
        if len(iban) != 22:
            return msg
        if not re.fullmatch(r"[A-Z]{2}\d{20}", iban):
            return msg
        # Basic mod-97 check
        rearranged = iban[4:] + iban[:4]
        numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
        if int(numeric) % 97 != 1:
            return msg
        return None


validation_service = ValidationService()
