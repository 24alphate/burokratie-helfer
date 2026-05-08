"""
Stage 4A — TesseractProvider unit tests.

Goals:
  - The provider NEVER raises (returns OCRDiagnostic on every input).
  - When pytesseract is missing OR the binary is missing, the provider
    returns status='ocr_unavailable'.
  - When the binary is present, an empty/blank PDF returns
    status='no_text_found' and an empty pdf_bytes input returns
    status='failed' (caught + wrapped, never raised).
  - When fitz can't parse the bytes at all, the provider still returns
    a valid OCRDiagnostic with status='failed'.
  - The OCRDiagnostic dataclass shape is stable + serializable to dict.
  - Status decision boundaries (LOW_CONFIDENCE_THRESHOLD) are correct.
  - When Tesseract IS available locally, a generated text image returns
    status='readable' with non-empty full_text.

Run with:  pytest tests/test_ocr_tesseract.py -v
"""
from __future__ import annotations

import io
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.ocr.diagnostic import (
    LOW_CONFIDENCE_THRESHOLD,
    OCRDiagnostic,
    OCRDiagnosticProvider,
    OCRPageQuality,
    OCRPageResult,
    OCRTextBlock,
    STATUS_FAILED,
    STATUS_LOW_CONFIDENCE,
    STATUS_NO_TEXT_FOUND,
    STATUS_OCR_UNAVAILABLE,
    STATUS_READABLE,
    make_failed,
    make_unavailable,
)
from app.services.ocr.tesseract_provider import (
    MAX_OCR_PAGES,
    RENDER_DPI,
    TesseractProvider,
    get_default_provider,
)


# ── Fixture builders ──────────────────────────────────────────────────────────

def _blank_pdf() -> bytes:
    """Single-page 'blank' PDF — no drawn text. Tesseract returns no blocks."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    # Intentionally draw nothing so OCR has zero text to recognise.
    c.showPage()
    c.save()
    return buf.getvalue()


def _text_pdf(lines: list[str]) -> bytes:
    """A PDF page rendered via reportlab — text is REAL pixels for OCR."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 24)   # large enough for confident OCR at 200 dpi
    y = 760
    for line in lines:
        c.drawString(72, y, line)
        y -= 36
    c.save()
    return buf.getvalue()


