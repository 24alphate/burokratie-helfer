"""
Stage 4A — process-pdf routing tests.

Verifies that:
  - A scanned (Level 4) PDF triggers the OCR diagnostic path:
      * 200 OK
      * fields = []
      * extracted_field_ids = []
      * analysis_report.support_level == 4
      * analysis_report.ocr_diagnostic populated
      * pdf_token IS returned (so the frontend state machine stays consistent)
        but the empty extracted_field_ids ensure /fill-pdf would 422 anyway.
      * NO question generation, NO LLM call, NO field invention.
  - The 422 "scanned PDF unsupported" branch from the old behaviour is GONE
    for the scanned case (replaced by the diagnostic 200 above).
  - Level 1 (verified template) does NOT trigger OCR.
  - Level 2 (AcroForm) does NOT trigger OCR.
  - Level 3 (flat readable) does NOT trigger OCR (still 422 if no fields).
  - The technical_message field is stripped from the API response.

These tests do NOT require Tesseract to be installed locally — when the
binary is missing, the OCR path returns status='ocr_unavailable' and the
test still verifies the routing contract.

Run with:  pytest tests/test_ocr_routing_4a.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient


# ── Fixture builders ─────────────────────────────────────────────────────────

def _verified_template_pdf() -> bytes:
    """Reproduces the BuT fingerprint phrases (Level 1, jobcenter_but_v1)."""
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
        "Bildung und Teilhabe",
        "Persönliche Angaben",
        "Schülerbeförderung",
    ]:
        c.drawString(50, y, line)
        y -= 22
    c.save()
    return buf.getvalue()


def _acroform_pdf() -> bytes:
    """Minimal valid AcroForm PDF (Level 2). Same fixture used by router tests."""
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


def _flat_readable_pdf() -> bytes:
    """Flat PDF with extractable text but no template fingerprint match (Level 3)."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 11)
    y = 800
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


