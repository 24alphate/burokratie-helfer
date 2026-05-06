"""
Tests for the deterministic field-map-first PDF pipeline.

Covers:
  - PDF type detection
  - AcroForm field extraction (field_id, field_type, options, page, bbox)
  - Anti-hallucination validator
  - Language separation invariants
  - Answer mapping (option.value = PDF language)
  - Final PDF field map round-trip
  - Confidence thresholds (show_question gate)
  - Hallucination edge cases (extra fields returned by AI)
  - AnalysisReport accuracy metrics
  - Golden snapshot for real Jobcenter PDF (when file is available)

Run with:  pytest tests/test_pdf_pipeline.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.pdf_pipeline import (
    CONF_REVIEW_MIN,
    CONF_SHOW_MIN,
    AnalysisReport,
    ExtractionResult,
    HallucinationReport,
    build_analysis_report,
    detect_pdf_type,
    extract_acroform_fields,
    extract_field_map,
    field_map_to_defs,
    validate_no_hallucinations,
    FieldMapEntry,
)


# ── Minimal PDF fixtures ──────────────────────────────────────────────────────

def _make_acroform_pdf() -> bytes:
    """Minimal fillable PDF with two AcroForm fields: Vorname (text) + Familienstand (radio)."""
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Annots [6 0 R 7 0 R 8 0 R] >> endobj
5 0 obj << /Fields [6 0 R 7 0 R] /DR << >> >> endobj
6 0 obj << /Type /Annot /Subtype /Widget /FT /Tx
  /T (Vorname) /Rect [50 750 250 770] /P 3 0 R >> endobj
7 0 obj << /FT /Btn /Ff 32768 /T (Familienstand) /Kids [8 0 R] >> endobj
8 0 obj << /Type /Annot /Subtype /Widget /Parent 7 0 R
  /Rect [50 700 70 720] /P 3 0 R
  /AP << /N << /ledig 9 0 R /Off 9 0 R >> >> >> endobj
9 0 obj << >> endobj
xref
0 10
0000000000 65535 f\r
0000000009 00000 n\r
0000000068 00000 n\r
0000000125 00000 n\r
0000000000 65535 f\r
0000000270 00000 n\r
0000000320 00000 n\r
0000000430 00000 n\r
0000000540 00000 n\r
0000000700 00000 n\r
trailer << /Size 10 /Root 1 0 R >>
startxref
720
%%EOF"""


