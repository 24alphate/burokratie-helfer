"""
Locale-coverage tests for Tier-A languages on both Level 1 verified templates.

Spec: every shown FieldDefinition must have a non-empty question[selected_locale]
that is not just the original German label, the question_source must be
verified or semantic, and the locale_quality_report must report
ready_for_locale=true with no fallback or missing entries.

Tier-A locales: en, de, fr, ar, tr, sq

Run with:  pytest tests/test_locale_coverage.py -v
"""
from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

TIER_A = ["en", "de", "fr", "ar", "tr", "sq"]


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# ── Fixtures: build BuT (synthetic) and load KG1 PDFs ────────────────────────


def _but_pdf_bytes() -> bytes:
    """Build a minimal flat PDF whose extracted text matches the BuT fingerprint."""
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


KG1_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "familienkasse_kg1_v1.pdf",
)


@pytest.fixture(scope="module")
def kg1_pdf_bytes() -> bytes:
    if not os.path.exists(KG1_PDF_PATH):
        pytest.skip(f"KG1 PDF not present at {KG1_PDF_PATH}")
    with open(KG1_PDF_PATH, "rb") as f:
        return f.read()


def _process(client, pdf_bytes: bytes, locale: str) -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Script detection helpers ─────────────────────────────────────────────────


_ARABIC_RE = re.compile(r"[؀-ۿ]")
_LATIN_RE = re.compile(r"[A-Za-z]")
# Albanian-specific letters that distinguish it from generic Latin.
_ALBANIAN_HINT_RE = re.compile(r"[ëçË Ç]|cili|cila|emri|adresa|datën|data|nuk|nga|ose|pas|para")


def _is_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text))


def _looks_latin(text: str) -> bool:
    return bool(_LATIN_RE.search(text))


# ── BuT — synthetic flat-PDF Level 1 template ─────────────────────────────────


