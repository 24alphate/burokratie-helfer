"""
Jobcenter Hauptantrag Bürgergeld (buergergeld_hauptantrag_v1) — routing,
gating, and the pypdf_native fill backend (custom "selektiert" exports +
native 0/1 radios).

Runs against the REAL official PDF (templates_source/incoming/
buergergeld_hauptantrag.pdf); skips if absent.
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.form_templates.buergergeld_hauptantrag import (
    L_GESCHLECHT, L_FAMSTAND, L_RVNR_STATUS, L_BUEG_AB,
)

BG_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "incoming", "buergergeld_hauptantrag.pdf",
)
EXPECTED_SHOWN = 104


@pytest.fixture(scope="module")
def bg_pdf_bytes() -> bytes:
    if not os.path.exists(BG_PDF_PATH):
        pytest.skip(f"Bürgergeld Hauptantrag PDF not present at {BG_PDF_PATH}")
    with open(BG_PDF_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _process(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("bg.pdf", pdf_bytes, "application/pdf")},
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


# ── 1. Process-pdf route ─────────────────────────────────────────────────────

class TestBgProcessRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, bg_pdf_bytes):
        self.body = _process(client, bg_pdf_bytes, "en")
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]
        self.by_id = {f["key"]: f for f in self.fields}

    def test_template_matched(self):
        assert self.report["template_id"] == "buergergeld_hauptantrag_v1"

    def test_support_level_is_1(self):
        assert self.report["support_level"] == 1

    def test_fill_strategy_acroform(self):
        # pypdf_native normalizes to "acroform" on the public surface.
        assert self.report["fill_strategy"] == "acroform"

    def test_shown_count(self):
        shown = [f for f in self.fields if f.get("show_question")]
        assert len(shown) == EXPECTED_SHOWN, len(shown)

    def test_weak_questions_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("weak_questions") == 0, qq.get("weak_reasons_by_field")

    def test_ai_calls_zero(self):
        qq = self.report.get("question_quality") or {}
        assert qq.get("ai_calls_made") == 0

    def test_all_sources_verified(self):
        shown = [f for f in self.fields if f.get("show_question")]
        bad = [f["key"] for f in shown if f.get("question_source") != "verified"]
        assert bad == [], bad

    def test_native_radio_has_ja_nein_labels(self):
        rad = self.by_id["rbtnSchwanger"]
        assert rad["input_type"] == "radio"
        opts = {o["value"]: o["label"] for o in rad["options"]}
        assert opts == {"0": "Ja", "1": "Nein"}

    def test_logical_ids_present(self):
        ids = set(self.body["extracted_field_ids"])
        for fid in (L_GESCHLECHT, L_FAMSTAND, L_RVNR_STATUS, L_BUEG_AB):
            assert fid in ids, fid

    def test_raw_gender_widgets_not_extracted(self):
        ids = set(self.body["extracted_field_ids"])
        for w in ("chbxMaennlich", "chbxFamStandLedig"):
            assert w not in ids, w


# ── 2. Conditional gating ────────────────────────────────────────────────────

class TestBgGating:
    @pytest.fixture(autouse=True)
    def _setup(self, client, bg_pdf_bytes):
        body = _process(client, bg_pdf_bytes, "en")
        self.by_id = {f["key"]: f for f in body["fields"]}

    def test_entbindung_gated_on_schwanger_ja(self):
        cond = self.by_id["dateEntbindung"].get("condition")
        assert cond == {"type": "field_equals", "field_key": "rbtnSchwanger", "value": "0"}

    def test_leistung_checkboxes_gated_on_andere_ja(self):
        cond = self.by_id["chbxLeistungWohngeld"].get("condition")
        assert cond == {"type": "field_equals", "field_key": "rbtnLeistungAndere", "value": "0"}

    def test_wohnen_gated_on_wohnsituation_nein(self):
        cond = self.by_id["chbxWohnenEhegatte"].get("condition")
        assert cond == {"type": "field_equals", "field_key": "rbtnWohnsituation", "value": "1"}

    def test_getrennt_gated_on_familienstand(self):
        cond = self.by_id["dateGetrennt"].get("condition")
        assert cond == {"type": "field_in", "field_key": L_FAMSTAND,
                        "values": ["getrennt", "geschieden", "aufgehoben"]}

    def test_core_fields_unconditioned(self):
        for fid in ("txtfPersonVorname", L_GESCHLECHT, L_FAMSTAND,
                    "rbtnSchwanger", "dateUnterschriftPerson"):
            assert self.by_id[fid].get("condition") in (None, {}), fid


# ── 3. Fill round-trip (pypdf_native: selektiert + native radios) ────────────

class TestBgFill:
    @pytest.fixture(autouse=True)
    def _setup(self, client, bg_pdf_bytes):
        self.client = client
        body = _process(client, bg_pdf_bytes, "en")
        self.token = body["pdf_token"]
        self.answers = {
            "txtfPersonVorname": "Aminata",
            "txtfPersonNachname": "Diallo",
            "datePersonGebDatum": "15.03.1990",
            L_GESCHLECHT: "weiblich",
            L_FAMSTAND: "ledig",
            "rtbnErwerbsfaehig": "0",   # Ja
            "rbtnSchwanger": "1",       # Nein
            "rbtnWohnsituation": "0",   # Ja (live alone)
            L_BUEG_AB: "ab sofort",
            "dateUnterschriftPerson": "13.06.2026",
        }

    def test_fill_200_acroform_original_pdf(self):
        resp = _fill(self.client, self.token, self.answers)
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("X-Fill-Strategy") == "acroform"
        assert resp.content[:4] == b"%PDF"

    def test_text_written(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert rb.get("txtfPersonVorname") == "Aminata"
        assert rb.get("dateUnterschriftPerson") == "13.06.2026"

    def test_checkbox_custom_selektiert_export(self):
        # The logical gender/marital radios write the REAL "selektiert" export,
        # not a hardcoded "Yes" — the whole reason this form needs pypdf_native.
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get("chbxWeiblich")) == "selektiert"
        assert _norm(rb.get("chbxMaennlich")) in ("off", "none")
        assert _norm(rb.get("chbxFamStandLedig")) == "selektiert"
        assert _norm(rb.get("chbxFamStandVerheiratet")) in ("off", "none")

    def test_native_radio_export_value(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get("rtbnErwerbsfaehig")) == "0"   # Ja
        assert _norm(rb.get("rbtnSchwanger")) == "1"        # Nein

    def test_grounding_rejects_unknown_key(self):
        bad = dict(self.answers)
        bad["nope"] = "x"
        resp = _fill(self.client, self.token, bad)
        assert resp.status_code == 400
