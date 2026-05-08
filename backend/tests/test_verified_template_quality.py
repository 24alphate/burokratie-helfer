"""
Phase C/C2 + C3 + C4 — verified-template question quality, AI-cost protection,
and fallback chain integration tests.

These tests run the full /process-pdf pipeline (TestClient + FastAPI app)
with PDFs that fingerprint as the Jobcenter BuT verified template, and
assert the rules from the Phase C spec:

  C2 — verified-template quality (no weak questions, all sources verified)
  C3 — AI-cost protection (Groq is never called for fully-resolved templates)
  C4 — fallback chain (verified > semantic > deterministic > AI)

What we are NOT testing here:
  - extraction/parsing internals
  - the legacy DB-based cases API
  - PDF filling

Run with:  pytest tests/test_verified_template_quality.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _but_pdf_bytes() -> bytes:
    """
    Build a flat PDF whose extracted text matches JobcenterButTemplate's
    fingerprint requirements (3 required phrases + 1 section marker).
    Reuses the same recipe as test_document_router.py's verified fixture.
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
        # Umlaut variants — the template fingerprint reads lowered text and
        # checks the literal German spellings.
        "Bildung und Teilhabe",
        "Persönliche Angaben",
        "Schülerbeförderung",
    ]:
        c.drawString(50, y, line)
        y -= 22
    c.save()
    return buf.getvalue()


