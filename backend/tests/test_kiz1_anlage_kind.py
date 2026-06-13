"""
KiZ 1 Anlage Kind (kiz1_anlage_kind_v1) — routing, gating, fill.

Runs against the REAL official PDF (templates_source/incoming/
kiz1_anlage_kind.pdf); skips if absent.
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fitz", reason="PyMuPDF required for fitz_acroform fill tests")

from app.services.form_templates.kiz1_anlage_kind import (
    L_REL_ME, L_REL_PARTNER,
    W_CHILD_NAME, W_CHILD_GEBDATUM, W_DATUM,
    W_MEHRBEDARF, W_ENTBINDUNG, W_LOHN, W_VERDIENSTBESCH, W_FERIENJOB,
    W_FK_KM, W_FK_TAGE, W_ALG2,
    W_REL_EIGEN_ME, W_REL_STIEF_ME, W_REL_EIGEN_PRT,
)

ANK_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "incoming", "kiz1_anlage_kind.pdf",
)
EXPECTED_SHOWN = 43


@pytest.fixture(scope="module")
def ank_pdf_bytes() -> bytes:
    if not os.path.exists(ANK_PDF_PATH):
        pytest.skip(f"KiZ Anlage Kind PDF not present at {ANK_PDF_PATH}")
    with open(ANK_PDF_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _process(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("kizank.pdf", pdf_bytes, "application/pdf")},
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

class TestKizAnkProcessRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ank_pdf_bytes):
        self.body = _process(client, ank_pdf_bytes, "en")
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]

    def test_template_matched(self):
        assert self.report["template_id"] == "kiz1_anlage_kind_v1"

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

    def test_logical_relationship_ids_present(self):
        ids = set(self.body["extracted_field_ids"])
        assert L_REL_ME in ids and L_REL_PARTNER in ids

    def test_raw_relationship_widgets_not_extracted(self):
        ids = set(self.body["extracted_field_ids"])
        for w in (W_REL_EIGEN_ME, W_REL_STIEF_ME, W_REL_EIGEN_PRT):
            assert w not in ids, w


# ── 2. Conditional gating ────────────────────────────────────────────────────

class TestKizAnkGating:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ank_pdf_bytes):
        body = _process(client, ank_pdf_bytes, "en")
        self.by_id = {f["key"]: f for f in body["fields"]}

    def test_entbindung_gated_on_mehrbedarf(self):
        cond = self.by_id[W_ENTBINDUNG].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_MEHRBEDARF,
                        "value": "yes"}

    def test_ferienjob_gated_on_lohn(self):
        cond = self.by_id[W_FERIENJOB].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_LOHN,
                        "value": "yes"}

    def test_verdienstbesch_gated_on_lohn(self):
        cond = self.by_id[W_VERDIENSTBESCH].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_LOHN,
                        "value": "yes"}

    def test_fk_tage_gated_on_km(self):
        cond = self.by_id[W_FK_TAGE].get("condition")
        assert cond == {"type": "field_not_equals", "field_key": W_FK_KM,
                        "value": "-"}

    def test_core_fields_unconditioned(self):
        for fid in (W_CHILD_NAME, W_CHILD_GEBDATUM, L_REL_ME, W_DATUM):
            assert self.by_id[fid].get("condition") in (None, {}), fid


# ── 3. Fill round-trip ───────────────────────────────────────────────────────

class TestKizAnkFill:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ank_pdf_bytes):
        self.client = client
        body = _process(client, ank_pdf_bytes, "en")
        self.token = body["pdf_token"]
        self.answers = {
            W_CHILD_NAME: "Diallo, Ibrahim",
            W_CHILD_GEBDATUM: "15.03.2019",
            L_REL_ME: "eigenes (leibliches) Kind",
            L_REL_PARTNER: "keine Angabe",
            W_ALG2: "yes",
            W_DATUM: "13.06.2026",
        }

    def test_fill_200_acroform_original_pdf(self):
        resp = _fill(self.client, self.token, self.answers)
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("X-Fill-Strategy") == "acroform"
        assert resp.content[:4] == b"%PDF"

    def test_text_and_escaped_datum_written(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert rb.get(W_CHILD_NAME) == "Diallo, Ibrahim"
        # Datum widget name contains literal "\." XFA escapes
        assert rb.get(W_DATUM) == "13.06.2026"

    def test_relationship_radio_checks_eigenes_only(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get(W_REL_EIGEN_ME)) == "yes"
        assert _norm(rb.get(W_REL_STIEF_ME)) in ("off", "none")
        # partner = keine Angabe → no widget checked
        assert _norm(rb.get(W_REL_EIGEN_PRT)) in ("off", "none")

    def test_income_checkbox_checked(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get(W_ALG2)) == "yes"

    def test_grounding_rejects_unknown_key(self):
        bad = dict(self.answers)
        bad["nope"] = "x"
        resp = _fill(self.client, self.token, bad)
        assert resp.status_code == 400