def _multi_page_pdf(page_count: int) -> bytes:
    """Generate N blank pages so we can probe MAX_OCR_PAGES handling."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(page_count):
        c.setFont("Helvetica", 14)
        c.drawString(72, 720, f"Page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _tesseract_available() -> bool:
    """Mirror TesseractProvider.is_available() so tests can skip selectively."""
    return TesseractProvider().is_available()


# ── 1. Provider availability + name + ABC contract ──────────────────────────

class TestProviderContract:
    def test_get_default_provider_returns_a_provider_instance(self):
        p = get_default_provider()
        assert isinstance(p, OCRDiagnosticProvider)

    def test_provider_name_is_tesseract(self):
        assert TesseractProvider().name() == "tesseract"

    def test_is_available_is_a_bool(self):
        result = TesseractProvider().is_available()
        assert isinstance(result, bool)

    def test_is_available_caches_result(self):
        p = TesseractProvider()
        first = p.is_available()
        second = p.is_available()
        assert first == second
        # The cache attribute is set after the first call.
        assert getattr(p, "_available_cache", None) is not None


# ── 2. Graceful-missing handling (engine not installed) ─────────────────────

class TestProviderGracefulMissing:
    """
    These two tests must pass on EVERY developer machine, even when
    Tesseract IS installed. They verify the helpers + behaviour
    independent of the actual binary.
    """

    def test_make_unavailable_returns_valid_diagnostic(self):
        diag = make_unavailable()
        assert isinstance(diag, OCRDiagnostic)
        assert diag.diagnostic_status == STATUS_OCR_UNAVAILABLE
        assert diag.page_count == 0
        assert diag.pages == []
        assert diag.average_confidence == 0.0
        assert diag.user_message == "OCR is not installed on this server yet."

    def test_provider_with_forced_unavailable_returns_unavailable(self):
        """Force is_available() to False → diagnose() must NOT call _run()."""
        p = TesseractProvider()
        p._available_cache = False  # bypass real preflight

        # Pass garbage bytes — if _run() were called, fitz.open would raise.
        diag = p.diagnose(b"this is not a pdf at all")
        assert diag.diagnostic_status == STATUS_OCR_UNAVAILABLE
        assert diag.provider == "tesseract"


# ── 3. Failure-path safety (bad bytes never raise) ──────────────────────────

class TestProviderNeverRaises:
    """
    diagnose() promises NEVER to raise. These tests pass on every
    machine, regardless of Tesseract availability.
    """

    def test_diagnose_garbage_bytes_returns_diagnostic(self):
        p = TesseractProvider()
        diag = p.diagnose(b"definitely-not-a-pdf")
        assert isinstance(diag, OCRDiagnostic)
        # Either ocr_unavailable (no binary) or failed (bytes can't open).
        assert diag.diagnostic_status in (STATUS_OCR_UNAVAILABLE, STATUS_FAILED)

    def test_diagnose_empty_bytes_returns_diagnostic(self):
        p = TesseractProvider()
        diag = p.diagnose(b"")
        assert isinstance(diag, OCRDiagnostic)
        assert diag.diagnostic_status in (STATUS_OCR_UNAVAILABLE, STATUS_FAILED)

    def test_make_failed_strips_exception_text_from_user_message(self):
        diag = make_failed("tesseract", "RuntimeError: secret/path/leaked")
        # The user message MUST NOT include the technical message
        assert "secret" not in diag.user_message
        assert "path" not in diag.user_message
        # but the technical message field carries it for backend logs only
        assert "secret/path/leaked" in diag.technical_message
        assert diag.diagnostic_status == STATUS_FAILED


# ── 4. OCRDiagnostic dataclass shape stability ──────────────────────────────

class TestOCRDiagnosticShape:
    def test_diagnostic_serializes_to_dict(self):
        diag = make_unavailable()
        d = asdict(diag)
        assert isinstance(d, dict)
        # Fields the frontend depends on:
        for required in (
            "provider", "page_count", "pages", "full_text",
            "average_confidence", "detected_languages",
            "readable_pages", "unreadable_pages",
            "diagnostic_status", "user_message", "technical_message",
        ):
            assert required in d, f"field {required!r} missing from OCRDiagnostic"

    def test_text_block_dataclass_round_trips(self):
        block = OCRTextBlock(text="Müller", page=1, bbox=[0, 0, 10, 10], confidence=0.9)
        d = asdict(block)
        assert d == {
            "text": "Müller",
            "page": 1,
            "bbox": [0, 0, 10, 10],
            "confidence": 0.9,
            "language": None,
        }

    def test_page_quality_dataclass_round_trips(self):
        q = OCRPageQuality(
            page=1, width=1200, height=1700, dpi_estimate=200,
            text_block_count=42, average_confidence=0.81, readable=True,
        )
        d = asdict(q)
        assert d["readable"] is True
        assert d["issues"] == []

    def test_page_result_carries_blocks_and_quality(self):
        block = OCRTextBlock(text="hello", page=1, bbox=[0, 0, 1, 1], confidence=0.5)
        q = OCRPageQuality(page=1, width=1, height=1, dpi_estimate=200,
                           text_block_count=1, average_confidence=0.5, readable=False)
        page_result = OCRPageResult(page=1, blocks=[block], quality=q)
        assert page_result.blocks[0].text == "hello"
        assert page_result.quality.average_confidence == 0.5

    def test_low_confidence_threshold_is_065(self):
        # If this constant ever changes, frontend copy + Stage 4D gate
        # need to change in lockstep — make it a hard test.
        assert LOW_CONFIDENCE_THRESHOLD == 0.65


# ── 5. Live OCR — only run when Tesseract is installed ──────────────────────

@pytest.mark.skipif(not _tesseract_available(),
                    reason="Tesseract binary not installed in this environment")
class TestProviderWithRealTesseract:
    """
    These tests run end-to-end through the local Tesseract binary.
    They are skipped (NOT failed) on environments without Tesseract
    so CI doesn't fail when the binary is unavailable.
    """

    def test_blank_pdf_returns_no_text_found(self):
        diag = TesseractProvider().diagnose(_blank_pdf())
        assert diag.diagnostic_status == STATUS_NO_TEXT_FOUND
        assert diag.full_text == ""
        assert diag.average_confidence == 0.0

    def test_text_pdf_returns_readable_with_text(self):
        diag = TesseractProvider().diagnose(_text_pdf([
            "Hello World",
            "This is a test document",
            "Bürokratie Helfer Stage 4A",
        ]))
        assert diag.diagnostic_status == STATUS_READABLE
        assert diag.average_confidence >= LOW_CONFIDENCE_THRESHOLD
        # Tesseract should pick up at least the simple ASCII content.
        assert "Hello" in diag.full_text or "World" in diag.full_text

    def test_text_pdf_blocks_have_bbox_and_confidence(self):
        diag = TesseractProvider().diagnose(_text_pdf(["Hello World"]))
        assert diag.pages, "expected at least one page result"
        page = diag.pages[0]
        assert page.blocks, "expected at least one text block"
        for b in page.blocks:
            assert len(b.bbox) == 4
            assert all(isinstance(c, (int, float)) for c in b.bbox)
            assert 0.0 <= b.confidence <= 1.0
            assert b.page == 1

    def test_provider_reports_dpi_estimate_on_quality(self):
        diag = TesseractProvider().diagnose(_text_pdf(["Sample"]))
        assert diag.pages[0].quality.dpi_estimate == RENDER_DPI

    def test_caps_pages_at_max_ocr_pages(self):
        diag = TesseractProvider().diagnose(
            _multi_page_pdf(MAX_OCR_PAGES + 3)
        )
        # page_count reflects the WHOLE document, not just the OCR'd subset.
        assert diag.page_count == MAX_OCR_PAGES + 3
        # Pages beyond the cap are surfaced as empty page-results so the
        # frontend can still show "we processed N of M pages".
        capped = [p for p in diag.pages if p.page > MAX_OCR_PAGES]
        for p in capped:
            assert p.blocks == []
            assert p.quality.text_block_count == 0
            assert any("cap" in iss.lower() for iss in p.quality.issues)


# ── 6. Sanity — make sure the diagnostic shape AnalysisReport stores survives
#                a round-trip through asdict (the path process_pdf uses) ─────

class TestDiagnosticRoundTripForAnalysisReport:
    def test_unavailable_diagnostic_asdict_has_no_extra_keys(self):
        d = asdict(make_unavailable())
        # Snapshot of the exact keys an OCRDiagnostic carries — adding new
        # keys is fine but you must update this list AND the frontend type.
        assert set(d.keys()) == {
            "provider", "page_count", "pages", "full_text",
            "average_confidence", "detected_languages",
            "readable_pages", "unreadable_pages",
            "diagnostic_status", "user_message", "technical_message",
        }

    def test_failed_diagnostic_keeps_user_message_safe(self):
        d = asdict(make_failed("tesseract", "stack-trace-bytes"))
        assert "stack" not in d["user_message"]
        assert d["diagnostic_status"] == STATUS_FAILED
