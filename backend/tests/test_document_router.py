"""
Tests for the centralized document router (Phase B / R1.3).

Covers:
  - support_level_for() mapping for every known extraction_source
  - route_document() returns the correct DocumentRoute for:
      * verified template PDF (Level 1)
      * AcroForm PDF (Level 2)
      * flat readable PDF (Level 3)
      * scanned/empty PDF (Level 4)
      * non-PDF garbage bytes (safe fallback)
  - DocumentRoute invariants (template_id presence/absence, total_pages)

Run with:  pytest tests/test_document_router.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.pdf_pipeline import (
    DocumentRoute,
    route_document,
    support_level_for,
)


# ── 1. support_level_for() mapping ────────────────────────────────────────────

class TestSupportLevelMapping:
    def test_verified_template_is_level_1(self):
        assert support_level_for("verified_template") == 1

    def test_acroform_is_level_2(self):
        assert support_level_for("acroform") == 2

    def test_pdfplumber_is_level_3(self):
        assert support_level_for("pdfplumber") == 3

    def test_auto_is_level_4(self):
        # "auto" is the source we set when no engine could extract — Level 4.
        assert support_level_for("auto") == 4

    def test_unknown_extraction_source_falls_back_to_4(self):
        # Defensive fallback: an unrecognised source string must NEVER claim Level 1.
        assert support_level_for("not_a_real_source") == 4
        assert support_level_for("") == 4

    def test_returned_levels_are_in_valid_range(self):
        for src in ("verified_template", "acroform", "pdfplumber", "auto", "x"):
            level = support_level_for(src)
            assert 1 <= level <= 4, f"{src} returned out-of-range level {level}"


# ── 2. PDF fixtures ───────────────────────────────────────────────────────────

def _verified_template_pdf() -> bytes:
    """
    A flat PDF whose extracted text matches the JobcenterButTemplate fingerprint:
      requires "bildung und teilhabe", "persönliche angaben", "beantragte leistung"
      plus one section marker (e.g. "schülerbeförderung").
    Built with reportlab so all phrases are searchable in extracted text.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 11)
    y = 800
    for line in [
        "Antrag auf Leistungen fur Bildung und Teilhabe",
        "Persoenliche Angaben (Antragsteller/in)",
        "Beantragte Leistung",
        "Schuelerbefoerderung",
        # German umlauts as the template fingerprint expects them — needed to match.
        "Bildung und Teilhabe",
        "Persönliche Angaben",
        "Schülerbeförderung",
    ]:
        c.drawString(50, y, line)
        y -= 22
    c.save()
    return buf.getvalue()


def _acroform_pdf() -> bytes:
    """
    Minimal valid fillable PDF — has /AcroForm with one /Tx widget.
    Same hand-crafted PDF used by other test files.
    """
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Annots [6 0 R] >> endobj
5 0 obj << /Fields [6 0 R] /DR << >> >> endobj
6 0 obj << /Type /Annot /Subtype /Widget /FT /Tx
  /T (Vorname) /Rect [50 750 250 770] /P 3 0 R >> endobj
xref
0 7
0000000000 65535 f\r
0000000009 00000 n\r
0000000068 00000 n\r
0000000125 00000 n\r
0000000000 65535 f\r
0000000270 00000 n\r
0000000320 00000 n\r
trailer << /Size 7 /Root 1 0 R >>
startxref
430
%%EOF"""


def _flat_pdf() -> bytes:
    """
    A flat PDF with extractable text, no AcroForm widgets, no template
    fingerprint match. Must contain >200 chars of extracted text — that is
    the threshold detect_pdf_type() uses to distinguish "flat" from "scanned".
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 11)
    y = 800
    # Generic municipal form text — long enough to clear the 200-char threshold,
    # but does NOT contain the BuT template fingerprint phrases.
    for line in [
        "Generic municipal application form for residency registration",
        "Section A - Applicant personal information",
        "Last name and first name as shown on identity document",
        "Current postal address including street and house number",
        "Postal code and city of current residence",
        "Date of birth in day month year format",
        "Country of nationality and language preference",
        "Section B - Reason for application",
        "Date of submission and applicant signature line",
        "Office use only - registration number and clerk initials",
    ]:
        c.drawString(50, y, line)
        y -= 22
    c.save()
    return buf.getvalue()


