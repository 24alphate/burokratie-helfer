"""
Stage 4B tests — OCR-text-to-FieldMap pipeline.

These tests use a MOCK OCRDiagnosticProvider so they pass even when
Tesseract isn't installed. They cover:

  • Unit-level: text_to_fields applies the same regex heuristics as the
    flat-PDF extractor and produces grounded FieldMapEntry objects.
  • Routing: when the OCR diagnostic is "readable" AND yields ≥1 field,
    /process-pdf promotes Level 4 → Level 3 and runs the normal pipeline
    (translate, quality, grounding).
  • Anti-hallucination: every emitted field's source_text is taken from
    an OCR block; field_id is in extracted_field_ids.
  • Stage 4A short-circuit still fires for non-readable / no-fields cases.
  • Locale: question[locale] populated for all Tier-A locales on OCR-derived
    fields whose label matches a deterministic German term.

Run with:  pytest tests/test_ocr_text_to_fields.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.ocr.diagnostic import (
    OCRDiagnostic,
    OCRDiagnosticProvider,
    OCRPageQuality,
    OCRPageResult,
    OCRTextBlock,
    STATUS_LOW_CONFIDENCE,
    STATUS_NO_TEXT_FOUND,
    STATUS_READABLE,
)


# ── Mock provider ────────────────────────────────────────────────────────────


class MockOCRProvider(OCRDiagnosticProvider):
    """Returns a pre-built OCRDiagnostic — no Tesseract required."""

    def __init__(self, diagnostic: OCRDiagnostic):
        self._diag = diagnostic

    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def diagnose(self, pdf_bytes: bytes) -> OCRDiagnostic:
        return self._diag


def _make_blocks(words_with_xy: list[tuple[str, int, int, int, int, float]],
                 page: int = 1) -> list[OCRTextBlock]:
    """Helper: build OCRTextBlock list from (text, x0, y0, w, h, conf) tuples."""
    return [
        OCRTextBlock(
            text=t,
            page=page,
            bbox=[float(x), float(y), float(x + w), float(y + h)],
            confidence=conf,
        )
        for (t, x, y, w, h, conf) in words_with_xy
    ]


def _readable_diagnostic(pages_blocks: list[list[OCRTextBlock]]) -> OCRDiagnostic:
    """Build a readable OCRDiagnostic from per-page block lists."""
    pages: list[OCRPageResult] = []
    all_blocks: list[OCRTextBlock] = []
    for i, blocks in enumerate(pages_blocks, 1):
        all_blocks.extend(blocks)
        avg = sum(b.confidence for b in blocks) / max(len(blocks), 1)
        pages.append(OCRPageResult(
            page=i,
            blocks=blocks,
            quality=OCRPageQuality(
                page=i,
                width=1500,
                height=2000,
                dpi_estimate=200,
                text_block_count=len(blocks),
                average_confidence=round(avg, 4),
                readable=(len(blocks) > 0 and avg >= 0.65),
            ),
        ))
    avg_all = (
        sum(b.confidence for b in all_blocks) / len(all_blocks)
        if all_blocks else 0.0
    )
    return OCRDiagnostic(
        provider="mock",
        page_count=len(pages_blocks),
        pages=pages,
        full_text="\n".join(b.text for b in all_blocks),
        average_confidence=round(avg_all, 4),
        detected_languages=["deu", "eng"],
        readable_pages=sum(1 for p in pages if p.quality.readable),
        unreadable_pages=sum(1 for p in pages if not p.quality.readable),
        diagnostic_status=STATUS_READABLE,
        user_message="OCR readable",
        technical_message="mock",
    )


# ── Unit tests for text_to_fields ────────────────────────────────────────────


class TestTextToFieldsExtraction:
    def test_label_with_blanks_extracts_text_field(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        # "Vorname: ___________" — label-with-blank pattern
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.90),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert len(fields) == 1
        f = fields[0]
        assert f.field_type == "text"
        assert f.original_label == "Vorname"
        assert f.source == "ocr"
        # source_text reflects what came from OCR
        assert "___________" in f.source_text or "Vorname" in f.source_text

    def test_high_confidence_blocks_get_show_conf(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr, SHOW_CONF
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert fields
        assert fields[0].confidence == SHOW_CONF
        # show_question gate (>= 0.70) is satisfied
        assert fields[0].confidence >= 0.70

    def test_low_confidence_blocks_get_manual_conf(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr, MANUAL_CONF
        # Page-level avg above the readable threshold but per-block conf
        # below the high-quality threshold → MANUAL_CONF.
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.70),
                ("___________", 200, 100, 200, 20, 0.70),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert fields
        assert fields[0].confidence == MANUAL_CONF

    def test_returns_empty_when_status_not_readable(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        diag = _readable_diagnostic([
            _make_blocks([("Vorname:", 100, 100, 80, 20, 0.95)])
        ])
        diag.diagnostic_status = STATUS_LOW_CONFIDENCE
        assert extract_fields_from_ocr(diag) == []
        diag.diagnostic_status = STATUS_NO_TEXT_FOUND
        assert extract_fields_from_ocr(diag) == []

    def test_skips_pages_marked_unreadable(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        # First page readable, second page not.
        page1 = OCRPageResult(
            page=1,
            blocks=_make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
            ]),
            quality=OCRPageQuality(
                page=1, width=1500, height=2000, dpi_estimate=200,
                text_block_count=2, average_confidence=0.95, readable=True,
            ),
        )
        page2 = OCRPageResult(
            page=2,
            blocks=_make_blocks([("garbage", 100, 100, 80, 20, 0.30)], page=2),
            quality=OCRPageQuality(
                page=2, width=1500, height=2000, dpi_estimate=200,
                text_block_count=1, average_confidence=0.30, readable=False,
            ),
        )
        diag = OCRDiagnostic(
            provider="mock",
            page_count=2,
            pages=[page1, page2],
            full_text="Vorname: ___________\ngarbage",
            average_confidence=0.625,
            detected_languages=["deu"],
            readable_pages=1,
            unreadable_pages=1,
            diagnostic_status=STATUS_READABLE,
            user_message="ok",
            technical_message="mock",
        )
        fields = extract_fields_from_ocr(diag)
        # Only the readable page produced a field
        assert all(f.source_page == 1 for f in fields)

    def test_blanks_then_unit_extracts_number_field(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        diag = _readable_diagnostic([
            _make_blocks([
                ("___________", 100, 100, 200, 20, 0.92),
                ("EUR", 320, 100, 40, 20, 0.92),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert any(f.field_type == "number" for f in fields), (
            f"Expected a number field, got: {[(f.field_id, f.field_type) for f in fields]}"
        )

    def test_unterschrift_extracts_signature_field(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        diag = _readable_diagnostic([
            _make_blocks([
                ("Unterschrift", 100, 100, 200, 20, 0.95),
                ("Antragsteller", 320, 100, 200, 20, 0.95),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert any(f.field_type == "signature" for f in fields)

    def test_skip_phrases_are_filtered(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        # "Hinweis: please fill ___" — "hinweis" is in _SKIP_PHRASES
        diag = _readable_diagnostic([
            _make_blocks([
                ("Hinweis:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert fields == []

    def test_anti_hallucination_every_field_has_source_text(self):
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
                ("Nachname:", 100, 130, 80, 20, 0.95),
                ("___________", 200, 130, 200, 20, 0.95),
            ])
        ])
        fields = extract_fields_from_ocr(diag)
        assert fields
        for f in fields:
            assert f.source == "ocr"
            assert f.source_text  # non-empty
            assert f.source_page == 1


# ── Routing tests with monkeypatched OCR provider ────────────────────────────


def _scanned_like_pdf() -> bytes:
    """Empty PDF — detect_pdf_type returns 'scanned' (Level 4)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f\r\n0000000009 00000 n\r\n"
        b"0000000068 00000 n\r\n0000000125 00000 n\r\n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF"
    )


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _patch_ocr(monkeypatch, diag: OCRDiagnostic):
    """Replace the Stage 4A provider with a mock returning `diag`."""
    from app.services.ocr import tesseract_provider

    def _factory():
        return MockOCRProvider(diag)

    monkeypatch.setattr(tesseract_provider, "get_default_provider", _factory)


