"""
Phase F6 — KG1 round-trip fill tests.

These tests run against the REAL Familienkasse KG1 PDF (must exist at
templates_source/familienkasse_kg1_v1.pdf). They prove that the second
Level 1 verified template is end-to-end usable: the routing matches, the
fill backend writes to the right widgets, manual fields stay blank, and
all output-safety invariants from Phase E + F/0 hold.

Test layout follows the F6 spec:
  1. Process-pdf route assertions
  2. Basic AcroForm fill round-trip + readback
  3. Radio group fill (Familienstand + Bank account-holder + invalid value)
  4. Manual widgets stay blank
  5. Tabelle 1 single-row fill
  6. Grounding tests
  7. Output safety (mock failures)

Run with:  pytest tests/test_familienkasse_kg1.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

# fitz/PyMuPDF is required because KG1 uses fill_strategy="fitz_acroform"
pytest.importorskip("fitz", reason="PyMuPDF required for KG1 round-trip fill tests")

from app.services.form_templates.familienkasse_kg1 import (
    # text widgets
    W_KG_NR, W_TELEFON, W_ANZAHL_ANLAGEN,
    W_APP_TITEL, W_APP_NAME, W_APP_VORNAME, W_APP_GEBURTSNAME,
    W_APP_GEB_DATUM, W_APP_GEB_ORT, W_APP_GESCHLECHT, W_APP_STAATSANG,
    W_APP_ANSCHRIFT, W_FS_SEIT,
    W_PRT_NAME, W_PRT_VORNAME, W_PRT_GEB_DATUM, W_PRT_ANSCHRIFT,
    W_BANK_IBAN, W_BANK_BIC, W_BANK_NAME, W_BANK_OWNER_NAME,
    W_AP_NAME, W_AP_VORNAME, W_AP_ANSCHRIFT,
    W_DATUM_1, W_DATUM_2,
    # radio group widgets
    W_FS_LEDIG, W_FS_VERHEIRATET, W_FS_PARTNER, W_FS_GESCHIEDEN,
    W_FS_AUFGEHOBEN, W_FS_GETRENNT, W_FS_VERWITWET,
    W_BANK_OWNER_APP, W_BANK_OWNER_OTH,
    # logical radio field IDs
    LOGICAL_FAMILIENSTAND, LOGICAL_BANK_OWNER,
    # manual widgets
    W_APP_STEUER_ID_1, W_APP_STEUER_ID_2, W_APP_STEUER_ID_3, W_APP_STEUER_ID_4,
    W_PRT_STEUER_ID_1, W_PRT_STEUER_ID_2, W_PRT_STEUER_ID_3, W_PRT_STEUER_ID_4,
    # tabelle helper
    _w_t1, _w_t2,
)

# ── Constants ────────────────────────────────────────────────────────────────

KG1_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "familienkasse_kg1_v1.pdf",
)
EXPECTED_PAGES = 5
EXPECTED_SHOWN = 52
EXPECTED_MANUAL = 33


@pytest.fixture(scope="module")
def kg1_pdf_bytes() -> bytes:
    if not os.path.exists(KG1_PDF_PATH):
        pytest.skip(f"KG1 PDF not present at {KG1_PDF_PATH}")
    with open(KG1_PDF_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _process(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("kg1.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill(client, token: str, answers: dict):
    return client.post(
        "/api/v1/fill-pdf",
        json={"pdf_token": token, "answers": answers, "field_labels": {}},
    )


def _readback(pdf_bytes: bytes) -> dict:
    """Return {field_name: /V value} for every widget that has a /V."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    out = {}
    for k, v in (reader.get_fields() or {}).items():
        out[k] = v.get("/V")
    return out


def _readback_pages(pdf_bytes: bytes) -> int:
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


# ── F6/1 — Process-pdf route assertions ──────────────────────────────────────