def _scanned_like_pdf() -> bytes:
    """
    Empty (no text) PDF — detect_pdf_type returns 'scanned' because the
    extracted text is below the threshold. This is the Stage 4A target.
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


# ── Test client fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app)


def _process(client: TestClient, pdf_bytes: bytes, locale: str = "en"):
    return client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )


# ── 1. Scanned PDF triggers Stage 4A diagnostic short-circuit ───────────────

class TestScannedPdfTriggersOcrDiagnostic:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.resp = _process(client, _scanned_like_pdf(), "en")
        # Stage 4A is supposed to short-circuit — it must NOT 422 like the
        # old behaviour did for scanned PDFs.
        assert self.resp.status_code == 200, self.resp.text
        self.body = self.resp.json()
        self.report = self.body["analysis_report"]

    def test_returns_200_ok(self):
        assert self.resp.status_code == 200

    def test_fields_are_empty(self):
        assert self.body["fields"] == []

    def test_extracted_field_ids_empty(self):
        assert self.body["extracted_field_ids"] == []

    def test_support_level_is_4(self):
        assert self.report["support_level"] == 4

    def test_ocr_diagnostic_is_populated(self):
        diag = self.report.get("ocr_diagnostic")
        assert diag is not None, "ocr_diagnostic missing from analysis_report"
        # Diagnostic shape carries every field the frontend reads
        for k in (
            "provider", "page_count", "diagnostic_status",
            "user_message", "average_confidence",
            "readable_pages", "unreadable_pages",
        ):
            assert k in diag, f"ocr_diagnostic missing key {k!r}"

    def test_diagnostic_status_is_known_value(self):
        diag = self.report["ocr_diagnostic"]
        assert diag["diagnostic_status"] in (
            "readable", "low_confidence", "no_text_found",
            "ocr_unavailable", "failed",
        )

    def test_technical_message_is_stripped(self):
        # technical_message is internal — never serialized to the client.
        diag = self.report["ocr_diagnostic"]
        assert "technical_message" not in diag, (
            "technical_message leaked into the API response — must be stripped"
        )

    def test_pdf_token_present(self):
        # Token signed even on Stage 4A so the frontend state machine
        # doesn't break — but it has no field_ids, so /fill-pdf would 422.
        assert isinstance(self.body.get("pdf_token"), str)
        assert len(self.body["pdf_token"]) > 0

    def test_no_questions_generated(self):
        # Stage 4A must NOT invent fields, questions, or quality scores.
        assert self.report["field_count"] == 0
        assert self.report["questions_shown"] == 0
        assert self.report["questions_blocked"] == 0

    def test_no_ai_quality_block_filled(self):
        # No translation pass ran — quality block stays None.
        assert self.report.get("question_quality") is None

    def test_no_ai_used_flag(self):
        assert self.body["ai_used"] is False


# ── 2. Levels 1/2/3 do NOT trigger OCR ──────────────────────────────────────

class TestNonScannedDoesNotTriggerOcr:
    """OCR diagnostic must remain absent for Levels 1, 2, 3."""

    def test_level_1_verified_template_no_ocr(self, client):
        resp = _process(client, _verified_template_pdf(), "en")
        assert resp.status_code == 200, resp.text
        report = resp.json()["analysis_report"]
        assert report["support_level"] == 1
        # Level 1 must NEVER touch the OCR path.
        assert report.get("ocr_diagnostic") is None
        # Sanity: the template was matched.
        assert report["template_id"] == "jobcenter_but_v1"

    def test_level_2_acroform_no_ocr(self, client):
        resp = _process(client, _acroform_pdf(), "en")
        # Whether the AcroForm has 0 or N fields, support_level must be 2
        # and OCR diagnostic must NOT be populated.
        if resp.status_code == 200:
            report = resp.json()["analysis_report"]
            assert report["support_level"] == 2
            assert report.get("ocr_diagnostic") is None
        else:
            # If the minimal fixture extracts 0 fields, we get 422 — that's
            # the legitimate "no extractable widgets" path. NOT 4A.
            assert resp.status_code == 422
            # The 422 detail must NOT mention OCR.
            assert "scanned" not in resp.json().get("detail", "").lower()

    def test_level_3_flat_readable_no_ocr(self, client):
        resp = _process(client, _flat_readable_pdf(), "en")
        # Flat fixture has no recognisable field patterns → expect 422 (the
        # extractor returns no fields). Whatever the outcome, OCR must
        # not run.
        if resp.status_code == 200:
            report = resp.json()["analysis_report"]
            assert report["support_level"] == 3
            assert report.get("ocr_diagnostic") is None
        else:
            assert resp.status_code == 422


# ── 3. Stage 4A invariants ──────────────────────────────────────────────────

class TestStage4AInvariants:
    """
    These tests are "if we ever break Stage 4A, the canary fires" —
    the contract Part IV Section 31 (hallucination prevention) describes.
    """

    def test_scanned_pdf_returns_no_field_definitions(self, client):
        """OCR must not invent FieldDefinitions on its own."""
        resp = _process(client, _scanned_like_pdf(), "en")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fields"] == []
        # raw_extracted_fields and ai_comparison are also empty —
        # Stage 4A skips translation entirely.
        assert body["raw_extracted_fields"] == []
        assert body["ai_comparison"] == []

    def test_scanned_pdf_does_not_call_ai(self, client):
        """ai_used must be False when the OCR short-circuit fires."""
        resp = _process(client, _scanned_like_pdf(), "en")
        assert resp.status_code == 200
        assert resp.json()["ai_used"] is False

    def test_scanned_pdf_token_has_no_fillable_fields(self, client):
        """The signed token must carry an empty field list."""
        from app.services.pdf_token import verify_pdf_token
        from app.config import settings
        resp = _process(client, _scanned_like_pdf(), "en")
        token = resp.json()["pdf_token"]
        decoded = verify_pdf_token(token, settings.secret_key)
        assert decoded is not None
        # Empty field list → /fill-pdf will refuse any answer key.
        assert decoded["field_ids"] == []
        # support_level baked into the token must equal 4.
        assert decoded["support_level"] == 4

    def test_scanned_pdf_extraction_source_is_auto(self, client):
        """Stage 4A doesn't pretend the document was "verified" or "acroform"."""
        resp = _process(client, _scanned_like_pdf(), "en")
        report = resp.json()["analysis_report"]
        assert report["extraction_source"] == "auto"
        assert report.get("template_id") is None

    def test_scanned_pdf_fill_strategy_is_none(self, client):
        """Stage 4A has no fill path → fill_strategy must be None."""
        resp = _process(client, _scanned_like_pdf(), "en")
        report = resp.json()["analysis_report"]
        assert report.get("fill_strategy") is None

    def test_scanned_pdf_grounding_remains_ok(self, client):
        """Vacuously true — no fields means nothing to ground, but the contract still holds."""
        resp = _process(client, _scanned_like_pdf(), "en")
        report = resp.json()["analysis_report"]
        assert report["grounding_ok"] is True
        assert report["grounding_rate"] == "100%"


# ── 4. The pdf_token from Stage 4A is unusable for /fill-pdf ────────────────

class TestStage4ATokenIsNotFillable:
    """
    The Stage 4A spec says: token IS signed (so frontend stays consistent),
    but /fill-pdf must refuse it because it carries no field_ids. This
    keeps the "no field invention" promise intact end-to-end.
    """

    def test_fill_pdf_refuses_empty_field_token(self, client):
        proc = _process(client, _scanned_like_pdf(), "en")
        assert proc.status_code == 200
        token = proc.json()["pdf_token"]

        # Try to fill with a fake answer — the grounding guard MUST reject.
        resp = client.post(
            "/api/v1/fill-pdf",
            json={
                "pdf_token": token,
                "answers": {"any_field": "some value"},
                "field_labels": {},
            },
        )
        # Per the grounding guard, providing answers for fields not in
        # extracted_field_ids → 400. Stage 4A's empty list guarantees
        # ANY answer key is "unknown".
        assert resp.status_code in (400, 422), (
            f"Expected 400/422 but got {resp.status_code}: {resp.text}"
        )