def _make_flat_pdf() -> bytes:
    """Minimal flat (non-fillable) PDF with text content."""
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 120 >>
stream
BT /F1 12 Tf 50 750 Td
(Name: ________________________________) Tj
0 -30 Td
(Geburtsdatum: ________________________) Tj ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f\r
0000000009 00000 n\r
0000000062 00000 n\r
0000000119 00000 n\r
0000000280 00000 n\r
0000000450 00000 n\r
trailer << /Size 6 /Root 1 0 R >>
startxref
540
%%EOF"""


# ── 1. PDF type detection ─────────────────────────────────────────────────────

class TestDetectPdfType:
    def test_acroform_detected(self):
        pdf_type, pages = detect_pdf_type(_make_acroform_pdf())
        assert pdf_type == "acroform"
        assert pages >= 1

    def test_flat_pdf_detected(self):
        pdf_type, pages = detect_pdf_type(_make_flat_pdf())
        assert pdf_type in ("flat", "scanned")
        assert pages == 1

    def test_non_pdf_bytes(self):
        pdf_type, pages = detect_pdf_type(b"This is not a PDF")
        assert pdf_type == "unknown"
        assert pages == 0

    def test_empty_bytes(self):
        pdf_type, pages = detect_pdf_type(b"")
        assert pdf_type == "unknown"
        assert pages == 0

    def test_no_acroform_returns_flat_or_scanned(self):
        minimal = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f\r\n0000000009 00000 n\r\n"
            b"0000000058 00000 n\r\n0000000115 00000 n\r\n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n200\n%%EOF"
        )
        pdf_type, _ = detect_pdf_type(minimal)
        assert pdf_type != "acroform"


# ── 2. AcroForm field extraction ──────────────────────────────────────────────

class TestAcroFormExtraction:
    def test_extracts_text_field(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        assert "Vorname" in {f.field_id for f in fields}

    def test_extracts_radio_group(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        assert any(f.field_id == "Familienstand" and f.field_type == "radio" for f in fields)

    def test_radio_field_has_options(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        familienstand = next((f for f in fields if f.field_id == "Familienstand"), None)
        if familienstand:
            assert isinstance(familienstand.options, list)

    def test_field_types_are_valid(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        valid_types = {"text", "date", "number", "checkbox", "radio",
                       "select", "multiselect", "signature"}
        for f in fields:
            assert f.field_type in valid_types

    def test_source_is_acroform_and_confidence_1(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.source == "acroform"
            assert f.confidence == 1.0

    def test_source_page_is_positive(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.source_page >= 1

    def test_source_text_is_field_name(self):
        """AcroForm widget name IS the grounding text."""
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.source_text != "", f"Field {f.field_id} has empty source_text"

    def test_reason_is_pdf_field(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.reason == "pdf_field"

    def test_no_fields_for_non_pdf(self):
        assert extract_acroform_fields(b"not a pdf") == []

    def test_no_fields_for_flat_pdf(self):
        assert extract_acroform_fields(_make_flat_pdf()) == []

    def test_field_ids_are_unique(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        ids = [f.field_id for f in fields]
        assert len(ids) == len(set(ids))

    def test_field_ids_are_non_empty(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.field_id.strip() != ""


# ── 3. extract_field_map entry point ─────────────────────────────────────────

class TestExtractFieldMap:
    def test_acroform_pdf_returns_acroform_type(self):
        result = extract_field_map(_make_acroform_pdf())
        assert result.pdf_type == "acroform"
        assert len(result.fields) > 0

    def test_total_pages_populated(self):
        result = extract_field_map(_make_acroform_pdf())
        assert result.total_pages >= 1

    def test_non_pdf_returns_empty(self):
        result = extract_field_map(b"garbage")
        assert result.fields == []

    def test_field_map_entries_have_required_attrs(self):
        result = extract_field_map(_make_acroform_pdf())
        for entry in result.fields:
            assert isinstance(entry, FieldMapEntry)
            assert entry.field_id
            assert entry.field_type
            assert entry.source_page >= 1
            assert 0.0 <= entry.confidence <= 1.0
            assert entry.source_text != ""


# ── 4. Anti-hallucination validator ───────────────────────────────────────────

class TestHallucinationValidator:
    def _make_field_map(self) -> list[FieldMapEntry]:
        return [
            FieldMapEntry("Vorname", "Vorname", "text", 1),
            FieldMapEntry("Familienstand", "Familienstand", "radio", 1,
                          options=["ledig", "verheiratet", "geschieden"]),
            FieldMapEntry("IBAN", "IBAN", "text", 2),
        ]

    def test_clean_translations_pass(self):
        report = validate_no_hallucinations(self._make_field_map(), {
            "Vorname":       {"question": "First name?", "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "Marital status?", "explanation": "",
                              "translated_options": {"ledig": "Single"}},
            "IBAN":          {"question": "Your IBAN?", "explanation": "", "translated_options": {}},
        })
        assert report.is_clean
        assert report.invented == []
        assert report.missing == []

    def test_invented_field_is_discarded(self):
        report = validate_no_hallucinations(self._make_field_map(), {
            "Vorname":       {"question": "q", "explanation": "", "translated_options": {}},
            "ERFUNDEN":      {"question": "Invented!", "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "q", "explanation": "", "translated_options": {}},
            "IBAN":          {"question": "q", "explanation": "", "translated_options": {}},
        })
        assert not report.is_clean
        assert "ERFUNDEN" in report.invented
        assert "ERFUNDEN" not in report.cleaned_translations

    def test_multiple_invented_fields_all_discarded(self):
        report = validate_no_hallucinations(self._make_field_map(), {
            "Vorname":    {"question": "q", "explanation": "", "translated_options": {}},
            "GhostField1": {"question": "g1", "explanation": "", "translated_options": {}},
            "GhostField2": {"question": "g2", "explanation": "", "translated_options": {}},
        })
        assert not report.is_clean
        assert "GhostField1" in report.invented
        assert "GhostField2" in report.invented
        assert "GhostField1" not in report.cleaned_translations
        assert "GhostField2" not in report.cleaned_translations

    def test_missing_field_gets_raw_label_fallback(self):
        report = validate_no_hallucinations(self._make_field_map(), {
            "Vorname": {"question": "First name?", "explanation": "", "translated_options": {}},
        })
        assert "Familienstand" in report.missing
        assert "IBAN" in report.missing
        assert report.cleaned_translations["Familienstand"]["question"] == "Familienstand"
        assert report.cleaned_translations["IBAN"]["question"] == "IBAN"

    def test_missing_field_backfill_preserves_options(self):
        report = validate_no_hallucinations(self._make_field_map(), {})
        opts = report.cleaned_translations["Familienstand"]["translated_options"]
        assert opts.get("ledig") == "ledig"
        assert opts.get("verheiratet") == "verheiratet"

    def test_empty_translations_all_backfilled(self):
        report = validate_no_hallucinations(self._make_field_map(), {})
        assert report.is_clean
        assert set(report.cleaned_translations.keys()) == {"Vorname", "Familienstand", "IBAN"}

    def test_output_has_exactly_one_entry_per_field(self):
        report = validate_no_hallucinations(self._make_field_map(), {
            "Vorname":       {"question": "q", "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "q", "explanation": "", "translated_options": {}},
            "IBAN":          {"question": "q", "explanation": "", "translated_options": {}},
            "INVENTED":      {"question": "Fake!", "explanation": "", "translated_options": {}},
        })
        assert len(report.cleaned_translations) == 3
        assert "INVENTED" not in report.cleaned_translations


# ── 5. Hallucination scenarios — explicit failure cases ────────────────────────

class TestHallucinationScenarios:
    """
    The AI may try to return fields that were not in the PDF.
    These tests verify that every invented key is discarded and logged.
    """

    def test_extra_field_discarded_and_logged(self):
        """
        Extracted: ["name", "birth_date", "address"]
        AI returns: ["name", "birth_date", "address", "monthly_income"]
        monthly_income must be discarded.
        """
        field_map = [
            FieldMapEntry("name", "Name", "text", 1),
            FieldMapEntry("birth_date", "Geburtsdatum", "date", 1),
            FieldMapEntry("address", "Adresse", "text", 1),
        ]
        translations = {
            "name":          {"question": "What is your name?", "explanation": "", "translated_options": {}},
            "birth_date":    {"question": "Date of birth?", "explanation": "", "translated_options": {}},
            "address":       {"question": "What is your address?", "explanation": "", "translated_options": {}},
            "monthly_income": {"question": "How much rent do you pay?", "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert "monthly_income" in report.invented, "Invented key must be in report.invented"
        assert "monthly_income" not in report.cleaned_translations, "Invented key must be removed"
        assert len(report.cleaned_translations) == 3, "Exactly 3 real fields must remain"

    def test_zero_real_fields_all_invented(self):
        """If AI invents everything and PDF has fields, all AI output is discarded."""
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        translations = {
            "InventedA": {"question": "q", "explanation": "", "translated_options": {}},
            "InventedB": {"question": "q", "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert not report.is_clean
        assert "InventedA" in report.invented
        assert "InventedB" in report.invented
        # Vorname must be backfilled with its raw label
        assert "Vorname" in report.cleaned_translations
        assert report.cleaned_translations["Vorname"]["question"] == "Vorname"
        assert len(report.cleaned_translations) == 1

    def test_count_is_always_field_map_count(self):
        """
        After validation, len(cleaned_translations) == len(field_map).
        No more, no less — no matter what AI returned.
        """
        field_map = [
            FieldMapEntry("A", "A", "text", 1),
            FieldMapEntry("B", "B", "text", 1),
        ]
        # AI returns 5 keys, only 1 of which is real
        translations = {k: {"question": "q", "explanation": "", "translated_options": {}}
                        for k in ["A", "Fake1", "Fake2", "Fake3", "Fake4"]}
        report = validate_no_hallucinations(field_map, translations)
        assert len(report.cleaned_translations) == len(field_map)

    def test_invented_count_in_report(self):
        field_map = [FieldMapEntry("X", "X", "text", 1)]
        translations = {
            "X":     {"question": "q", "explanation": "", "translated_options": {}},
            "GHOST": {"question": "q", "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert len(report.invented) == 1
        assert "GHOST" in report.invented


# ── 6. Confidence thresholds ───────────────────────────────────────────────────

class TestConfidenceThresholds:
    """
    show_question gate:
        conf >= 0.90  → show_question=True,  needs_review=False
        0.70 ≤ conf < 0.90 → show_question=True,  needs_review=True
        conf < 0.70   → show_question=False
    """

    def _defs(self, conf: float, source: str = "pdfplumber"):
        fm = [FieldMapEntry("X", "X label", "text", 1, confidence=conf, source=source)]
        tr = validate_no_hallucinations(fm, {})
        return field_map_to_defs(fm, tr.cleaned_translations, set(), "en", "de")

    def test_high_confidence_acroform_shows_no_review(self):
        defs = self._defs(1.0, source="acroform")
        assert defs[0].show_question is True
        assert defs[0].needs_review is False

    def test_medium_confidence_shows_with_review(self):
        defs = self._defs(0.75, source="pdfplumber")
        assert defs[0].show_question is True
        assert defs[0].needs_review is True

    def test_at_boundary_0_90_acroform_no_review(self):
        defs = self._defs(0.90, source="acroform")
        assert defs[0].show_question is True
        assert defs[0].needs_review is False

    def test_just_below_review_threshold(self):
        defs = self._defs(0.89, source="acroform")
        assert defs[0].show_question is True
        assert defs[0].needs_review is True

    def test_at_show_min_boundary_shows(self):
        defs = self._defs(CONF_SHOW_MIN)
        assert defs[0].show_question is True

    def test_just_below_show_min_blocked(self):
        defs = self._defs(CONF_SHOW_MIN - 0.01)
        assert defs[0].show_question is False

    def test_very_low_confidence_blocked(self):
        defs = self._defs(0.50)
        assert defs[0].show_question is False

    def test_blocked_field_still_in_output(self):
        """Blocked fields appear in the list so the UI can show a count."""
        defs = self._defs(0.50)
        assert len(defs) == 1
        assert defs[0].show_question is False


# ── 7. Source grounding metadata ───────────────────────────────────────────────

class TestSourceGrounding:
    """Every returned FieldDefinition must carry verifiable grounding metadata."""

    def test_source_text_populated_for_acroform(self):
        fm = extract_acroform_fields(_make_acroform_pdf())
        tr = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, tr.cleaned_translations, set(), "en", "de")
        for d in defs:
            assert d.source_text != "", f"{d.key} has empty source_text"

    def test_reason_is_pdf_field(self):
        fm = extract_acroform_fields(_make_acroform_pdf())
        tr = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, tr.cleaned_translations, set(), "en", "de")
        for d in defs:
            assert d.reason == "pdf_field"

    def test_question_type_matches_reason(self):
        fm = extract_acroform_fields(_make_acroform_pdf())
        tr = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, tr.cleaned_translations, set(), "en", "de")
        for d in defs:
            assert d.question_type == d.reason


# ── 8. Language separation ────────────────────────────────────────────────────

class TestLanguageSeparation:
    def test_field_option_value_is_pdf_language(self):
        from app.schemas.document import FieldOption
        opt = FieldOption(value="verheiratet", label="Marié(e)")
        assert opt.value == "verheiratet"
        assert opt.label == "Marié(e)"

    def test_document_language_is_pdf_language(self):
        from app.schemas.document import FieldDefinition, FieldOption
        fd = FieldDefinition(
            key="Familienstand",
            question={"fr": "Quelle est votre situation familiale ?"},
            explanation={"fr": ""},
            input_type="radio",
            options=[FieldOption(value="ledig", label="Célibataire"),
                     FieldOption(value="verheiratet", label="Marié(e)")],
            original_label="Familienstand",
            document_language="de",
            source_page=1,
            order=1,
            is_prefilled=False,
        )
        assert fd.document_language == "de"
        assert fd.options[0].value == "ledig"
        assert fd.options[1].label == "Marié(e)"


# ── 9. Answer → PDF field mapping ─────────────────────────────────────────────

class TestAnswerMapping:
    def test_choice_raw_answer_is_pdf_value(self):
        from app.api.v1.documents import CHOICE_TYPES
        assert "radio" in CHOICE_TYPES
        assert "checkbox" in CHOICE_TYPES
        assert "select" in CHOICE_TYPES
        assert "multiselect" in CHOICE_TYPES

    def test_every_extracted_field_has_a_question(self):
        field_map = [
            FieldMapEntry("Vorname", "Vorname", "text", 1),
            FieldMapEntry("IBAN",    "IBAN",    "text", 1),
        ]
        report = validate_no_hallucinations(field_map, {})
        assert len(report.cleaned_translations) == len(field_map)

    def test_no_question_without_pdf_field(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        report = validate_no_hallucinations(field_map, {
            "Vorname":  {"question": "q", "explanation": "", "translated_options": {}},
            "INVENTED": {"question": "Ghost", "explanation": "", "translated_options": {}},
        })
        assert "INVENTED" not in report.cleaned_translations
        assert len(report.cleaned_translations) == 1


# ── 10. field_map_to_defs round-trip ─────────────────────────────────────────

class TestFieldMapToDefs:
    def test_one_def_per_field(self):
        field_map = [
            FieldMapEntry("Vorname",       "Vorname",       "text",  1),
            FieldMapEntry("Familienstand", "Familienstand", "radio", 1,
                          options=["ledig", "verheiratet"]),
        ]
        report = validate_no_hallucinations(field_map, {
            "Vorname": {"question": "First name?", "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "Marital status?", "explanation": "",
                              "translated_options": {"ledig": "Single", "verheiratet": "Married"}},
        })
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert len(defs) == 2

    def test_options_have_pdf_values_and_translated_labels(self):
        field_map = [FieldMapEntry("Familienstand", "Familienstand", "radio", 1,
                                   options=["ledig", "verheiratet"])]
        report = validate_no_hallucinations(field_map, {
            "Familienstand": {"question": "Situation de famille ?", "explanation": "",
                              "translated_options": {"ledig": "Célibataire", "verheiratet": "Marié(e)"}},
        })
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "fr", "de")
        assert defs[0].options[0].value == "ledig"
        assert defs[0].options[0].label == "Célibataire"

    def test_prefilled_field_marked(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1, current_value="Max")]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, {"Vorname"}, "en", "de")
        assert defs[0].is_prefilled is True

    def test_acroform_confidence_1_not_needs_review(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1, confidence=1.0, source="acroform")]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert defs[0].needs_review is False
        assert defs[0].show_question is True

    def test_pdfplumber_needs_review(self):
        field_map = [FieldMapEntry("X", "X", "text", 1, confidence=0.75, source="pdfplumber")]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert defs[0].needs_review is True
        assert defs[0].show_question is True

    def test_document_language_preserved(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "fr", "de")
        assert defs[0].document_language == "de"

    def test_question_in_user_language(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        report = validate_no_hallucinations(field_map, {
            "Vorname": {"question": "Quel est votre prénom ?", "explanation": "", "translated_options": {}},
        })
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "fr", "de")
        assert "fr" in defs[0].question
        assert defs[0].question["fr"] == "Quel est votre prénom ?"


# ── 11. AnalysisReport accuracy metrics ───────────────────────────────────────

class TestAnalysisReport:
    def _make_extraction(self, fields: list[FieldMapEntry]) -> ExtractionResult:
        return ExtractionResult(pdf_type="acroform", fields=fields, total_pages=1)

    def test_grounding_rate_always_100(self):
        fm = [FieldMapEntry("A", "A", "text", 1, confidence=1.0, source="acroform")]
        hr = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, hr.cleaned_translations, set(), "en", "de")
        report = build_analysis_report(self._make_extraction(fm), defs, hr)
        assert report.grounding_rate == "100%"
        assert report.grounding_ok is True

    def test_questions_shown_equals_shown_fields(self):
        fm = [
            FieldMapEntry("A", "A", "text", 1, confidence=1.0,  source="acroform"),
            FieldMapEntry("B", "B", "text", 1, confidence=0.75, source="pdfplumber"),
            FieldMapEntry("C", "C", "text", 1, confidence=0.50, source="pdfplumber"),
        ]
        hr   = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, hr.cleaned_translations, set(), "en", "de")
        report = build_analysis_report(self._make_extraction(fm), defs, hr)
        # A (1.0) and B (0.75) shown; C (0.50) blocked
        assert report.questions_shown == 2
        assert report.questions_blocked == 1

    def test_invented_count_propagates(self):
        fm = [FieldMapEntry("A", "A", "text", 1)]
        hr = validate_no_hallucinations(fm, {
            "A":     {"question": "q", "explanation": "", "translated_options": {}},
            "GHOST": {"question": "g", "explanation": "", "translated_options": {}},
        })
        defs = field_map_to_defs(fm, hr.cleaned_translations, set(), "en", "de")
        report = build_analysis_report(self._make_extraction(fm), defs, hr)
        assert report.invented_questions_removed == 1

    def test_coverage_rate_all_shown(self):
        fm = [FieldMapEntry("A", "A", "text", 1, confidence=1.0, source="acroform")]
        hr = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, hr.cleaned_translations, set(), "en", "de")
        report = build_analysis_report(self._make_extraction(fm), defs, hr)
        assert report.coverage_rate == "100%"

    def test_coverage_rate_with_blocked(self):
        fm = [
            FieldMapEntry("A", "A", "text", 1, confidence=0.75),
            FieldMapEntry("B", "B", "text", 1, confidence=0.50),
        ]
        hr = validate_no_hallucinations(fm, {})
        defs = field_map_to_defs(fm, hr.cleaned_translations, set(), "en", "de")
        report = build_analysis_report(self._make_extraction(fm), defs, hr)
        # 1 shown out of 2 = 50%
        assert report.coverage_rate == "50%"


# ── 12. Golden snapshot — real Jobcenter PDF ──────────────────────────────────

JOBCENTER_PDF = r"c:\Users\bahib\Downloads\032_jc_lro_but_antrag_auf_leistungen_16032026_ba267943.pdf"

@pytest.mark.skipif(
    not os.path.exists(JOBCENTER_PDF),
    reason="Real Jobcenter PDF not available in this environment"
)
class TestJobcenterPdfGoldenSnapshot:
    """
    Golden test against the real Jobcenter BuT application form.
    Any regression that causes extra or missing questions will fail here.
    """

    def setup_method(self):
        with open(JOBCENTER_PDF, "rb") as f:
            self.pdf_bytes = f.read()

    def test_pdf_type_is_flat(self):
        result = extract_field_map(self.pdf_bytes)
        assert result.pdf_type == "flat", f"Expected flat, got {result.pdf_type}"

    def test_total_pages_is_2(self):
        result = extract_field_map(self.pdf_bytes)
        assert result.total_pages == 2

    def test_field_count_is_11(self):
        result = extract_field_map(self.pdf_bytes)
        assert len(result.fields) == 11, (
            f"Expected 11 fields, got {len(result.fields)}. "
            f"IDs: {[f.field_id for f in result.fields]}"
        )

    def test_expected_field_ids_present(self):
        result = extract_field_map(self.pdf_bytes)
        ids = {f.field_id for f in result.fields}
        required = {
            "name_vorname",
            "postanschrift",
            "name_vorname_geburtsdatum",
            "ort_datum",
            "leistungsart_auswahl",
        }
        for fid in required:
            assert fid in ids, f"Expected field_id '{fid}' not found. Got: {ids}"

    def test_multiselect_field_has_6_options(self):
        result = extract_field_map(self.pdf_bytes)
        ms = next((f for f in result.fields if f.field_type == "multiselect"), None)
        assert ms is not None, "No multiselect field found"
        assert len(ms.options) == 6, (
            f"Expected 6 options for leistungsart_auswahl, got {len(ms.options)}"
        )

    def test_no_duplicate_field_ids(self):
        result = extract_field_map(self.pdf_bytes)
        ids = [f.field_id for f in result.fields]
        assert len(ids) == len(set(ids)), f"Duplicate field_ids: {set(x for x in ids if ids.count(x) > 1)}"

    def test_all_fields_have_source_text(self):
        result = extract_field_map(self.pdf_bytes)
        for f in result.fields:
            assert f.source_text != "", f"Field '{f.field_id}' has empty source_text"

    def test_all_fields_are_pdfplumber_source(self):
        result = extract_field_map(self.pdf_bytes)
        for f in result.fields:
            assert f.source == "pdfplumber", f"Field '{f.field_id}' has source={f.source}"

    def test_confidence_is_0_75(self):
        result = extract_field_map(self.pdf_bytes)
        for f in result.fields:
            assert f.confidence == 0.75, f"Field '{f.field_id}' has confidence={f.confidence}"

    def test_all_fields_shown_at_0_75(self):
        """All pdfplumber fields (conf=0.75) must be shown (0.75 >= CONF_SHOW_MIN=0.70)."""
        result = extract_field_map(self.pdf_bytes)
        hr = validate_no_hallucinations(result.fields, {})
        defs = field_map_to_defs(result.fields, hr.cleaned_translations, set(), "en", "de")
        blocked = [d for d in defs if not d.show_question]
        assert len(blocked) == 0, f"Unexpected blocked fields: {[d.key for d in blocked]}"

    def test_all_fields_need_review_at_0_75(self):
        """pdfplumber fields are shown but flagged needs_review."""
        result = extract_field_map(self.pdf_bytes)
        hr = validate_no_hallucinations(result.fields, {})
        defs = field_map_to_defs(result.fields, hr.cleaned_translations, set(), "en", "de")
        for d in defs:
            assert d.needs_review is True, f"Field '{d.key}' should have needs_review=True"

    def test_grounding_rate_is_100_percent(self):
        result = extract_field_map(self.pdf_bytes)
        hr = validate_no_hallucinations(result.fields, {})
        defs = field_map_to_defs(result.fields, hr.cleaned_translations, set(), "en", "de")
        report = build_analysis_report(result, defs, hr)
        assert report.grounding_rate == "100%"
        assert report.grounding_ok is True

    def test_questions_equal_field_count(self):
        """No hallucinated extras — question count must equal extracted field count."""
        result = extract_field_map(self.pdf_bytes)
        hr = validate_no_hallucinations(result.fields, {})
        defs = field_map_to_defs(result.fields, hr.cleaned_translations, set(), "en", "de")
        assert len(defs) == len(result.fields), (
            f"Question count {len(defs)} != field count {len(result.fields)}"
        )