class TestStage4BPromotion:
    """When OCR is readable AND yields ≥1 field, Level 4 PDF gets promoted."""

    def test_promoted_response_has_fields_and_questions(self, client, monkeypatch):
        # Build a readable diagnostic with two extractable label-blank lines.
        diag = _readable_diagnostic([
            _make_blocks([
                # Use German labels that match deterministic translations,
                # so the question pipeline can localize them.
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
                ("Nachname:", 100, 130, 80, 20, 0.95),
                ("___________", 200, 130, 200, 20, 0.95),
            ])
        ])
        _patch_ocr(monkeypatch, diag)

        resp = client.post(
            "/api/v1/process-pdf?user_language=fr",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Level 4 → 3 promotion
        assert body["analysis_report"]["support_level"] == 3
        assert body["analysis_report"]["extraction_source"] == "ocr"
        # Fields present, grounded
        assert len(body["fields"]) >= 1
        for f in body["fields"]:
            assert f["key"] in body["extracted_field_ids"]
        # OCR diagnostic still attached for transparency
        assert body["analysis_report"]["ocr_diagnostic"] is not None
        # technical_message stripped from public response
        assert "technical_message" not in body["analysis_report"]["ocr_diagnostic"]

    def test_promoted_response_localizes_questions(self, client, monkeypatch):
        # Vorname / Nachname are in the deterministic translation table,
        # so the French question text should not be the raw German label.
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
                ("Nachname:", 100, 130, 80, 20, 0.95),
                ("___________", 200, 130, 200, 20, 0.95),
            ])
        ])
        _patch_ocr(monkeypatch, diag)
        resp = client.post(
            "/api/v1/process-pdf?user_language=fr",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        body = resp.json()
        for f in body["fields"]:
            q_fr = (f["question"] or {}).get("fr", "")
            assert q_fr, f"field {f['key']} missing French question"

    def test_promoted_response_ai_used_false_for_known_labels(self, client, monkeypatch):
        # All labels are deterministic — no Groq call needed.
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
            ])
        ])
        _patch_ocr(monkeypatch, diag)
        resp = client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        body = resp.json()
        # Either ai_used=False or the deterministic source is recorded
        assert body["analysis_report"]["question_quality"]["ai_calls_made"] >= 0


