"""
Phase C/C1 — direct tests for the question-quality checker.

The checker (`app.services.question_quality.quality_flags`) is the single
mechanism that decides whether a rendered question is "strong" (no flags)
or "weak" (one or more flags). Every weak pattern from the Phase C spec
gets one positive test (the flag fires) and one negative test (a strong
question of the same type does NOT trip the flag).

What we are NOT testing here:
  - PDF extraction
  - Template matching
  - AI calls
  - Field IDs / answer keys

We are protecting the *labeling* of questions, nothing else.

Run with:  pytest tests/test_question_quality.py -v
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.question_quality import (
    NOUN_PHRASES,
    quality_flags,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def _fd(
    *,
    question: str = "What is your full name?",
    input_type: str = "text",
    question_source: str = "verified",
    guidance_example: dict | None = None,
    guidance_format_hint: dict | None = None,
):
    """
    Build a fake FieldDefinition-like object with only the attributes the
    checker reads. SimpleNamespace keeps the test free of Pydantic validation
    overhead and makes the assertions read straight off the test data.
    """
    if guidance_example is not None or guidance_format_hint is not None:
        guidance = SimpleNamespace(
            example=guidance_example or {},
            format_hint=guidance_format_hint or {},
            plain_language={},
        )
    else:
        guidance = None
    return SimpleNamespace(
        question={"en": question},
        input_type=input_type,
        question_source=question_source,
        guidance=guidance,
    )


def _entry(label: str = "ZZ_some_label"):
    return SimpleNamespace(original_label=label)


def _flags(fd, entry=None, locale="en", source="auto"):
    return quality_flags(fd, entry, user_language=locale, extraction_source=source)


# ── 1. too_short — fewer than 5 words ────────────────────────────────────────

class TestTooShort:
    def test_short_text_question_flagged(self):
        # 4 words, text field, AI source → flagged. Verified-source short
        # questions are exempt (Arabic/Turkish naturally hit 4 words).
        fd = _fd(question="What is your name", input_type="text", question_source="ai")
        assert "too_short" in _flags(fd, _entry())

    def test_short_verified_text_question_NOT_flagged(self):
        # Locale-fairness exemption: verified-source short questions pass.
        fd = _fd(question="ما هو اسمك", input_type="text", question_source="verified")
        assert "too_short" not in _flags(fd, _entry())

    def test_long_text_question_not_flagged(self):
        fd = _fd(question="What is your full legal name as on your ID?", input_type="text")
        assert "too_short" not in _flags(fd, _entry())

    def test_short_checkbox_NOT_flagged(self):
        # checkboxes are exempt from the 5-word minimum
        fd = _fd(question="Married?", input_type="checkbox")
        assert "too_short" not in _flags(fd, _entry())

    def test_short_signature_NOT_flagged(self):
        fd = _fd(question="Sign here", input_type="signature")
        assert "too_short" not in _flags(fd, _entry())


# ── 2. same_as_label — question text equals raw German label ─────────────────

class TestSameAsLabel:
    def test_question_equals_label_flagged(self):
        fd = _fd(question="Familienstand", input_type="text", question_source="ai")
        assert "same_as_label" in _flags(fd, _entry("Familienstand"))

    def test_question_differs_from_label_not_flagged(self):
        fd = _fd(question="What is your marital status?", input_type="text")
        assert "same_as_label" not in _flags(fd, _entry("Familienstand"))

    def test_long_label_match_does_not_fire(self):
        # Labels >= 30 chars are unlikely to be raw fields and not flagged
        long_label = "A very long label of 31 characters"
        fd = _fd(question=long_label, input_type="text", question_source="ai")
        assert "same_as_label" not in _flags(fd, _entry(long_label))


# ── 3. trailing_number — raw suffixes like " 04", " 08", " 13" ───────────────

class TestTrailingNumber:
    @pytest.mark.parametrize("suffix", [" 04", " 08", " 13", " 99", " 1"])
    def test_trailing_digit_flagged(self, suffix):
        fd = _fd(question=f"What is your starting location{suffix}", input_type="text")
        assert "trailing_number" in _flags(fd, _entry())

    def test_no_trailing_digits_not_flagged(self):
        fd = _fd(question="What is your starting location?", input_type="text")
        assert "trailing_number" not in _flags(fd, _entry())

    def test_digit_inside_question_not_flagged(self):
        fd = _fd(question="Was your first child born after 2010?", input_type="text")
        assert "trailing_number" not in _flags(fd, _entry())


# ── 4. contains_equals — question text contains "=" ──────────────────────────

class TestContainsEquals:
    def test_equals_in_question_flagged(self):
        fd = _fd(question="Zielort = Startort?", input_type="text")
        assert "contains_equals" in _flags(fd, _entry())

    def test_no_equals_not_flagged(self):
        fd = _fd(question="Is the destination the same as the start?", input_type="text")
        assert "contains_equals" not in _flags(fd, _entry())


# ── 5. noun_not_question — bare nouns / single words ─────────────────────────

class TestNounNotQuestion:
    @pytest.mark.parametrize("noun", [
        "Number / Count", "Number", "Count", "Day", "Month", "Year",
        "we", "Yes", "No", "Ja", "Nein",
    ])
    def test_known_noun_phrases_flagged(self, noun):
        # input_type="text" so too_short is also flagged, but we only assert noun_not_question here.
        fd = _fd(question=noun, input_type="text", question_source="ai")
        assert "noun_not_question" in _flags(fd, _entry())

    def test_full_question_not_flagged(self):
        fd = _fd(question="How many children live in your household?", input_type="number")
        assert "noun_not_question" not in _flags(fd, _entry())

    def test_noun_phrases_set_includes_required(self):
        for required in ("number / count", "we", "year", "month", "day"):
            assert required in NOUN_PHRASES


# ── 6. explicit_failure — "Translation unavailable" or ⚠ prefix ──────────────

class TestExplicitFailure:
    def test_translation_unavailable_flagged(self):
        fd = _fd(question="Translation unavailable: Tag", input_type="text", question_source="ai")
        assert "explicit_failure" in _flags(fd, _entry())

    def test_warning_prefix_flagged(self):
        fd = _fd(question="⚠ Could not translate this field", input_type="text", question_source="ai")
        assert "explicit_failure" in _flags(fd, _entry())

    def test_normal_question_not_flagged(self):
        fd = _fd(question="What is your full name?", input_type="text")
        assert "explicit_failure" not in _flags(fd, _entry())


# ── 7. date_missing_example — date field has no example in guidance ──────────

class TestDateMissingExample:
    def test_date_without_example_flagged(self):
        fd = _fd(question="What is your date of birth?", input_type="date")
        assert "date_missing_example" in _flags(fd, _entry())

    def test_date_with_example_not_flagged(self):
        fd = _fd(
            question="What is your date of birth?",
            input_type="date",
            guidance_example={"en": "15.03.1985"},
        )
        assert "date_missing_example" not in _flags(fd, _entry())

    def test_text_field_not_subject_to_date_check(self):
        fd = _fd(question="What is your name?", input_type="text")
        assert "date_missing_example" not in _flags(fd, _entry())


# ── 8. number_missing_example — number field has no example/format hint ──────

class TestNumberMissingExample:
    def test_number_no_guidance_AI_flagged(self):
        fd = _fd(question="How many people live with you?", input_type="number", question_source="ai")
        assert "number_missing_example" in _flags(fd, _entry())

    def test_number_with_example_not_flagged(self):
        fd = _fd(
            question="How many people live with you?",
            input_type="number",
            question_source="ai",
            guidance_example={"en": "3"},
        )
        assert "number_missing_example" not in _flags(fd, _entry())

    def test_number_with_format_hint_not_flagged(self):
        fd = _fd(
            question="What is the amount in Euros?",
            input_type="number",
            question_source="ai",
            guidance_format_hint={"en": "Use a dot or comma for cents"},
        )
        assert "number_missing_example" not in _flags(fd, _entry())

    def test_number_verified_source_not_flagged(self):
        # Verified questions are exempt — they vouch for their own quality.
        fd = _fd(question="Wie hoch?", input_type="number", question_source="verified")
        assert "number_missing_example" not in _flags(fd, _entry())


# ── 9. checkbox_not_yes_no — Phase C NEW ─────────────────────────────────────

class TestCheckboxNotYesNo:
    def test_checkbox_statement_flagged(self):
        # Bare statement, no "?", no instructional hint → flagged
        fd = _fd(question="Married", input_type="checkbox", question_source="ai")
        assert "checkbox_not_yes_no" in _flags(fd, _entry())

    def test_checkbox_question_not_flagged(self):
        fd = _fd(question="Are you married?", input_type="checkbox")
        assert "checkbox_not_yes_no" not in _flags(fd, _entry())

    def test_checkbox_arabic_question_mark_not_flagged(self):
        # Arabic question mark "؟" must be accepted equivalently.
        fd = _fd(question="هل أنت متزوج؟", input_type="checkbox")
        assert "checkbox_not_yes_no" not in _flags(fd, _entry())

    def test_checkbox_check_this_instruction_not_flagged(self):
        # "Check this if..." imperative form is also a valid checkbox phrasing.
        fd = _fd(
            question="Check this if you currently receive Bürgergeld",
            input_type="checkbox",
        )
        assert "checkbox_not_yes_no" not in _flags(fd, _entry())

    def test_checkbox_german_ankreuzen_instruction_not_flagged(self):
        fd = _fd(
            question="Ankreuzen wenn Sie aktuell Bürgergeld erhalten",
            input_type="checkbox",
        )
        assert "checkbox_not_yes_no" not in _flags(fd, _entry())

    def test_text_field_not_subject_to_checkbox_check(self):
        fd = _fd(question="Married", input_type="text", question_source="ai")
        assert "checkbox_not_yes_no" not in _flags(fd, _entry())


# ── 10. multiselect_missing_select_all — Phase C NEW ─────────────────────────

class TestMultiselectMissingSelectAll:
    def test_multiselect_without_select_all_flagged(self):
        fd = _fd(
            question="What benefits do you receive?",
            input_type="multiselect",
            question_source="ai",
        )
        assert "multiselect_missing_select_all" in _flags(fd, _entry())

    def test_multiselect_select_all_phrase_not_flagged(self):
        fd = _fd(
            question="Select all benefits you currently receive.",
            input_type="multiselect",
        )
        assert "multiselect_missing_select_all" not in _flags(fd, _entry())

    def test_multiselect_german_alle_zutreffenden_not_flagged(self):
        fd = _fd(
            question="Bitte alle zutreffenden Leistungen ankreuzen.",
            input_type="multiselect",
        )
        assert "multiselect_missing_select_all" not in _flags(fd, _entry())

    def test_radio_field_not_subject_to_multiselect_check(self):
        fd = _fd(
            question="What is your marital status?",
            input_type="radio",
            question_source="ai",
        )
        assert "multiselect_missing_select_all" not in _flags(fd, _entry())


# ── 11. verified_question_weak — Level 1 invariant ───────────────────────────

class TestVerifiedQuestionWeak:
    def test_verified_with_other_flags_marks_weak(self):
        # A verified question that ALSO trips another flag → critical bug.
        fd = _fd(question="Vorname", input_type="text", question_source="verified")
        flags = _flags(fd, _entry("Vorname"))
        assert "same_as_label" in flags
        assert "verified_question_weak" in flags

    def test_verified_without_other_flags_clean(self):
        fd = _fd(question="What is your full name?", input_type="text", question_source="verified")
        assert _flags(fd, _entry()) == []


# ── 12. template_field_not_verified — Level 1 invariant ──────────────────────

class TestTemplateFieldNotVerified:
    def test_verified_template_with_ai_question_flagged(self):
        fd = _fd(question="What is your name?", input_type="text", question_source="ai")
        flags = _flags(fd, _entry(), source="verified_template")
        assert "template_field_not_verified" in flags

    def test_verified_template_with_verified_question_not_flagged(self):
        fd = _fd(question="What is your name?", input_type="text", question_source="verified")
        flags = _flags(fd, _entry(), source="verified_template")
        assert "template_field_not_verified" not in flags

    def test_acroform_extraction_not_subject_to_invariant(self):
        # Outside Level 1, AI questions are allowed.
        fd = _fd(question="What is your name?", input_type="text", question_source="ai")
        flags = _flags(fd, _entry(), source="acroform")
        assert "template_field_not_verified" not in flags


# ── 13. Strong-question integration: a fully formed question is clean ─────────

class TestStrongQuestionsAreClean:
    def test_strong_text_question(self):
        fd = _fd(question="What is your full name as on your ID?", input_type="text", question_source="verified")
        assert _flags(fd, _entry("Name, Vorname")) == []

    def test_strong_date_question_with_example(self):
        fd = _fd(
            question="What is your date of birth?",
            input_type="date",
            question_source="verified",
            guidance_example={"en": "15.03.1985"},
        )
        assert _flags(fd, _entry("Geburtsdatum")) == []

    def test_strong_number_question_with_format(self):
        fd = _fd(
            question="What is the amount in Euros?",
            input_type="number",
            question_source="verified",
            guidance_format_hint={"en": "Number, e.g. 25.50"},
        )
        assert _flags(fd, _entry("Betrag")) == []

    def test_strong_checkbox_yes_no_question(self):
        fd = _fd(
            question="Are you currently receiving Bürgergeld?",
            input_type="checkbox",
            question_source="verified",
        )
        assert _flags(fd, _entry("Bürgergeld")) == []

    def test_strong_multiselect_with_hint(self):
        fd = _fd(
            question="Please select all benefits that you currently receive.",
            input_type="multiselect",
            question_source="verified",
        )
        assert _flags(fd, _entry("Leistungen")) == []