class TestKg1ProcessRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.body = _process(client, kg1_pdf_bytes, "en")
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]

    def test_template_matched(self):
        assert self.report["template_id"] == "familienkasse_kg1_v1"

    def test_support_level_is_1(self):
        assert self.report["support_level"] == 1

    def test_fill_strategy_advertises_acroform(self):
        # The template's actual fill_strategy is "fitz_acroform"; the
        # public advertisement normalizes to "acroform" for the user.
        assert self.report["fill_strategy"] == "acroform"

    def test_shown_count_is_52(self):
        shown = [f for f in self.fields if f.get("show_question")]
        assert len(shown) == EXPECTED_SHOWN, (
            f"Expected {EXPECTED_SHOWN} shown KG1 questions, got {len(shown)}"
        )

    def test_manual_count_is_33(self):
        manual = [f for f in self.fields if not f.get("show_question")]
        assert len(manual) == EXPECTED_MANUAL, (
            f"Expected {EXPECTED_MANUAL} manual fields, got {len(manual)}"
        )

    def test_weak_questions_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("weak_questions") == 0, (
            f"weak_reasons_by_field: {qq.get('weak_reasons_by_field')}"
        )

    def test_ai_calls_made_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("ai_calls_made") == 0
        # And the skipped count must be the count of fields the engine
        # didn't translate — this should at least cover the 52 shown
        # logical fields (it can also include the 2 logical radio field IDs
        # which appear in extraction.fields).
        assert qq.get("ai_calls_skipped", 0) >= EXPECTED_SHOWN

    def test_extracted_field_ids_includes_logical_radio_fields(self):
        ids = set(self.body["extracted_field_ids"])
        assert LOGICAL_FAMILIENSTAND in ids
        assert LOGICAL_BANK_OWNER in ids

    def test_extracted_field_ids_excludes_raw_radio_widget_names(self):
        # Raw widget names (per-option /Btn fields) MUST NOT appear in the
        # user-visible field map. They live only inside the radio_group
        # expansion at fill time.
        ids = set(self.body["extracted_field_ids"])
        for w in (W_FS_LEDIG, W_FS_VERHEIRATET, W_FS_PARTNER,
                  W_FS_GESCHIEDEN, W_FS_AUFGEHOBEN, W_FS_GETRENNT,
                  W_FS_VERWITWET, W_BANK_OWNER_APP, W_BANK_OWNER_OTH):
            assert w not in ids, (
                f"Raw radio widget {w!r} leaked into extracted_field_ids"
            )

    def test_every_shown_question_source_is_verified(self):
        shown = [f for f in self.fields if f.get("show_question")]
        bad = [f["key"] for f in shown if f.get("question_source") != "verified"]
        assert bad == [], (
            f"Shown KG1 fields with non-verified source: {bad}"
        )


# ── F6/2 — Basic AcroForm fill round-trip ────────────────────────────────────

