"""
KG 1 Anlage Kind (kg1_anlage_kind_v1) — routing, gating, and fill round-trip.

Runs against the REAL official PDF (templates_source/incoming/
kg1_anlage_kind.pdf); every test skips if it is absent. Mirrors the KG1
test layout (test_familienkasse_kg1.py):

  1. Process-pdf route assertions (Level 1, weak=0, ai_calls=0)
  2. Conditional gating (minor-child persona sees no adult-child questions)
  3. Fill round-trip: text + Steuer-ID split + kinship radio + ja/nein radio
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fitz", reason="PyMuPDF required for fitz_acroform fill tests")

from app.services.form_templates.kg1_anlage_kind import (
    L_STEUER_ID, L_REL_APP, L_REL_PARTNER, L_REL_OTHER,
    L_ABGESCHLOSSEN, L_ERWERB, L_BEHINDERUNG, L_PRIOR_KG,
    L_OEFF_DIENST, L_DIENST_BUND, L_DIENST_BA, L_AUSL_LEISTUNG,
    L_7A, L_7B, L_7C,
    W_CHILD_VORNAME, W_CHILD_NAME, W_DATUM,
    W_STEUER_1, W_STEUER_2, W_STEUER_3, W_STEUER_4,
    W_AP_NAME, W_F4_NAME, W_ABSCHLUSS, W_CHK_SCHUL, W_SCHUL_BEZ_1,
    W_F4_JA, W_F4_NEIN,
    _kv,
)

ANK_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "incoming", "kg1_anlage_kind.pdf",
)
EXPECTED_SHOWN = 89
EXPECTED_MANUAL = 9


@pytest.fixture(scope="module")
def ank_pdf_bytes() -> bytes:
    if not os.path.exists(ANK_PDF_PATH):
        pytest.skip(f"Anlage Kind PDF not present at {ANK_PDF_PATH}")
    with open(ANK_PDF_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _process(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("anlage_kind.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill(client, token: str, answers: dict):
    return client.post(
        "/api/v1/fill-pdf",
        json={"pdf_token": token, "answers": answers, "field_labels": {}},
    )


def _readback(pdf_bytes: bytes) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return {k: v.get("/V") for k, v in (reader.get_fields() or {}).items()}


def _norm(v) -> str:
    return str(v).lstrip("/").lower()


# ── 1. Process-pdf route assertions ──────────────────────────────────────────

class TestAnkProcessRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ank_pdf_bytes):
        self.body = _process(client, ank_pdf_bytes, "en")
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]

    def test_template_matched(self):
        assert self.report["template_id"] == "kg1_anlage_kind_v1"

    def test_support_level_is_1(self):
        assert self.report["support_level"] == 1

    def test_fill_strategy_advertises_acroform(self):
        assert self.report["fill_strategy"] == "acroform"

    def test_shown_count(self):
        shown = [f for f in self.fields if f.get("show_question")]
        assert len(shown) == EXPECTED_SHOWN, len(shown)

    def test_manual_count(self):
        manual = [f for f in self.fields if not f.get("show_question")]
        assert len(manual) == EXPECTED_MANUAL, len(manual)

    def test_weak_questions_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("weak_questions") == 0, qq.get("weak_reasons_by_field")

    def test_ai_calls_made_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("ai_calls_made") == 0

    def test_every_shown_question_source_is_verified(self):
        shown = [f for f in self.fields if f.get("show_question")]
        bad = [f["key"] for f in shown if f.get("question_source") != "verified"]
        assert bad == [], bad

    def test_logical_ids_in_extracted_field_ids(self):
        ids = set(self.body["extracted_field_ids"])
        for fid in (L_STEUER_ID, L_REL_APP, L_REL_PARTNER, L_REL_OTHER,
                    L_PRIOR_KG, L_7A):
            assert fid in ids, fid

    def test_raw_steuer_comb_widgets_not_extracted(self):
        ids = set(self.body["extracted_field_ids"])
        for w in (W_STEUER_1, W_STEUER_2, W_STEUER_3, W_STEUER_4):
            assert w not in ids, w


# ── 2. Conditional gating ────────────────────────────────────────────────────

class TestAnkConditionalGating:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ank_pdf_bytes):
        body = _process(client, ank_pdf_bytes, "en")
        self.by_id = {f["key"]: f for f in body["fields"]}

    def test_other_person_block_gated_on_rel_other(self):
        cond = self.by_id[W_AP_NAME].get("condition")
        assert cond and cond["type"] == "field_in"
        assert cond["field_key"] == L_REL_OTHER
        assert "keine Angabe" not in cond["values"]

    def test_f4_details_gated_on_ja(self):
        cond = self.by_id[W_F4_NAME].get("condition")
        assert cond == {"type": "field_equals", "field_key": L_PRIOR_KG,
                        "value": "ja"}

    def test_adult_section_gated_on_activity_or(self):
        cond = self.by_id[L_ABGESCHLOSSEN].get("condition")
        assert cond and cond["type"] == "or"
        cond_b = self.by_id[L_BEHINDERUNG].get("condition")
        assert cond_b and cond_b["type"] == "or"

    def test_schul_details_gated_on_checkbox(self):
        cond = self.by_id[W_SCHUL_BEZ_1].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_CHK_SCHUL,
                        "value": "yes"}

    def test_core_child_fields_unconditioned(self):
        for fid in (W_CHILD_VORNAME, W_CHILD_NAME, L_STEUER_ID, L_REL_APP,
                    L_PRIOR_KG, W_DATUM):
            assert self.by_id[fid].get("condition") in (None, {}), fid


# ── 3. Fill round-trip ───────────────────────────────────────────────────────

class TestAnkFillRoundTrip:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ank_pdf_bytes):
        self.client = client
        body = _process(client, ank_pdf_bytes, "en")
        self.token = body["pdf_token"]
        # Minor-child persona: core data + kinship + all ja/nein answered nein.
        self.answers = {
            W_CHILD_NAME:    "Diallo",
            W_CHILD_VORNAME: "Ibrahim",
            L_STEUER_ID:     "12 345 678 901",
            L_REL_APP:       "leibliches Kind",
            L_REL_PARTNER:   "keine Angabe",
            L_REL_OTHER:     "keine Angabe",
            L_PRIOR_KG:      "nein",
            L_OEFF_DIENST:   "nein",
            L_AUSL_LEISTUNG: "nein",
            L_7A: "nein", L_7B: "nein", L_7C: "nein",
            W_DATUM: "12.06.2026",
        }

    def test_fill_200_acroform_original_pdf(self):
        resp = _fill(self.client, self.token, self.answers)
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("X-Fill-Strategy") == "acroform"
        assert resp.content[:4] == b"%PDF"

    def test_text_and_steuer_id_split(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert rb.get(W_CHILD_VORNAME) == "Ibrahim"
        assert rb.get(W_CHILD_NAME) == "Diallo"
        # 11-digit Steuer-ID sliced 2/3/3/3 across the comb widgets
        assert rb.get(W_STEUER_1) == "12"
        assert rb.get(W_STEUER_2) == "345"
        assert rb.get(W_STEUER_3) == "678"
        assert rb.get(W_STEUER_4) == "901"

    def test_kinship_radio_checks_only_chosen_cell(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        # Row 1 (applicant): leibliches Kind → Zelle2 checked. PyMuPDF
        # normalizes checked state to /Yes (it synthesizes the appearance),
        # same behavior as the proven KG1 template.
        assert _norm(rb.get(_kv(1, 2))) == "yes"
        for z in (3, 4, 5, 6):
            assert _norm(rb.get(_kv(1, z))) in ("off", "none")
        # Rows 2 + 4 fully off ("keine Angabe")
        for zeile in (2, 4):
            for z in (2, 3, 4, 5, 6):
                assert _norm(rb.get(_kv(zeile, z))) in ("off", "none")

    def test_ja_nein_radio_nein(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get(W_F4_NEIN)) == "yes"
        assert _norm(rb.get(W_F4_JA)) in ("off", "none")

    def test_grounding_rejects_unknown_key(self):
        bad = dict(self.answers)
        bad["invented_field"] = "x"
        resp = _fill(self.client, self.token, bad)
        assert resp.status_code == 400

    def test_steuer_id_wrong_length_not_written(self):
        answers = dict(self.answers)
        answers[L_STEUER_ID] = "12345"   # wrong length → group skipped
        resp = _fill(self.client, self.token, answers)
        assert resp.status_code == 200
        rb = _readback(resp.content)
        assert rb.get(W_STEUER_1) in (None, "")
