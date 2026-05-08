"""
Tests for the Level 1 verified template registry.

Covers:
  - Template contract validation (P0.1)
  - Fingerprint: match BuT text, reject non-BuT text (P0.3)
  - find_template_by_id: correct lookup and miss (P0.3)
  - Field map completeness: unique ids, confidence, source (P0)
  - Write specs coverage: every non-sig field has a spec (P0)
  - validate_template() returns no errors for the current BuT template (P0)

Run with:  pytest tests/test_template_registry.py -v
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.form_templates import (
    find_matching_template,
    find_template_by_id,
    validate_template,
)
from app.services.form_templates.jobcenter_but import JobcenterButTemplate


# ── Fixtures ──────────────────────────────────────────────────────────────────

BUT_TEXT = """
Antrag auf Leistungen für Bildung und Teilhabe
Persönliche Angaben
Beantragte Leistung
A. Eintägige Ausflüge der Schule
B. Mehrtägige Klassenfahrten
C. Schülerbeförderung
D. Lernförderung
E. Mittagessen
F. Teilhabe am sozialen und kulturellen Leben
"""

NON_BUT_TEXTS = [
    "Antrag auf Arbeitslosengeld II ALG2 SGB II Wohngeld Unterhaltsvorschuss",
    "Kindergeldantrag Familienkasse Elterngeld Kinderzuschlag",
    "Steuererklärung Einkommensteuer Finanzamt Anlage N",
    "",  # empty text
    "Bildung und Teilhabe",  # partial — missing required phrases
]


# ── 1. Template registry: fingerprint ─────────────────────────────────────────

class TestFingerprint:
    def test_but_text_matches(self):
        tmpl = find_matching_template(BUT_TEXT)
        assert tmpl is not None
        assert tmpl.template_id == "jobcenter_but_v1"

    def test_but_text_case_insensitive(self):
        tmpl = find_matching_template(BUT_TEXT.upper())
        assert tmpl is not None, "Fingerprint must be case-insensitive"

    def test_non_but_texts_do_not_match(self):
        for text in NON_BUT_TEXTS:
            result = find_matching_template(text)
            assert result is None, f"False positive for: {text[:60]!r}"

    def test_partial_but_text_no_match(self):
        partial = "Bildung und Teilhabe"
        assert find_matching_template(partial) is None

    def test_minimal_valid_but_text(self):
        minimal = (
            "bildung und teilhabe persönliche angaben "
            "beantragte leistung schülerbeförderung"
        )
        tmpl = find_matching_template(minimal)
        assert tmpl is not None


# ── 2. Template registry: find_by_id ─────────────────────────────────────────

class TestFindById:
    def test_correct_id_returns_template(self):
        tmpl = find_template_by_id("jobcenter_but_v1")
        assert tmpl is not None
        assert isinstance(tmpl, JobcenterButTemplate)

    def test_wrong_id_returns_none(self):
        assert find_template_by_id("nonexistent_template") is None

    def test_empty_id_returns_none(self):
        assert find_template_by_id("") is None


# ── 3. Field map integrity ────────────────────────────────────────────────────

class TestFieldMap:
    def setup_method(self):
        self.tmpl = JobcenterButTemplate()
        self.field_map = self.tmpl.get_field_map()

    def test_field_map_nonempty(self):
        assert len(self.field_map) > 0

    def test_field_ids_unique(self):
        ids = [f.field_id for f in self.field_map]
        assert len(ids) == len(set(ids)), f"Duplicate field_ids: {[x for x in ids if ids.count(x) > 1]}"

    def test_non_signature_confidence_is_1(self):
        for f in self.field_map:
            if f.field_type != "signature":
                assert f.confidence == 1.0, f"{f.field_id} has confidence {f.confidence}"

    def test_signature_confidence_is_0_5(self):
        sigs = [f for f in self.field_map if f.field_type == "signature"]
        for s in sigs:
            assert s.confidence == 0.5, f"{s.field_id} signature should have confidence 0.5"

    def test_all_fields_source_is_verified_template(self):
        for f in self.field_map:
            assert f.source == "verified_template", f"{f.field_id}.source = {f.source!r}"

    def test_field_ids_are_nonempty_strings(self):
        for f in self.field_map:
            assert isinstance(f.field_id, str) and f.field_id.strip(), f"Empty field_id in field_map"


# ── 4. Write spec integrity ───────────────────────────────────────────────────

class TestWriteSpecs:
    def setup_method(self):
        self.tmpl = JobcenterButTemplate()
        self.field_map = self.tmpl.get_field_map()
        self.specs = self.tmpl.get_write_specs()

    def test_write_specs_nonempty(self):
        assert len(self.specs) > 0

    def test_spec_ids_unique(self):
        ids = [s.field_id for s in self.specs]
        assert len(ids) == len(set(ids)), f"Duplicate WriteSpec field_ids: {[x for x in ids if ids.count(x) > 1]}"

    def test_every_non_sig_field_has_write_spec(self):
        spec_ids = {s.field_id for s in self.specs}
        non_sig_fields = [f for f in self.field_map if f.confidence > 0.5]
        for f in non_sig_fields:
            assert f.field_id in spec_ids, f"No WriteSpec for non-signature field: {f.field_id}"

    def test_signature_fields_are_skipped(self):
        skip_ids = {s.field_id for s in self.specs if s.strategy == "skip"}
        sig_fields = [f for f in self.field_map if f.field_type == "signature"]
        for s in sig_fields:
            assert s.field_id in skip_ids, f"Signature field {s.field_id} must have strategy='skip'"

    def test_label_search_specs_have_nonempty_label(self):
        for s in self.specs:
            if s.strategy == "label_search":
                assert s.label_search.strip(), f"{s.field_id} has empty label_search"


# ── 5. validate_template() contract check ────────────────────────────────────

class TestValidateTemplate:
    def test_jobcenter_but_passes_validation(self):
        tmpl = JobcenterButTemplate()
        errors = validate_template(tmpl)
        assert errors == [], f"Template contract violations:\n" + "\n".join(errors)