def _scanned_pdf() -> bytes:
    """
    A PDF with no text content at all (treated as 'scanned' by detect_pdf_type
    when extracted text is shorter than ~50 chars).
    """
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f\r\n0000000009 00000 n\r\n"
        b"0000000068 00000 n\r\n0000000125 00000 n\r\n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF"
    )


def _garbage_bytes() -> bytes:
    """Not a PDF at all — router must not raise."""
    return b"This is not a PDF document, just plain ASCII bytes."


# ── 3. route_document() per level ─────────────────────────────────────────────

class TestRouteVerifiedTemplate:
    def setup_method(self):
        self.route = route_document(_verified_template_pdf())

    def test_returns_document_route(self):
        assert isinstance(self.route, DocumentRoute)

    def test_support_level_is_1(self):
        assert self.route.support_level == 1

    def test_extraction_source_is_verified_template(self):
        assert self.route.extraction_source == "verified_template"

    def test_pdf_type_is_verified_template(self):
        assert self.route.pdf_type == "verified_template"

    def test_template_id_is_set(self):
        assert self.route.template_id == "jobcenter_but_v1"

    def test_total_pages_is_positive(self):
        assert self.route.total_pages >= 1


class TestRouteAcroForm:
    def setup_method(self):
        self.route = route_document(_acroform_pdf())

    def test_support_level_is_2(self):
        assert self.route.support_level == 2

    def test_extraction_source_is_acroform(self):
        assert self.route.extraction_source == "acroform"

    def test_pdf_type_is_acroform(self):
        assert self.route.pdf_type == "acroform"

    def test_template_id_is_none(self):
        assert self.route.template_id is None


class TestRouteFlat:
    def setup_method(self):
        self.route = route_document(_flat_pdf())

    def test_support_level_is_3(self):
        assert self.route.support_level == 3

    def test_extraction_source_is_pdfplumber(self):
        assert self.route.extraction_source == "pdfplumber"

    def test_pdf_type_is_flat(self):
        assert self.route.pdf_type == "flat"

    def test_template_id_is_none(self):
        assert self.route.template_id is None


class TestRouteScanned:
    def setup_method(self):
        self.route = route_document(_scanned_pdf())

    def test_support_level_is_4(self):
        # No extractable text → router must NOT claim verified, AcroForm, or flat.
        assert self.route.support_level == 4

    def test_extraction_source_is_auto(self):
        assert self.route.extraction_source == "auto"

    def test_template_id_is_none(self):
        assert self.route.template_id is None

    def test_pdf_type_indicates_unknown_or_scanned(self):
        # detect_pdf_type may return "scanned" or "unknown" depending on version.
        # Either is acceptable as long as it is NOT a level-1/2/3 claim.
        assert self.route.pdf_type in ("scanned", "unknown")


class TestRouteGarbageBytes:
    def setup_method(self):
        # Router must not raise on non-PDF input — falls through to safe default.
        self.route = route_document(_garbage_bytes())

    def test_does_not_raise_returns_route(self):
        assert isinstance(self.route, DocumentRoute)

    def test_garbage_input_is_level_4(self):
        assert self.route.support_level == 4

    def test_garbage_input_has_no_template_id(self):
        assert self.route.template_id is None


# ── 4. Cross-cutting invariants ───────────────────────────────────────────────

class TestRouteInvariants:
    @pytest.mark.parametrize("pdf_factory,expected_template", [
        (_verified_template_pdf, True),
        (_acroform_pdf,         False),
        (_flat_pdf,             False),
        (_scanned_pdf,          False),
        (_garbage_bytes,        False),
    ])
    def test_template_id_is_set_iff_level_1(self, pdf_factory, expected_template):
        route = route_document(pdf_factory())
        if expected_template:
            assert route.support_level == 1
            assert route.template_id is not None
        else:
            assert route.template_id is None

    @pytest.mark.parametrize("pdf_factory", [
        _verified_template_pdf,
        _acroform_pdf,
        _flat_pdf,
        _scanned_pdf,
        _garbage_bytes,
    ])
    def test_route_support_level_matches_extraction_source_mapping(self, pdf_factory):
        route = route_document(pdf_factory())
        assert route.support_level == support_level_for(route.extraction_source)
