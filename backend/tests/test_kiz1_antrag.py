"""
KiZ 1 Antrag auf Kinderzuschlag (kiz1_antrag_v1) — routing, gating, fill.

Runs against the REAL official PDF (templates_source/incoming/
kiz1_antrag.pdf); skips if absent. Mirrors the KG1 / Anlage Kind layout.
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fitz", reason="PyMuPDF required for fitz_acroform fill tests")

from app.services.form_templates.kiz1_antrag import (
    L_FAMILIENSTAND,
    W_NAME, W_GEBDATUM, W_ANSCHRIFT, W_IBAN, W_KONTOINHABER, W_DATUM,
    W_FS_SEIT, W_FS_LEDIG, W_FS_GETRENNT,
    W_PRT_NAME, W_PRT_GEBDATUM,
    _w_t4,
)

KIZ_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "incoming", "kiz1_antrag.pdf",
)
EXPECTED_SHOWN = 67


@pytest.fixture(scope="module")
def kiz_pdf_bytes() -> bytes:
    if not os.path.exists(KIZ_PDF_PATH):
        pytest.skip(f"KiZ1 PDF not present at {KIZ_PDF_PATH}")
    with open(KIZ_PDF_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _process(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("kiz1.pdf", pdf_bytes, "application/pdf")},
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

class TestKizProcessRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kiz_pdf_bytes):
        self.body = _process(client, kiz_pdf_bytes, "en")
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]

    def test_template_matched(self):
        assert self.report["template_id"] == "kiz1_antrag_v1"

    def test_support_level_is_1(self):
        assert self.report["support_level"] == 1

    def test_fill_strategy_acroform(self):
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

    def test_logical_familienstand_in_ids(self):
        assert L_FAMILIENSTAND in set(self.body["extracted_field_ids"])

    def test_raw_familienstand_widgets_not_extracted(self):
        ids = set(self.body["extracted_field_ids"])
        assert W_FS_LEDIG not in ids
        assert W_FS_GETRENNT not in ids


# ── 2. Conditional gating ────────────────────────────────────────────────────

class TestKizGating:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kiz_pdf_bytes):
        body = _process(client, kiz_pdf_bytes, "en")
        self.by_id = {f["key"]: f for f in body["fields"]}

    def test_seit_gated_on_getrennt(self):
        cond = self.by_id[W_FS_SEIT].get("condition")
        assert cond == {"type": "field_equals", "field_key": L_FAMILIENSTAND,
                        "value": "getrennt lebend"}

    def test_partner_details_gated_on_partner_name(self):
        cond = self.by_id[W_PRT_GEBDATUM].get("condition")
        assert cond == {"type": "field_not_equals", "field_key": W_PRT_NAME,
                        "value": "-"}

    def test_child2_gated_on_child1_name(self):
        cond = self.by_id[_w_t4(2, 1)].get("condition")
        assert cond == {"type": "field_not_equals",
                        "field_key": _w_t4(1, 1), "value": "-"}

    def test_child1_name_unconditioned(self):
        assert self.by_id[_w_t4(1, 1)].get("condition") in (None, {})

    def test_core_fields_unconditioned(self):
        for fid in (W_NAME, W_GEBDATUM, W_ANSCHRIFT, W_IBAN, L_FAMILIENSTAND, W_DATUM):
            assert self.by_id[fid].get("condition") in (None, {}), fid


# ── 3. Fill round-trip ───────────────────────────────────────────────────────

class TestKizFill:
    @pytest.fixture(autouse=True)
    def _setup(self, client, kiz_pdf_bytes):
        self.client = client
        body = _process(client, kiz_pdf_bytes, "en")
        self.token = body["pdf_token"]
        self.answers = {
            W_NAME: "Diallo, Aminata",
            W_GEBDATUM: "15.03.1990",
            W_ANSCHRIFT: "Hauptstraße 12, 18055 Rostock",
            L_FAMILIENSTAND: "getrennt lebend",
            W_FS_SEIT: "01.2025",
            W_IBAN: "DE89370400440532013000",
            W_KONTOINHABER: "Aminata Diallo",
            _w_t4(1, 1): "Diallo, Ibrahim",
            _w_t4(1, 2): "15.03.2019",
            W_DATUM: "13.06.2026",
        }

    def test_fill_200_acroform_original_pdf(self):
        resp = _fill(self.client, self.token, self.answers)
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("X-Fill-Strategy") == "acroform"
        assert resp.content[:4] == b"%PDF"

    def test_text_values_written(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert rb.get(W_NAME) == "Diallo, Aminata"
        assert rb.get(W_IBAN) == "DE89370400440532013000"
        assert rb.get(_w_t4(1, 1)) == "Diallo, Ibrahim"

    def test_escaped_datum_widget_written(self):
        # The signature date widget name contains literal "\." XFA escapes;
        # confirm the fill engine matches it correctly.
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert rb.get(W_DATUM) == "13.06.2026"

    def test_familienstand_radio_checks_getrennt(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get(W_FS_GETRENNT)) == "yes"
        assert _norm(rb.get(W_FS_LEDIG)) in ("off", "none")

    def test_grounding_rejects_unknown_key(self):
        bad = dict(self.answers)
        bad["nope"] = "x"
        resp = _fill(self.client, self.token, bad)
        assert resp.status_code == 400