class TestBuTAcrossTierA:
    @pytest.fixture(scope="class")
    def but_pdf(self):
        return _but_pdf_bytes()

    @pytest.mark.parametrize("locale", TIER_A)
    def test_support_level_and_template(self, client, but_pdf, locale):
        body = _process(client, but_pdf, locale)
        rep = body["analysis_report"]
        assert rep["support_level"] == 1
        assert rep["template_id"] == "jobcenter_but_v1"
        assert rep["question_quality"]["weak_questions"] == 0
        assert rep["question_quality"]["ai_calls_made"] == 0

    @pytest.mark.parametrize("locale", TIER_A)
    def test_every_shown_field_has_question_in_selected_locale(self, client, but_pdf, locale):
        body = _process(client, but_pdf, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        assert len(shown) > 0
        for f in shown:
            q = (f.get("question") or {}).get(locale, "")
            assert q, f"Field {f['key']!r} missing question[{locale}]"

    @pytest.mark.parametrize("locale", ["fr", "ar", "tr", "sq"])
    def test_main_question_is_not_english_for_non_english_tier_a(
        self, client, but_pdf, locale,
    ):
        # The English text for the same field should NOT equal the localized
        # text for fr/ar/tr/sq. This catches silent en-fallback.
        body = _process(client, but_pdf, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        assert len(shown) > 0
        same_as_en = []
        for f in shown:
            q_local = (f.get("question") or {}).get(locale, "")
            q_en = (f.get("question") or {}).get("en", "")
            if q_local and q_en and q_local == q_en:
                # Single-token replies (e.g. "2026") may legitimately match.
                if len(q_local) > 5:
                    same_as_en.append((f["key"], q_local))
        assert same_as_en == [], (
            f"Locale {locale}: shown questions identical to English (silent fallback): "
            f"{same_as_en}"
        )

    @pytest.mark.parametrize("locale", TIER_A)
    def test_question_source_is_verified_or_semantic(self, client, but_pdf, locale):
        body = _process(client, but_pdf, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        for f in shown:
            assert f.get("question_source") in ("verified", "semantic"), (
                f"Locale {locale}: field {f['key']} source={f.get('question_source')!r}"
            )

    @pytest.mark.parametrize("locale", TIER_A)
    def test_main_question_is_not_raw_german_label(self, client, but_pdf, locale):
        body = _process(client, but_pdf, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        for f in shown:
            q = (f.get("question") or {}).get(locale, "").strip()
            orig = (f.get("original_label") or "").strip()
            if locale == "de":
                continue  # German is allowed to match the original label
            assert q.lower() != orig.lower() or not orig, (
                f"Locale {locale}: field {f['key']} renders raw label: {q!r}"
            )

    @pytest.mark.parametrize("locale", TIER_A)
    def test_locale_quality_report_ready(self, client, but_pdf, locale):
        body = _process(client, but_pdf, locale)
        rep = body["analysis_report"]["locale_quality_report"]
        assert rep["selected_locale"] == locale
        assert rep["ready_for_locale"] is True, (
            f"Locale {locale} not ready: missing={rep['missing_questions']} "
            f"fallback={rep['fallback_field_ids']}"
        )
        assert rep["fallback_questions"] == 0
        assert rep["missing_questions"] == []
        # Tier-A all ready
        assert rep["tier_a_ready"] is True

    def test_arabic_questions_contain_arabic_script(self, client, but_pdf):
        body = _process(client, but_pdf, "ar")
        shown = [f for f in body["fields"] if f.get("show_question")]
        # At least 80% of questions should contain Arabic characters.
        with_arabic = sum(
            1 for f in shown if _is_arabic((f.get("question") or {}).get("ar", ""))
        )
        assert with_arabic / max(len(shown), 1) >= 0.8, (
            f"Only {with_arabic}/{len(shown)} Arabic questions contain Arabic script"
        )


# ── KG1 — real verified template ─────────────────────────────────────────────


class TestKG1AcrossTierA:
    @pytest.mark.parametrize("locale", TIER_A)
    def test_support_level_and_template(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        rep = body["analysis_report"]
        assert rep["support_level"] == 1
        assert rep["template_id"] == "familienkasse_kg1_v1"
        assert rep["question_quality"]["weak_questions"] == 0
        assert rep["question_quality"]["ai_calls_made"] == 0

    @pytest.mark.parametrize("locale", TIER_A)
    def test_every_shown_field_has_question(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        assert len(shown) > 0
        missing = [f["key"] for f in shown if not (f.get("question") or {}).get(locale)]
        assert missing == [], f"{locale}: fields missing question: {missing}"

    @pytest.mark.parametrize("locale", ["fr", "ar", "tr", "sq"])
    def test_main_question_is_localized_not_english(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        same_as_en = []
        for f in shown:
            q_local = (f.get("question") or {}).get(locale, "")
            q_en = (f.get("question") or {}).get("en", "")
            if q_local and q_en and q_local == q_en and len(q_local) > 5:
                same_as_en.append((f["key"], q_local))
        assert same_as_en == [], (
            f"{locale}: identical-to-English questions: {same_as_en}"
        )

    @pytest.mark.parametrize("locale", TIER_A)
    def test_question_source_is_verified(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        bad = [f["key"] for f in shown if f.get("question_source") != "verified"]
        assert bad == [], f"{locale}: non-verified source for fields {bad}"

    @pytest.mark.parametrize("locale", TIER_A)
    def test_main_question_is_not_raw_german(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        shown = [f for f in body["fields"] if f.get("show_question")]
        if locale == "de":
            return  # German is allowed to match
        for f in shown:
            q = (f.get("question") or {}).get(locale, "").strip()
            orig = (f.get("original_label") or "").strip()
            assert q.lower() != orig.lower() or not orig, (
                f"{locale}: field {f['key']} = raw German label {orig!r}"
            )

    @pytest.mark.parametrize("locale", TIER_A)
    def test_locale_quality_report_ready(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        rep = body["analysis_report"]["locale_quality_report"]
        assert rep["selected_locale"] == locale
        assert rep["ready_for_locale"] is True, (
            f"{locale} KG1 not ready: missing={rep['missing_questions']} "
            f"fallback={rep['fallback_field_ids']}"
        )
        assert rep["fallback_questions"] == 0
        assert rep["missing_questions"] == []
        assert rep["tier_a_ready"] is True

    def test_arabic_kg1_contains_arabic_script(self, client, kg1_pdf_bytes):
        body = _process(client, kg1_pdf_bytes, "ar")
        shown = [f for f in body["fields"] if f.get("show_question")]
        with_arabic = sum(
            1 for f in shown if _is_arabic((f.get("question") or {}).get("ar", ""))
        )
        assert with_arabic / max(len(shown), 1) >= 0.8

    def test_albanian_kg1_uses_latin(self, client, kg1_pdf_bytes):
        body = _process(client, kg1_pdf_bytes, "sq")
        shown = [f for f in body["fields"] if f.get("show_question")]
        # Albanian uses Latin script — every question must have Latin chars
        for f in shown:
            q = (f.get("question") or {}).get("sq", "")
            assert _looks_latin(q), f"Albanian question for {f['key']} has no Latin: {q!r}"


# ── Strict locale-completeness for verified template entries ─────────────────


class TestVerifiedTemplateLocaleCompleteness:
    """
    Direct unit-level check: for every verified entry that has at least one
    Tier-A locale, it must have ALL Tier-A locales. Stops a future PR from
    landing partial coverage.
    """

    def test_verified_by_field_id_tier_a_complete(self):
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        gaps: list[tuple[str, list[str]]] = []
        for fid, entry in VERIFIED_BY_FIELD_ID.items():
            present_tier_a = [loc for loc in TIER_A if loc in entry]
            if not present_tier_a:
                continue  # entry doesn't claim Tier-A; skip
            missing = [loc for loc in TIER_A if loc not in entry]
            if missing:
                gaps.append((fid, missing))
        assert gaps == [], (
            "Tier-A locale gaps in VERIFIED_BY_FIELD_ID. "
            f"Each listed entry has *some* Tier-A locales but is missing others: {gaps}"
        )

    def test_verified_by_label_tier_a_complete(self):
        from app.services.verified_questions import VERIFIED_BY_LABEL
        gaps: list[tuple[str, list[str]]] = []
        for label, entry in VERIFIED_BY_LABEL.items():
            present_tier_a = [loc for loc in TIER_A if loc in entry]
            if not present_tier_a:
                continue
            missing = [loc for loc in TIER_A if loc not in entry]
            if missing:
                gaps.append((label, missing))
        assert gaps == [], (
            f"Tier-A locale gaps in VERIFIED_BY_LABEL: {gaps}"
        )


# ── Locale quality reporter — pure unit ─────────────────────────────────────


class TestLocaleQualityReporter:
    def test_ready_when_all_localized(self):
        from app.services.locale_quality import build_locale_quality_report
        from types import SimpleNamespace

        f = SimpleNamespace(
            key="x",
            question={"en": "Q?", "de": "F?", "fr": "Q ?", "ar": "س؟", "tr": "S?", "sq": "P?"},
            original_label="Frage",
        )
        rep = build_locale_quality_report(
            shown_fields=[f],
            selected_locale="fr",
            document_language="de",
            extraction_source="verified_template",
            support_level=1,
        )
        assert rep["ready_for_locale"] is True
        assert rep["tier_a_ready"] is True
        assert rep["per_locale"]["sq"]["ready_for_locale"] is True

    def test_not_ready_when_missing_locale(self):
        from app.services.locale_quality import build_locale_quality_report
        from types import SimpleNamespace

        f = SimpleNamespace(
            key="x",
            question={"en": "Q?", "de": "F?"},  # missing fr/ar/tr/sq
            original_label="Frage",
        )
        rep = build_locale_quality_report(
            shown_fields=[f],
            selected_locale="fr",
            document_language="de",
            extraction_source="verified_template",
            support_level=1,
        )
        assert rep["ready_for_locale"] is False
        assert rep["per_locale"]["en"]["ready_for_locale"] is True
        assert rep["per_locale"]["fr"]["ready_for_locale"] is False
        assert rep["tier_a_ready"] is False

    def test_fallback_to_german_label_counts_as_fallback(self):
        from app.services.locale_quality import build_locale_quality_report
        from types import SimpleNamespace

        # French question is the German label — counts as fallback, not localized.
        f = SimpleNamespace(
            key="x",
            question={"en": "Q?", "de": "Frage", "fr": "Frage",
                      "ar": "س؟", "tr": "S?", "sq": "P?"},
            original_label="Frage",
        )
        rep = build_locale_quality_report(
            shown_fields=[f],
            selected_locale="fr",
            document_language="de",
            extraction_source="verified_template",
            support_level=1,
        )
        assert rep["fallback_questions"] == 1
        assert rep["ready_for_locale"] is False
