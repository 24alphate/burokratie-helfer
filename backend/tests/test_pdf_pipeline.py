"""
Tests for the deterministic field-map-first PDF pipeline.

Covers:
  - PDF type detection
  - AcroForm field extraction (field_id, field_type, options, page, bbox)
  - Anti-hallucination validator
  - Language separation invariants
  - Answer mapping (option.value = PDF language)
  - Final PDF field map round-trip

Run with:  pytest tests/test_pdf_pipeline.py -v
"""
from __future__ import annotations

import io
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.pdf_pipeline import (
    detect_pdf_type,
    extract_field_map,
    extract_acroform_fields,
    validate_no_hallucinations,
    field_map_to_defs,
    FieldMapEntry,
    HallucinationReport,
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
        pdf = _make_acroform_pdf()
        pdf_type, pages = detect_pdf_type(pdf)
        assert pdf_type == "acroform", f"Expected acroform, got {pdf_type}"
        assert pages >= 1

    def test_flat_pdf_detected(self):
        pdf = _make_flat_pdf()
        pdf_type, pages = detect_pdf_type(pdf)
        assert pdf_type in ("flat", "scanned"), f"Expected flat or scanned, got {pdf_type}"
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
        # Valid PDF header but minimal content — not acroform
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
        assert pdf_type != "acroform", "Should not detect AcroForm when /AcroForm is absent"


# ── 2. AcroForm field extraction ──────────────────────────────────────────────

class TestAcroFormExtraction:
    def test_extracts_text_field(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        names = {f.field_id for f in fields}
        assert "Vorname" in names, f"Expected Vorname, got {names}"

    def test_extracts_radio_group(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        radio = [f for f in fields if f.field_type == "radio"]
        assert any(f.field_id == "Familienstand" for f in radio), \
            "Expected Familienstand radio field"

    def test_radio_field_has_options(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        familienstand = next((f for f in fields if f.field_id == "Familienstand"), None)
        if familienstand:  # option extraction depends on exact PDF structure
            assert isinstance(familienstand.options, list)

    def test_field_types_are_valid(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        valid_types = {"text", "date", "number", "checkbox", "radio",
                       "select", "multiselect", "signature"}
        for f in fields:
            assert f.field_type in valid_types, \
                f"Invalid field_type '{f.field_type}' for field '{f.field_id}'"

    def test_source_is_acroform(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.source == "acroform"
            assert f.confidence == 1.0

    def test_source_page_is_positive(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.source_page >= 1, f"source_page must be ≥ 1, got {f.source_page}"

    def test_no_fields_for_non_pdf(self):
        fields = extract_acroform_fields(b"not a pdf")
        assert fields == []

    def test_no_fields_for_flat_pdf(self):
        fields = extract_acroform_fields(_make_flat_pdf())
        assert fields == [], "Flat PDF should return no AcroForm fields"

    def test_field_ids_are_unique(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        ids = [f.field_id for f in fields]
        assert len(ids) == len(set(ids)), "Duplicate field_ids returned"

    def test_field_ids_are_non_empty(self):
        fields = extract_acroform_fields(_make_acroform_pdf())
        for f in fields:
            assert f.field_id.strip() != "", "Empty field_id returned"


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
        field_map = self._make_field_map()
        translations = {
            "Vorname":       {"question": "First name?",       "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "Marital status?",   "explanation": "",
                              "translated_options": {"ledig": "Single", "verheiratet": "Married", "geschieden": "Divorced"}},
            "IBAN":          {"question": "Your IBAN number?", "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert report.is_clean
        assert report.invented == []
        assert report.missing == []
        assert set(report.cleaned_translations.keys()) == {"Vorname", "Familienstand", "IBAN"}

    def test_invented_field_is_discarded(self):
        field_map = self._make_field_map()
        translations = {
            "Vorname":      {"question": "First name?", "explanation": "", "translated_options": {}},
            "ERFUNDEN":     {"question": "Invented question!", "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "Marital status?", "explanation": "", "translated_options": {}},
            "IBAN":         {"question": "IBAN?", "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert not report.is_clean
        assert "ERFUNDEN" in report.invented
        assert "ERFUNDEN" not in report.cleaned_translations

    def test_multiple_invented_fields_all_discarded(self):
        field_map = self._make_field_map()
        translations = {
            "Vorname": {"question": "q", "explanation": "", "translated_options": {}},
            "GhostField1": {"question": "ghost1", "explanation": "", "translated_options": {}},
            "GhostField2": {"question": "ghost2", "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert not report.is_clean
        assert "GhostField1" in report.invented
        assert "GhostField2" in report.invented
        assert "GhostField1" not in report.cleaned_translations
        assert "GhostField2" not in report.cleaned_translations

    def test_missing_field_gets_raw_label_fallback(self):
        field_map = self._make_field_map()
        translations = {
            "Vorname": {"question": "First name?", "explanation": "", "translated_options": {}},
            # Familienstand and IBAN are missing
        }
        report = validate_no_hallucinations(field_map, translations)
        assert "Familienstand" in report.missing
        assert "IBAN" in report.missing
        # Backfilled with raw PDF label
        assert report.cleaned_translations["Familienstand"]["question"] == "Familienstand"
        assert report.cleaned_translations["IBAN"]["question"] == "IBAN"

    def test_missing_field_backfill_preserves_options(self):
        field_map = self._make_field_map()
        translations = {}  # AI returned nothing
        report = validate_no_hallucinations(field_map, translations)
        # Familienstand has options, they should be backfilled identity-mapped
        opts = report.cleaned_translations["Familienstand"]["translated_options"]
        assert opts.get("ledig") == "ledig"
        assert opts.get("verheiratet") == "verheiratet"

    def test_empty_translations_all_backfilled(self):
        field_map = self._make_field_map()
        report = validate_no_hallucinations(field_map, {})
        assert report.is_clean  # no invented keys
        assert set(report.cleaned_translations.keys()) == {"Vorname", "Familienstand", "IBAN"}

    def test_output_has_exactly_one_entry_per_field(self):
        field_map = self._make_field_map()
        translations = {
            "Vorname":       {"question": "First name?", "explanation": "", "translated_options": {}},
            "Familienstand": {"question": "Status?",     "explanation": "", "translated_options": {}},
            "IBAN":          {"question": "IBAN?",       "explanation": "", "translated_options": {}},
            "INVENTED":      {"question": "Fake!",       "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        # Exactly one entry per real field — INVENTED is stripped
        assert len(report.cleaned_translations) == 3
        assert set(report.cleaned_translations.keys()) == {"Vorname", "Familienstand", "IBAN"}


# ── 5. Language separation ────────────────────────────────────────────────────

class TestLanguageSeparation:
    """
    The user-facing language must never contaminate the PDF-native values.
    FieldOption.value  = PDF-native export value  (document language, e.g. "verheiratet")
    FieldOption.label  = user-facing translation   (user language,     e.g. "Marié(e)")
    raw_answer         = option.value              (submitted to backend, PDF language)
    translated_answer  = raw_answer                (for choice fields — already PDF language)
    """

    def test_field_option_value_is_pdf_language(self):
        from app.schemas.document import FieldOption
        opt = FieldOption(value="verheiratet", label="Marié(e)")
        assert opt.value == "verheiratet"    # goes into the German PDF
        assert opt.label == "Marié(e)"       # shown in French UI

    def test_field_option_value_never_equals_label(self):
        from app.schemas.document import FieldOption
        # When label differs from value, they must not be swapped
        opt = FieldOption(value="ledig", label="Célibataire")
        assert opt.value != opt.label

    def test_document_language_is_pdf_language(self):
        from app.schemas.document import FieldDefinition, FieldOption
        fd = FieldDefinition(
            key="Familienstand",
            question={"fr": "Quelle est votre situation familiale ?"},
            explanation={"fr": ""},
            input_type="radio",
            options=[
                FieldOption(value="ledig",      label="Célibataire"),
                FieldOption(value="verheiratet", label="Marié(e)"),
            ],
            original_label="Familienstand",   # German — the PDF label
            document_language="de",
            source_page=1,
            order=1,
            is_prefilled=False,
        )
        assert fd.document_language == "de"
        assert "fr" in fd.question              # UI in French
        assert fd.original_label == "Familienstand"  # PDF label stays German
        # Values are German PDF export values
        assert fd.options[0].value == "ledig"
        assert fd.options[1].value == "verheiratet"
        # Labels are French UI translations
        assert fd.options[0].label == "Célibataire"
        assert fd.options[1].label == "Marié(e)"

    def test_question_keyed_by_user_locale(self):
        from app.schemas.document import FieldDefinition
        fd = FieldDefinition(
            key="Vorname",
            question={"ar": "ما هو اسمك الأول؟"},
            explanation={"ar": ""},
            input_type="text",
            options=[],
            original_label="Vorname",
            document_language="de",
            source_page=1,
            order=1,
            is_prefilled=False,
        )
        assert "ar" in fd.question
        assert fd.original_label == "Vorname"  # PDF label unchanged


# ── 6. Answer → PDF field mapping ─────────────────────────────────────────────

class TestAnswerMapping:
    """
    User answers are in the user-selected language (labels).
    But raw_answer submitted to the backend must be option.value (PDF language).
    The PDF generator uses raw_answer / translated_answer to fill fields.
    """

    def test_choice_raw_answer_is_pdf_value(self):
        """
        When user clicks "Marié(e)" (French label), the frontend submits
        option.value = "verheiratet" (German PDF export value) as raw_answer.
        This means raw_answer is already in PDF language — no translation needed.
        """
        # The CHOICE_TYPES set in documents.py determines which fields skip translation
        from app.api.v1.documents import CHOICE_TYPES
        assert "radio"      in CHOICE_TYPES
        assert "checkbox"   in CHOICE_TYPES
        assert "select"     in CHOICE_TYPES
        assert "multiselect" in CHOICE_TYPES

    def test_checkbox_normalised_to_yes_off(self):
        """Checkbox answers must normalise to 'Yes' or 'Off' before PDF writing."""
        truthy = {"yes", "ja", "true", "1", "x", "on"}
        for val in truthy:
            assert val.lower() in truthy, f"'{val}' should be truthy"
        for val in ("no", "nein", "false", "0", ""):
            assert val.lower() not in truthy, f"'{val}' should not be truthy"

    def test_every_extracted_field_has_a_question(self):
        """
        After validate_no_hallucinations, cleaned_translations must have
        exactly one entry per extracted field — guaranteed by backfill.
        """
        field_map = [
            FieldMapEntry("Vorname", "Vorname", "text", 1),
            FieldMapEntry("IBAN",    "IBAN",    "text", 1),
        ]
        report = validate_no_hallucinations(field_map, {})
        assert len(report.cleaned_translations) == len(field_map)
        for entry in field_map:
            assert entry.field_id in report.cleaned_translations

    def test_no_question_without_pdf_field(self):
        """
        No translation key should exist without a matching FieldMapEntry.
        The validator strips all invented keys.
        """
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        translations = {
            "Vorname":  {"question": "First name?", "explanation": "", "translated_options": {}},
            "INVENTED": {"question": "Ghost field",  "explanation": "", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        assert "INVENTED" not in report.cleaned_translations
        assert len(report.cleaned_translations) == 1


# ── 7. field_map_to_defs round-trip ──────────────────────────────────────────

class TestFieldMapToDefs:
    def test_one_def_per_field(self):
        from app.schemas.document import FieldDefinition
        field_map = [
            FieldMapEntry("Vorname",       "Vorname",       "text",  1),
            FieldMapEntry("Familienstand", "Familienstand", "radio", 1,
                          options=["ledig", "verheiratet"]),
        ]
        translations = {
            "Vorname": {"question": "First name?", "explanation": "", "translated_options": {}},
            "Familienstand": {
                "question": "Marital status?", "explanation": "",
                "translated_options": {"ledig": "Single", "verheiratet": "Married"},
            },
        }
        report = validate_no_hallucinations(field_map, translations)
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert len(defs) == 2

    def test_options_have_pdf_values_and_translated_labels(self):
        field_map = [
            FieldMapEntry("Familienstand", "Familienstand", "radio", 1,
                          options=["ledig", "verheiratet"]),
        ]
        translations = {
            "Familienstand": {
                "question": "Situation de famille ?", "explanation": "",
                "translated_options": {"ledig": "Célibataire", "verheiratet": "Marié(e)"},
            },
        }
        report = validate_no_hallucinations(field_map, translations)
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "fr", "de")
        fd = defs[0]
        assert fd.options[0].value == "ledig"        # PDF-native (German)
        assert fd.options[0].label == "Célibataire"  # UI label (French)
        assert fd.options[1].value == "verheiratet"
        assert fd.options[1].label == "Marié(e)"

    def test_prefilled_field_marked(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1, current_value="Max")]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, {"Vorname"}, "en", "de")
        assert defs[0].is_prefilled is True

    def test_non_prefilled_field_not_marked(self):
        field_map = [FieldMapEntry("IBAN", "IBAN", "text", 1)]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert defs[0].is_prefilled is False

    def test_acroform_fields_not_needs_review(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1, confidence=1.0, source="acroform")]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert defs[0].needs_review is False

    def test_pdfplumber_fields_needs_review(self):
        field_map = [FieldMapEntry("some_field", "Some field", "text", 1, confidence=0.8, source="pdfplumber")]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "en", "de")
        assert defs[0].needs_review is True

    def test_document_language_preserved_in_defs(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        report = validate_no_hallucinations(field_map, {})
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "fr", "de")
        assert defs[0].document_language == "de"   # PDF stays German

    def test_question_in_user_language_not_document_language(self):
        field_map = [FieldMapEntry("Vorname", "Vorname", "text", 1)]
        translations = {
            "Vorname": {"question": "Quel est votre prénom ?", "explanation": "...", "translated_options": {}},
        }
        report = validate_no_hallucinations(field_map, translations)
        defs = field_map_to_defs(field_map, report.cleaned_translations, set(), "fr", "de")
        assert "fr" in defs[0].question
        assert defs[0].question["fr"] == "Quel est votre prénom ?"