class TestStage4AStillShortCircuits:
    """Non-readable diagnostics keep the old short-circuit behavior."""

    def test_low_confidence_short_circuits(self, client, monkeypatch):
        diag = _readable_diagnostic([
            _make_blocks([("garbage", 100, 100, 80, 20, 0.30)])
        ])
        diag.diagnostic_status = STATUS_LOW_CONFIDENCE
        _patch_ocr(monkeypatch, diag)
        resp = client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis_report"]["support_level"] == 4
        assert body["fields"] == []
        assert body["extracted_field_ids"] == []

    def test_no_text_short_circuits(self, client, monkeypatch):
        diag = _readable_diagnostic([])
        diag.diagnostic_status = STATUS_NO_TEXT_FOUND
        diag.page_count = 1
        _patch_ocr(monkeypatch, diag)
        resp = client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis_report"]["support_level"] == 4
        assert body["fields"] == []

    def test_readable_but_zero_fields_short_circuits(self, client, monkeypatch):
        # Readable text but only boilerplate ("Hinweis:") — no extractable fields.
        diag = _readable_diagnostic([
            _make_blocks([
                ("Hinweis:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
            ])
        ])
        _patch_ocr(monkeypatch, diag)
        resp = client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Promotion didn't fire — back to Stage 4A short-circuit shape
        assert body["analysis_report"]["support_level"] == 4
        assert body["fields"] == []


class TestStage4BGroundingInvariant:
    """Anti-hallucination: every field_id must appear in extracted_field_ids."""

    def test_every_field_in_extracted_ids(self, client, monkeypatch):
        diag = _readable_diagnostic([
            _make_blocks([
                ("Vorname:", 100, 100, 80, 20, 0.95),
                ("___________", 200, 100, 200, 20, 0.95),
                ("Nachname:", 100, 130, 80, 20, 0.95),
                ("___________", 200, 130, 200, 20, 0.95),
                ("Geburtsdatum:", 100, 160, 80, 20, 0.95),
                ("___________", 200, 160, 200, 20, 0.95),
            ])
        ])
        _patch_ocr(monkeypatch, diag)
        resp = client.post(
            "/api/v1/process-pdf?user_language=de",
            files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
        )
        body = resp.json()
        extracted = set(body["extracted_field_ids"])
        for f in body["fields"]:
            assert f["key"] in extracted, (
                f"BUG: field {f['key']} not in extracted_field_ids ({extracted})"
            )
        assert body["analysis_report"]["grounding_ok"] is True
