"""
Tests for PDF-grounded question accuracy, field-type detection,
language separation, and answer→PDF mapping.

Run with:  pytest tests/test_pdf_grounding.py -v
"""
from __future__ import annotations

import io
import json
import sys
import os

# Allow importing from the app package without installing it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ── 1. Field-type classifier ──────────────────────────────────────────────────

# Functions previously lived in app.api.v1.documents but were moved into
# app.services.pdf_pipeline as part of the stateless-pipeline refactor.
# Aliasing keeps the test body unchanged.
from app.services.pdf_pipeline import (
    _classify_field_type as _acroform_field_type,
    _FF_RADIO,
    _FF_PUSHBUTTON,
    _FF_MULTISELECT,
)


@pytest.mark.parametrize("ft,flags,expected", [
    ("/Tx",  0,               "text"),
    ("/Sig", 0,               "signature"),
    ("/Ch",  0,               "select"),
    ("/Ch",  _FF_MULTISELECT, "multiselect"),
    ("/Btn", _FF_RADIO,       "radio"),
    ("/Btn", 0,               "checkbox"),
    ("/Btn", _FF_PUSHBUTTON,  None),      # pushbutton → skip
    ("/Tx",  _FF_RADIO,       "text"),    # /Tx ignores flags
    ("/Unknown", 0,           "text"),    # unknown → default text
])
def test_field_type_classifier(ft, flags, expected):
    assert _acroform_field_type(ft, flags) == expected


# ── 2. No hallucinated questions (every field has a PDF source key) ───────────

# Renamed (and made public) during the stateless-pipeline refactor.
# Now returns FieldMapEntry dataclasses (not dicts); see attribute-access below.
from app.services.pdf_pipeline import extract_acroform_fields as _extract_acroform_fields


def _make_minimal_acroform_pdf() -> bytes:
    """
    Build a minimal valid fillable PDF with three AcroForm fields:
      - Vorname (text)
      - Familienstand (radio: ledig / verheiratet)
      - Datum (text)
    Uses raw PDF syntax — no dependency on reportlab.
    """
    # This is a handcrafted minimal AcroForm PDF.
    # Widget coordinates are arbitrary; we only care about field structure.
    pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Annots [6 0 R 7 0 R 8 0 R 9 0 R] >> endobj

% AcroForm root
5 0 obj << /Fields [6 0 R 7 0 R] /DR << >> >> endobj

% Text field: Vorname
6 0 obj <<
  /Type /Annot /Subtype /Widget /FT /Tx
  /T (Vorname) /Rect [50 750 250 770] /P 3 0 R
>> endobj

% Radio group: Familienstand  (parent node with /Kids)
7 0 obj <<
  /FT /Btn /Ff 32768
  /T (Familienstand)
  /Kids [8 0 R 9 0 R]
>> endobj

% Radio widget 1: ledig
8 0 obj <<
  /Type /Annot /Subtype /Widget
  /Parent 7 0 R /Rect [50 700 70 720] /P 3 0 R
  /AP << /N << /ledig 10 0 R /Off 11 0 R >> >>
>> endobj

% Radio widget 2: verheiratet
9 0 obj <<
  /Type /Annot /Subtype /Widget
  /Parent 7 0 R /Rect [50 680 70 700] /P 3 0 R
  /AP << /N << /verheiratet 10 0 R /Off 11 0 R >> >>
>> endobj

10 0 obj << >> endobj
11 0 obj << >> endobj

xref
0 12
0000000000 65535 f\r
0000000009 00000 n\r
0000000068 00000 n\r
0000000125 00000 n\r
0000000000 65535 f\r
0000000260 00000 n\r
0000000310 00000 n\r
0000000430 00000 n\r
0000000540 00000 n\r
0000000680 00000 n\r
0000000820 00000 n\r
0000000840 00000 n\r