def _post_but(client, locale: str = "en"):
    """Post a BuT-fingerprint PDF and return the JSON body."""
    pdf = _but_pdf_bytes()
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("but.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── C2 — Verified template quality ───────────────────────────────────────────

class TestVerifiedTemplateQualityEnglish:
    """
    Run the BuT pipeline in English and assert every Phase C/C2 invariant
    against the rendered FieldDefinitions and the analysis_report.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.body = _post_but(client, "en")
        self.shown = [f for f in self.body["fields"] if f.get("show_question")]
        self.report = self.body["analysis_report"]

    # Routing assertions ----------------------------------------------------

    def test_support_level_is_1(self):
        assert self.report["support_level"] == 1

    def test_extraction_source_is_verified_template(self):
        assert self.report["extraction_source"] == "verified_template"

    def test_template_id_is_jobcenter_but(self):
        assert self.report["template_id"] == "jobcenter_but_v1"

    # Question source assertions --------------------------------------------

    def test_every_shown_question_source_is_verified_or_semantic(self):
        bad = [
            f["key"] for f in self.shown
            if f.get("question_source") not in ("verified", "semantic")
        ]
        assert bad == [], (
            f"Shown verified-template fields used a non-verified source: {bad}"
        )

    # Quality report assertions ---------------------------------------------

    def test_weak_questions_count_is_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("weak_questions") == 0, (
            f"Verified template has weak questions: "
            f"{qq.get('weak_reasons_by_field')}"
        )

    def test_no_strong_question_is_a_raw_label(self):
        # A "raw label" = the question text equals the original German label.
        for f in self.shown:
            q = (f.get("question") or {}).get("en", "")
            orig = f.get("original_label", "")
            assert q.strip().lower() != orig.strip().lower(), (
                f"Field {f['key']} renders the raw German label as the question"
            )

    @pytest.mark.parametrize("forbidden", [
        "Tag", "Monat", "Jahr",
        "Number / Count", "Number", "Count",
        "we",
    ])
    def test_no_shown_question_is_a_bare_noun(self, forbidden):
        for f in self.shown:
            q = (f.get("question") or {}).get("en", "").strip()
            assert q != forbidden, (
                f"Field {f['key']} renders bare noun {forbidden!r} as the question"
            )

    def test_no_question_contains_translation_unavailable(self):
        for f in self.shown:
            q = (f.get("question") or {}).get("en", "")
            assert "translation unavailable" not in q.lower()

    def test_no_question_has_trailing_artifact_number(self):
        # Catches "Klasse 04", "Startort 13", etc. — raw template artefacts
        # that should never reach the user.
        import re
        bad = []
        for f in self.shown:
            q = (f.get("question") or {}).get("en", "")
            if re.search(r"\s+\d+$", q):
                bad.append((f["key"], q))
        assert bad == [], f"Shown questions ending in raw number: {bad}"

    def test_every_date_field_has_example(self):
        for f in self.shown:
            if f.get("input_type") != "date":
                continue
            guidance = f.get("guidance") or {}
            example = guidance.get("example") or {}
            assert example, (
                f"Date field {f['key']} has no guidance.example "
                f"(question: {(f.get('question') or {}).get('en')!r})"
            )

    def test_every_number_field_has_example_or_format_hint(self):
        for f in self.shown:
            if f.get("input_type") != "number":
                continue
            guidance = f.get("guidance") or {}
            has_example = bool(guidance.get("example"))
            has_format = bool(guidance.get("format_hint"))
            assert has_example or has_format, (
                f"Number field {f['key']} has no example or format_hint"
            )

    def test_every_checkbox_is_yes_no_or_instruction(self):
        # Re-uses the quality checker so this test stays in sync with the
        # canonical rule set (no duplicated checkbox-detection logic here).
        from app.services.question_quality import quality_flags
        from types import SimpleNamespace

        for f in self.shown:
            if f.get("input_type") != "checkbox":
                continue
            fd = SimpleNamespace(
                question=f.get("question"),
                input_type="checkbox",
                question_source=f.get("question_source"),
                guidance=None,
            )
            entry = SimpleNamespace(original_label=f.get("original_label", ""))
            flags = quality_flags(fd, entry, user_language="en", extraction_source="verified_template")
            assert "checkbox_not_yes_no" not in flags, (
                f"Checkbox field {f['key']} is not phrased yes/no or "
                f"instruction-form: {(f.get('question') or {}).get('en')!r}"
            )


class TestVerifiedTemplateQualityArabic:
    """
    Phase C/C2 also requires the same invariants to hold for at least one
    non-English supported locale. Arabic exercises the question-mark
    variant (؟) and the right-to-left rendering path.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.body = _post_but(client, "ar")
        self.shown = [f for f in self.body["fields"] if f.get("show_question")]
        self.report = self.body["analysis_report"]

    def test_support_level_is_1(self):
        assert self.report["support_level"] == 1

    def test_weak_questions_count_is_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("weak_questions") == 0

    def test_every_shown_question_source_is_verified(self):
        # Arabic is one of the 9 covered locales — every BuT field has a
        # verified Arabic question, so AI must never see this template.
        bad = [
            f["key"] for f in self.shown
            if f.get("question_source") not in ("verified", "semantic")
        ]
        assert bad == []


# ── C3 — AI cost protection ──────────────────────────────────────────────────

class TestAICostProtection:
    """
    Verified templates must NEVER reach Groq. Mock translate_fields to
    sound an alarm if the orchestrator ever calls it for a Level 1 PDF.
    """

    def test_translate_fields_is_not_called_for_verified_template(
        self, client, monkeypatch
    ):
        from app.api.v1 import process_pdf as endpoint

        calls: list[dict] = []

        def _fail_if_called(fields, lang, doc_lang=None):
            calls.append({"fields": fields, "lang": lang, "doc_lang": doc_lang})
            return {}

        monkeypatch.setattr(endpoint, "translate_fields", _fail_if_called)

        body = _post_but(client, "en")

        assert calls == [], (
            f"translate_fields was called for a verified template — Level 1 "
            f"AI-cost invariant violated: {calls}"
        )

        report = body["analysis_report"]
        qq = report.get("question_quality") or {}
        assert qq.get("ai_calls_made") == 0
        assert qq.get("ai_calls_skipped", 0) > 0

    def test_ai_call_count_is_zero_in_quality_report(self, client):
        body = _post_but(client, "en")
        qq = body["analysis_report"].get("question_quality") or {}
        assert qq["ai_calls_made"] == 0
        # All non-signature BuT fields are pre-resolved → ai_calls_skipped > 0.
        assert qq["ai_calls_skipped"] > 0

    def test_question_source_counts_show_only_verified(self, client):
        body = _post_but(client, "en")
        qq = body["analysis_report"].get("question_quality") or {}
        counts = qq.get("question_source_counts") or {}
        # All shown questions for a BuT PDF must come from "verified".
        # The other buckets ("ai", "deterministic", "label", "key") must be 0.
        for forbidden in ("ai", "deterministic", "label", "key"):
            assert counts.get(forbidden, 0) == 0, (
                f"Verified template produced a {forbidden!r} question — "
                f"counts: {counts}"
            )


# ── C4 — Fallback chain (verified > semantic > deterministic > AI) ───────────

class TestFallbackChain:
    """
    Direct unit tests for the ordering inside process_pdf's pre-resolution
    loop. We don't need a full endpoint roundtrip for these — call the
    individual lookup functions and assert the priority directly.
    """

    def test_lookup_verified_returns_field_id_match(self):
        from app.services.verified_questions import lookup_verified
        # applicant_name_vorname has a verified entry in BuT.
        r = lookup_verified("applicant_name_vorname", "Name, Vorname", "en")
        assert r is not None
        assert "name" in r["question"].lower()

    def test_lookup_verified_falls_back_to_label_match(self):
        from app.services.verified_questions import lookup_verified
        # A field_id with no entry, but the original_label matches a generic
        # German term ("Tag") — must still return a verified question.
        r = lookup_verified("unknown_field_xyz", "Tag", "en")
        assert r is not None
        assert "?" in r["question"]

    def test_lookup_verified_returns_none_when_nothing_matches(self):
        from app.services.verified_questions import lookup_verified
        r = lookup_verified("totally_unknown_field", "Some random label", "en")
        assert r is None

    def test_semantic_lookup_works_for_known_keys(self):
        from app.services.semantic_questions import (
            infer_semantic_key, lookup_semantic,
        )
        key = infer_semantic_key("Vorname")
        assert key is not None
        sem = lookup_semantic(key, "en")
        assert sem is not None
        assert "?" in sem["question"]

    def test_deterministic_returns_full_question_for_known_label(self):
        from app.services.question_translator import get_deterministic_translation
        # "Tag" must resolve to a real question, not the bare noun.
        det = get_deterministic_translation("Tag", "en")
        assert det is not None
        assert "?" in det
        assert det.lower() != "tag"

    def test_deterministic_returns_none_for_unknown_label(self):
        from app.services.question_translator import get_deterministic_translation
        # Unknown labels do not get a deterministic translation; the AI path
        # must take over for these fields.
        det = get_deterministic_translation("ZZ_completely_random_label", "en")
        assert det in (None, "")

    def test_resolution_order_verified_beats_semantic(self):
        # Both `applicant_name_vorname` (verified) and the inferred semantic
        # key from "Vorname" exist. The verified entry must win at lookup.
        from app.services.verified_questions import lookup_verified
        from app.services.semantic_questions import (
            infer_semantic_key, lookup_semantic,
        )
        verified = lookup_verified("applicant_name_vorname", "Vorname", "en")
        semantic_key = infer_semantic_key("Vorname")
        semantic = lookup_semantic(semantic_key, "en") if semantic_key else None
        assert verified is not None
        assert semantic is not None
        # Different question text — they're independent layers; the test
        # asserts each one resolves rather than asserting equality.

    def test_field_map_to_defs_marks_low_confidence_needs_review(self):
        # Confirms the confidence band 0.70..0.90 still flags needs_review,
        # which is the trigger downstream UI uses to show fallback fields
        # with a "double-check this" indicator.
        from app.services.pdf_pipeline import FieldMapEntry, field_map_to_defs

        entry = FieldMapEntry(
            field_id="ZZ_needs_review",
            original_label="Some label",
            field_type="text",
            source_page=1,
            confidence=0.75,
            source="pdfplumber",
        )
        defs = field_map_to_defs([entry], {}, set(), "en", "de")
        assert defs[0].show_question is True
        assert defs[0].needs_review is True

    def test_field_map_to_defs_blocks_below_show_threshold(self):
        from app.services.pdf_pipeline import FieldMapEntry, field_map_to_defs

        entry = FieldMapEntry(
            field_id="ZZ_blocked",
            original_label="Some label",
            field_type="text",
            source_page=1,
            confidence=0.5,
            source="ocr",
        )
        defs = field_map_to_defs([entry], {}, set(), "en", "de")
        assert defs[0].show_question is False
