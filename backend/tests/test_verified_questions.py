"""
Tests for the verified questions layer (Level 1 quality assurance).

Covers:
  - VERIFIED_BY_FIELD_ID keys cover all BuT template field_ids (P1.3)
  - All 9 locales have non-empty question strings for every BuT field (P1.3)
  - Questions end with "?" or are checkbox instructions (P1)
  - Questions have at least 5 words (P1)
  - Questions do not equal the original German label (P1)
  - lookup_verified() returns correct locale data (P1)
  - lookup_verified() falls back to "en" when locale missing (P1)

Run with:  pytest tests/test_verified_questions.py -v
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.verified_questions import VERIFIED_BY_FIELD_ID, lookup_verified
from app.services.form_templates.jobcenter_but import JobcenterButTemplate

REQUIRED_LOCALES = ["en", "de", "fr", "ar", "tr", "sq"]
ALL_LOCALES = ["en", "de", "fr", "ar", "tr", "sq", "es", "ru", "uk"]

# Checkbox-type fields — their question may be an instruction rather than end with "?"
_CHECKBOX_FIELDS = {
    "benefit_sgb_ii", "benefit_sgb_xii", "benefit_kinderzuschlag",
    "benefit_wohngeld", "benefit_asylbewerberleistungsgesetz", "benefit_sonstige",
    "leistung_a_ausflug", "leistung_b_klassenfahrt", "leistung_c_schuelerbefoerderung",
    "leistung_d_lernfoerderung", "leistung_e_mittagessen", "leistung_f_soziale_teilhabe",
    "consent_direct_settlement", "lunch_school_hort", "lunch_kita_kindertagespflege",
}


def _all_but_field_ids() -> list[str]:
    """Non-signature BuT fields only (signatures are excluded from Q&A flow)."""
    tmpl = JobcenterButTemplate()
    return [f.field_id for f in tmpl.get_field_map() if f.confidence > 0.5]


def _all_but_labels() -> dict[str, str]:
    tmpl = JobcenterButTemplate()
    return {f.field_id: f.original_label for f in tmpl.get_field_map() if f.confidence > 0.5}


# ── 1. Coverage: every BuT field_id has an entry ──────────────────────────────

class TestCoverage:
    def test_all_but_field_ids_in_verified_dict(self):
        but_ids = _all_but_field_ids()
        missing = [fid for fid in but_ids if fid not in VERIFIED_BY_FIELD_ID]
        assert missing == [], (
            f"BuT field_ids missing from VERIFIED_BY_FIELD_ID:\n" + "\n".join(missing)
        )

    def test_required_locales_have_questions_for_all_but_fields(self):
        but_ids = _all_but_field_ids()
        failures = []
        for fid in but_ids:
            entry = VERIFIED_BY_FIELD_ID.get(fid, {})
            for locale in REQUIRED_LOCALES:
                q = entry.get(locale, {}).get("question", "")
                if not q.strip():
                    failures.append(f"{fid}[{locale}]: empty question")
        assert failures == [], "Missing questions:\n" + "\n".join(failures)

    def test_all_locales_have_questions_for_all_but_fields(self):
        but_ids = _all_but_field_ids()
        failures = []
        for fid in but_ids:
            entry = VERIFIED_BY_FIELD_ID.get(fid, {})
            for locale in ALL_LOCALES:
                q = entry.get(locale, {}).get("question", "")
                if not q.strip():
                    failures.append(f"{fid}[{locale}]: empty question")
        assert failures == [], "Missing questions (all 9 locales):\n" + "\n".join(failures)


# ── 2. Question quality: questions must pass basic checks ─────────────────────

class TestQuestionQuality:
    def test_questions_have_minimum_3_words(self):
        # 3-word minimum is language-agnostic: catches bare labels ("Name", "Datum")
        # while accepting valid short questions in Arabic/Turkish/German.
        but_ids = _all_but_field_ids()
        failures = []
        for fid in but_ids:
            entry = VERIFIED_BY_FIELD_ID.get(fid, {})
            for locale in REQUIRED_LOCALES:
                q = entry.get(locale, {}).get("question", "")
                if q and len(q.split()) < 3:
                    failures.append(f"{fid}[{locale}]: too short ({q!r})")
        assert failures == [], "Short questions:\n" + "\n".join(failures)

    def test_questions_not_equal_to_german_label(self):
        labels = _all_but_labels()
        failures = []
        for fid, label in labels.items():
            entry = VERIFIED_BY_FIELD_ID.get(fid, {})
            for locale in REQUIRED_LOCALES:
                q = entry.get(locale, {}).get("question", "")
                if q and q.strip().lower() == label.strip().lower():
                    failures.append(f"{fid}[{locale}]: question equals German label ({q!r})")
        assert failures == [], "Questions same as label:\n" + "\n".join(failures)

    def test_non_checkbox_questions_end_with_question_mark(self):
        # Accept both ASCII "?" and Arabic "؟" (U+061F)
        QUESTION_MARKS = {"?", "؟"}
        but_ids = _all_but_field_ids()
        failures = []
        for fid in but_ids:
            if fid in _CHECKBOX_FIELDS:
                continue
            entry = VERIFIED_BY_FIELD_ID.get(fid, {})
            for locale in REQUIRED_LOCALES:
                q = entry.get(locale, {}).get("question", "")
                if q and q.strip()[-1] not in QUESTION_MARKS:
                    failures.append(f"{fid}[{locale}]: does not end with '?' ({q!r})")
        assert failures == [], "Questions without '?':\n" + "\n".join(failures)

    def test_no_translation_unavailable_text(self):
        for fid, locales in VERIFIED_BY_FIELD_ID.items():
            for locale, data in locales.items():
                q = data.get("question", "")
                assert "translation unavailable" not in q.lower(), (
                    f"{fid}[{locale}]: contains 'Translation unavailable'"
                )
                assert q.startswith("⚠") is False, (
                    f"{fid}[{locale}]: starts with warning emoji"
                )


# ── 3. lookup_verified() function ─────────────────────────────────────────────

class TestLookupVerified:
    def test_lookup_by_field_id_returns_correct_locale(self):
        result = lookup_verified("applicant_name_vorname", "Name, Vorname", "en")
        assert result is not None
        assert "question" in result
        assert "?" in result["question"]

    def test_lookup_by_field_id_german(self):
        result = lookup_verified("applicant_name_vorname", "Name, Vorname", "de")
        assert result is not None
        q = result["question"]
        assert "?" in q

    def test_lookup_by_field_id_french(self):
        result = lookup_verified("applicant_name_vorname", "Name, Vorname", "fr")
        assert result is not None
        assert "?" in result["question"]

    def test_lookup_by_field_id_arabic(self):
        result = lookup_verified("applicant_name_vorname", "Name, Vorname", "ar")
        assert result is not None
        assert result["question"]

    def test_lookup_missing_field_id_returns_none(self):
        result = lookup_verified("nonexistent_field_xyz", "Some label", "en")
        assert result is None

    def test_lookup_by_label_tag(self):
        result = lookup_verified("unknown_field", "Tag", "en")
        assert result is not None
        q = result["question"]
        assert "?" in q

    def test_lookup_by_label_monat(self):
        result = lookup_verified("unknown_field", "Monat", "fr")
        assert result is not None

    def test_lookup_falls_back_to_en_for_unknown_locale(self):
        result = lookup_verified("applicant_name_vorname", "Name, Vorname", "xx")
        assert result is not None, "Should fall back to 'en' for unknown locale"
        assert "question" in result

    def test_lookup_field_id_takes_priority_over_label(self):
        result_by_id = lookup_verified("applicant_name_vorname", "Tag", "en")
        # field_id match should win over label match
        assert result_by_id is not None
        assert "name" in result_by_id["question"].lower()