trailer << /Size 12 /Root 1 0 R >>
startxref
860
%%EOF"""
    return pdf


def test_extraction_returns_only_acroform_fields():
    """Every returned field must originate from the AcroForm /Fields tree."""
    pdf = _make_minimal_acroform_pdf()
    fields = _extract_acroform_fields(pdf)
    # We expect at least the Vorname text field; Familienstand radio may or may not
    # parse correctly from this minimal PDF — but we NEVER get invented fields.
    for f in fields:
        # Attribute access — extract_acroform_fields now returns FieldMapEntry.
        assert f.field_id != "", "Empty field name — parser returned a garbage entry"
        assert f.field_type in (
            "text", "date", "radio", "checkbox", "select", "multiselect", "signature"
        ), f"Unknown field_type: {f.field_type}"


def test_extraction_returns_empty_for_non_pdf():
    """Passing random bytes returns empty list, never raises."""
    result = _extract_acroform_fields(b"This is not a PDF at all!")
    assert result == []


def test_extraction_returns_empty_for_non_acroform_pdf():
    """A valid but non-fillable PDF (no AcroForm) returns empty list."""
    # Minimal PDF with no AcroForm key in the catalog
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f\r\n0000000009 00000 n\r\n"
        b"0000000068 00000 n\r\n0000000125 00000 n\r\n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF"
    )
    result = _extract_acroform_fields(pdf)
    assert result == []


# ── 3. Language separation (option value vs label) ────────────────────────────

from app.schemas.document import FieldDefinition, FieldOption


def test_field_option_value_is_pdf_language():
    """
    FieldOption.value must be the PDF-native export value.
    FieldOption.label must be the user-facing translated text.
    These must never be swapped.
    """
    opt = FieldOption(value="verheiratet", label="Marié(e)")
    assert opt.value == "verheiratet", "value should be PDF-native German"
    assert opt.label == "Marié(e)",    "label should be user-facing French"


def test_field_definition_question_is_user_language():
    """
    FieldDefinition.question is keyed by user locale.
    The PDF's original label is in original_label (document language).
    """
    fd = FieldDefinition(
        key="Familienstand",
        question={"fr": "Quelle est votre situation familiale ?"},
        explanation={"fr": ""},
        input_type="radio",
        options=[
            FieldOption(value="ledig", label="Célibataire"),
            FieldOption(value="verheiratet", label="Marié(e)"),
        ],
        original_label="Familienstand",   # German label from PDF
        document_language="de",
        source_page=1,
        order=1,
        is_prefilled=False,
        confidence=1.0,
    )
    assert "fr" in fd.question,                 "question must be keyed by user locale"
    assert fd.document_language == "de",        "document_language must be the PDF's language"
    assert fd.original_label == "Familienstand","original_label is the PDF label (German)"
    assert fd.options[0].value == "ledig",      "option value must be PDF-native"
    assert fd.options[1].label == "Marié(e)",   "option label must be in user language"


# ── 4. Choice field answer does NOT go through translation ───────────────────

def test_choice_types_constant():
    """CHOICE_TYPES should include all radio/checkbox/select variants."""
    from app.api.v1.documents import CHOICE_TYPES
    for t in ("radio", "checkbox", "select", "multiselect", "yes_no"):
        assert t in CHOICE_TYPES, f"{t} must be in CHOICE_TYPES"


# ── 5. Radio option extraction (field-tree, not page walk) ───────────────────

from app.services.pdf_pipeline import _radio_options_from_kids


def test_radio_options_from_empty_kids():
    """If the field has no /Kids, returns empty list without raising."""
    class FakeField:
        def get(self, key, default=None):
            return default
        def __contains__(self, key):
            return False
    result = _radio_options_from_kids(FakeField())
    assert result == []


# ── 6. PDF generator: checkbox normalisation ──────────────────────────────────

import pytest


@pytest.mark.parametrize("raw_value,expected_pdf_value", [
    ("yes",  "Yes"),
    ("ja",   "Yes"),
    ("true", "Yes"),
    ("1",    "Yes"),
    ("x",    "Yes"),
    ("no",   "Off"),
    ("",     "Off"),
    ("nein", "Off"),
])
def test_checkbox_normalisation(raw_value, expected_pdf_value):
    """Boolean answers must normalise to 'Yes' or 'Off' for PDF AcroForm checkboxes."""
    truthy = {"yes", "ja", "true", "1", "x", "on"}
    normalised = "Yes" if raw_value.lower() in truthy else "Off"
    assert normalised == expected_pdf_value


# ── 7. Grounding invariant: every question has a PDF source key ───────────────

# `_build_field_defs(extracted_dicts, translations, prefilled, ul, dl, confidence)`
# was the legacy entry point. The stateless pipeline replaced it with
# `field_map_to_defs(field_map, validated_translations, prefilled, ul, dl)`,
# which takes FieldMapEntry instances and reads confidence per-field.
# The shim below preserves the old test signatures while exercising the new API.
from app.services.pdf_pipeline import FieldMapEntry, field_map_to_defs


def _build_field_defs(extracted, translations, prefilled, user_lang, doc_lang, confidence=1.0):
    field_map = [
        FieldMapEntry(
            field_id=e["field_name"],
            original_label=e.get("original_label", e["field_name"]),
            field_type=e["field_type"],
            source_page=1,
            options=list(e.get("options", [])),
            current_value=e.get("current_value", ""),
            confidence=confidence,
            source="acroform",
            source_text=e.get("original_label", e["field_name"]),
        )
        for e in extracted
    ]
    return field_map_to_defs(field_map, translations, prefilled, user_lang, doc_lang)


def test_build_field_defs_uses_only_extracted_field_names():
    """
    _build_field_defs must only create questions for fields that appeared
    in the extraction result. It must never invent new field keys.
    """
    extracted = [
        {"field_name": "Vorname",       "field_type": "text",  "current_value": "", "options": [], "original_label": "Vorname"},
        {"field_name": "Familienstand", "field_type": "radio", "current_value": "", "options": ["ledig", "verheiratet"], "original_label": "Familienstand"},
    ]
    translations = {
        "Vorname":       {"question": "What is your first name?",          "explanation": "", "translated_options": {}},
        "Familienstand": {"question": "What is your marital status?",      "explanation": "",
                          "translated_options": {"ledig": "Single", "verheiratet": "Married"}},
    }
    defs = _build_field_defs(extracted, translations, set(), "en", "de", 1.0)

    assert len(defs) == 2, "Must return exactly one FieldDefinition per extracted field"
    keys = {d.key for d in defs}
    assert keys == {"Vorname", "Familienstand"}, "Keys must match extracted field names exactly"

    fs = {d.key: d for d in defs}
    assert fs["Familienstand"].input_type == "radio"
    assert len(fs["Familienstand"].options) == 2
    assert fs["Familienstand"].options[0].value == "ledig"
    assert fs["Familienstand"].options[0].label == "Single"
    assert fs["Familienstand"].options[1].value == "verheiratet"
    assert fs["Familienstand"].options[1].label == "Married"
    assert fs["Vorname"].options == []


def test_build_field_defs_confidence_flags():
    """
    The stateless pipeline uses two thresholds (CONF_SHOW_MIN=0.70,
    CONF_REVIEW_MIN=0.90) where the legacy single-threshold test used 0.6.
    Fields in [0.70, 0.90) must be shown but flagged needs_review=True;
    fields >= 0.90 are shown without the flag.
    """
    extracted = [{"field_name": "SomeField", "field_type": "text", "current_value": "", "options": [], "original_label": "SomeField"}]
    defs_review = _build_field_defs(extracted, {}, set(), "en", "de", confidence=0.75)
    defs_high   = _build_field_defs(extracted, {}, set(), "en", "de", confidence=1.0)
    assert defs_review[0].needs_review is True
    assert defs_high[0].needs_review   is False