class TestKg1BasicFillRoundTrip:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        self.body = _process(client, kg1_pdf_bytes, "en")
        self.token = self.body["pdf_token"]
        self.input_pdf = kg1_pdf_bytes
        self.answers = {
            W_TELEFON:        "0151 12345678",
            W_APP_NAME:       "Müller",
            W_APP_VORNAME:    "Anna",
            W_APP_GEB_DATUM:  "15.03.1985",
            W_APP_GEB_ORT:    "Damascus",
            W_APP_STAATSANG:  "Syrian",
            W_APP_ANSCHRIFT:  "Hauptstraße 12, 18055 Rostock",
            W_BANK_IBAN:      "DE89370400440532013000",
            W_BANK_BIC:       "COBADEFFXXX",
            W_BANK_NAME:      "Commerzbank",
            W_BANK_OWNER_NAME:"Anna Müller",
            W_DATUM_1:        "08.05.2026",
        }

    def test_fill_returns_200_and_acroform_strategy(self):
        resp = _fill(self.client, self.token, self.answers)
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("X-Fill-Strategy") == "acroform"
        assert int(resp.headers.get("X-Fields-Filled", "0")) >= len(self.answers)

    def test_output_starts_with_pdf_magic(self):
        resp = _fill(self.client, self.token, self.answers)
        assert resp.content[:4] == b"%PDF"

    def test_output_page_count_matches_input(self):
        resp = _fill(self.client, self.token, self.answers)
        assert _readback_pages(resp.content) == _readback_pages(self.input_pdf)
        assert _readback_pages(resp.content) == EXPECTED_PAGES

    def test_text_values_round_trip_through_widgets(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        for widget, expected in self.answers.items():
            actual = rb.get(widget)
            # Some PDFs wrap the value differently; compare permissively.
            assert actual == expected or str(actual) == expected, (
                f"Widget {widget!r}: expected {expected!r}, got {actual!r}"
            )


# ── F6/3 — Radio group fill ──────────────────────────────────────────────────

class TestKg1FamilienstandRadio:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        self.token = _process(client, kg1_pdf_bytes, "en")["pdf_token"]

    def test_choosing_verheiratet_sets_only_verheiratet_yes(self):
        resp = _fill(self.client, self.token,
                     {LOGICAL_FAMILIENSTAND: "verheiratet"})
        assert resp.status_code == 200
        rb = _readback(resp.content)
        # /Yes on the chosen widget; /Off on every sibling.
        assert str(rb.get(W_FS_VERHEIRATET)).lstrip("/").lower() == "yes"
        for w in (W_FS_LEDIG, W_FS_PARTNER, W_FS_GESCHIEDEN,
                  W_FS_AUFGEHOBEN, W_FS_GETRENNT, W_FS_VERWITWET):
            v = str(rb.get(w)).lstrip("/").lower()
            assert v == "off", f"Sibling {w!r} should be /Off, got {rb.get(w)!r}"

    def test_choosing_ledig_sets_only_ledig_yes(self):
        resp = _fill(self.client, self.token,
                     {LOGICAL_FAMILIENSTAND: "ledig"})
        rb = _readback(resp.content)
        assert str(rb.get(W_FS_LEDIG)).lstrip("/").lower() == "yes"
        for w in (W_FS_VERHEIRATET, W_FS_PARTNER, W_FS_GESCHIEDEN,
                  W_FS_AUFGEHOBEN, W_FS_GETRENNT, W_FS_VERWITWET):
            assert str(rb.get(w)).lstrip("/").lower() == "off"

    def test_invalid_radio_value_writes_all_off(self, caplog):
        # Documented behavior (matches the F2 synthetic-template tests):
        # an answer that doesn't match any option results in all sibling
        # widgets set to Off, plus a WARNING log entry naming the bad
        # value. The fill still succeeds (200) — Phase E intentionally
        # does NOT 4xx on a bad client value, since the user can fix it
        # by clicking the correct option in the rendered PDF.
        import logging
        with caplog.at_level(logging.WARNING, logger="burokratie.fill_pdf"):
            resp = _fill(self.client, self.token,
                         {LOGICAL_FAMILIENSTAND: "totally_unknown_status"})
        assert resp.status_code == 200
        rb = _readback(resp.content)
        for w in (W_FS_LEDIG, W_FS_VERHEIRATET, W_FS_PARTNER,
                  W_FS_GESCHIEDEN, W_FS_AUFGEHOBEN, W_FS_GETRENNT,
                  W_FS_VERWITWET):
            assert str(rb.get(w)).lstrip("/").lower() == "off"
        assert any(
            "RADIO_GROUP_VALUE_NOT_IN_OPTIONS" in r.message
            and "totally_unknown_status" in r.message
            for r in caplog.records
        ), "Expected RADIO_GROUP_VALUE_NOT_IN_OPTIONS warning"


class TestKg1BankAccountHolderRadio:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        self.token = _process(client, kg1_pdf_bytes, "en")["pdf_token"]

    def test_choosing_applicant_sets_applicant_yes_other_off(self):
        resp = _fill(self.client, self.token,
                     {LOGICAL_BANK_OWNER: "Antragsteller"})
        rb = _readback(resp.content)
        assert str(rb.get(W_BANK_OWNER_APP)).lstrip("/").lower() == "yes"
        assert str(rb.get(W_BANK_OWNER_OTH)).lstrip("/").lower() == "off"

    def test_choosing_andere_person_sets_other_yes_applicant_off(self):
        resp = _fill(self.client, self.token,
                     {LOGICAL_BANK_OWNER: "andere Person"})
        rb = _readback(resp.content)
        assert str(rb.get(W_BANK_OWNER_OTH)).lstrip("/").lower() == "yes"
        assert str(rb.get(W_BANK_OWNER_APP)).lstrip("/").lower() == "off"


# ── F6/4 — Manual widgets stay blank ─────────────────────────────────────────

class TestKg1ManualWidgetsStayBlank:
    """
    The 8 Steuer-ID widgets and 25 Tabelle-2 Zählkinder widgets are
    confidence=0.5 / show_question=False per Phase F1 scope. The user
    cannot answer them through the UI. After a normal fill (without
    sending those keys), the output PDF must have them blank (no /V).
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        self.token = _process(client, kg1_pdf_bytes, "en")["pdf_token"]
        # A normal fill — answers cover only shown fields.
        self.resp = _fill(self.client, self.token, {
            W_APP_VORNAME: "Anna",
            W_APP_NAME:    "Müller",
        })
        assert self.resp.status_code == 200
        self.rb = _readback(self.resp.content)

    def test_applicant_steuer_id_widgets_are_blank(self):
        for w in (W_APP_STEUER_ID_1, W_APP_STEUER_ID_2,
                  W_APP_STEUER_ID_3, W_APP_STEUER_ID_4):
            assert self.rb.get(w) is None, (
                f"Applicant Steuer-ID widget {w} should be blank in output"
            )

    def test_partner_steuer_id_widgets_are_blank(self):
        for w in (W_PRT_STEUER_ID_1, W_PRT_STEUER_ID_2,
                  W_PRT_STEUER_ID_3, W_PRT_STEUER_ID_4):
            assert self.rb.get(w) is None

    def test_zaehlkinder_widgets_all_blank(self):
        # 5×5 = 25 Zählkinder widgets must remain unfilled.
        for row in (1, 2, 3, 4, 5):
            for cell in (1, 2, 3, 4, 5):
                w = _w_t2(row, cell)
                assert self.rb.get(w) is None, (
                    f"Zählkind {row}/{cell} widget should be blank"
                )


# ── F6/5 — Tabelle 1 fill ────────────────────────────────────────────────────

class TestKg1Tabelle1:
    """
    Filling row 1 of Tabelle 1 — the 4 cells must round-trip; rows 2–5
    must remain blank.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        self.token = _process(client, kg1_pdf_bytes, "en")["pdf_token"]
        self.resp = _fill(self.client, self.token, {
            _w_t1(1, 1): "Lena Müller",
            _w_t1(1, 2): "12.03.2016",
            _w_t1(1, 3): "w",
            _w_t1(1, 4): "Familienkasse Rostock — KG-Nr 12345BG0001234",
        })
        assert self.resp.status_code == 200
        self.rb = _readback(self.resp.content)

    def test_row_1_values_round_trip(self):
        assert self.rb.get(_w_t1(1, 1)) == "Lena Müller"
        assert self.rb.get(_w_t1(1, 2)) == "12.03.2016"
        assert self.rb.get(_w_t1(1, 3)) == "w"
        assert self.rb.get(_w_t1(1, 4)) == (
            "Familienkasse Rostock — KG-Nr 12345BG0001234"
        )

    def test_unfilled_rows_stay_blank(self):
        for row in (2, 3, 4, 5):
            for cell in (1, 2, 3, 4):
                w = _w_t1(row, cell)
                assert self.rb.get(w) is None, (
                    f"Tabelle1 row {row} cell {cell} should be blank"
                )


# ── F6/6 — Grounding tests ───────────────────────────────────────────────────

class TestKg1Grounding:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        body = _process(client, kg1_pdf_bytes, "en")
        self.token = body["pdf_token"]
        self.extracted_ids = set(body["extracted_field_ids"])

    def test_invented_answer_key_rejected_400(self):
        resp = _fill(self.client, self.token, {"NotARealField": "x"})
        assert resp.status_code == 400

    def test_raw_radio_widget_name_rejected_400(self):
        # Raw radio widget names are not in extracted_field_ids — the
        # grounding guard MUST reject them. This protects against a
        # client trying to bypass the radio_group expansion.
        assert W_FS_LEDIG not in self.extracted_ids
        resp = _fill(self.client, self.token, {W_FS_LEDIG: "Yes"})
        assert resp.status_code == 400

    def test_manual_widget_id_is_in_extracted_field_ids(self):
        # Documented behavior: manual (confidence=0.5) widgets DO appear
        # in extracted_field_ids today (the template's get_field_map
        # returns them). The UI does not surface them as questions, but
        # if a client manually crafted a request with one of these keys,
        # the grounding guard would accept it. We document this rather
        # than ship a hidden surface.
        assert W_APP_STEUER_ID_1 in self.extracted_ids

    def test_manual_widget_answer_is_accepted_by_grounding_guard(self):
        # Companion to the test above. Client-crafted answers for manual
        # widgets pass the grounding guard and reach the fill engine.
        # This is an acknowledged surface, not a security issue: the
        # widget is real, the value is the user's own input, and there's
        # no UI that produces these keys.
        resp = _fill(self.client, self.token,
                     {W_APP_STEUER_ID_1: "12345678901"})
        assert resp.status_code == 200
        # The value is written to the widget (the engine doesn't
        # double-check show_question at fill time).
        rb = _readback(resp.content)
        assert rb.get(W_APP_STEUER_ID_1) == "12345678901"


# ── F6/7 — Output safety (mock failures) ─────────────────────────────────────

class TestKg1OutputSafety:
    """
    Mirror Phase E's strict-policy enforcement for the fitz_acroform path.
    Any failure mode that could silently return a non-AcroForm PDF must
    surface as a friendly 500.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client, kg1_pdf_bytes):
        self.client = client
        self.token = _process(client, kg1_pdf_bytes, "en")["pdf_token"]

    def test_fitz_acroform_crash_returns_500(self, monkeypatch):
        from app.services.pdf_generator import fitz_acroform_fill

        def _boom(*a, **k):
            raise RuntimeError("simulated fitz_acroform failure")

        monkeypatch.setattr(
            fitz_acroform_fill, "fill_acroform_via_fitz", _boom,
        )
        resp = _fill(self.client, self.token, {W_APP_VORNAME: "Anna"})
        assert resp.status_code == 500
        # The 500 body must be the friendly user message — not a PDF.
        assert resp.headers.get("content-type", "").startswith("application/json")
        # Must NOT advertise summary or minimal fallback.
        assert resp.headers.get("X-Fill-Strategy") != "summary"

    def test_fitz_acroform_zero_fill_returns_500(self, monkeypatch):
        from app.services.pdf_generator import fitz_acroform_fill
        from app.services.pdf_generator.fitz_acroform_fill import FillResult

        def _zero_fill(pdf_bytes, answers):
            return FillResult(
                pdf_bytes=b"%PDF-1.4\n%fake\n",
                field_count_filled=0,
                warnings=["simulated: wrote nothing"],
            )

        monkeypatch.setattr(
            fitz_acroform_fill, "fill_acroform_via_fitz", _zero_fill,
        )
        resp = _fill(self.client, self.token, {W_APP_VORNAME: "Anna"})
        assert resp.status_code == 500


# ── Smoke tests across all 6 Tier-A locales ──────────────────────────────────

class TestKg1AcrossLocales:
    """
    weak_questions=0 and ai_calls_made=0 must hold for every supported
    locale, just like Phase C asserts for BuT.
    """

    @pytest.mark.parametrize("locale", ["en", "de", "fr", "ar", "tr", "sq"])
    def test_locale(self, client, kg1_pdf_bytes, locale):
        body = _process(client, kg1_pdf_bytes, locale)
        rep = body["analysis_report"]
        qq  = rep["question_quality"]
        assert rep["template_id"] == "familienkasse_kg1_v1"
        assert rep["support_level"] == 1
        assert rep["fill_strategy"] == "acroform"
        assert qq["weak_questions"] == 0, (
            f"{locale}: weak={qq['weak_questions']} reasons={qq.get('weak_reasons_by_field')}"
        )
        assert qq["ai_calls_made"] == 0


# ── F6/8 — Documented v1 limitations ─────────────────────────────────────────

# These are not test cases — they are an in-source acknowledgement that the
# following gaps are KNOWN and DEFERRED to KG1 v2. Listed here so a future
# reader (or grep) finds them next to the test suite that proves v1 is safe:
#
#   - Steuer-ID is manual in v1 (8 widgets across applicant + partner).
#     See Phase F1 scope decisions; user fills these by hand on the printout.
#   - Tabelle 2 Zählkinder (25 widgets) is manual in v1. Concept is
#     conceptually subtle and we deliberately did NOT author guidance for it.
#   - Partner section is unconditional. Single applicants will see 8 partner
#     questions; the convention is to leave them blank.
#   - Familienstand "seit" date is unconditional. A `ledig` user is still
#     asked "Since when?" — accepted as v1 trade-off.
#   - Anzahl-Anlagen is text with a format hint, no numeric validation.
#   - Conditional question flow (e.g. "Do you have a partner?" → skip Punkt 2)
#     is deferred to v2.
