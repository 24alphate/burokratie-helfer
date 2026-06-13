"""
KiZ 1 Anlage Antragsteller/Partner (kiz1_anlage_antragsteller_v1) —
routing, partner gating, fill.

Runs against the REAL official PDF (templates_source/incoming/
kiz1_anlage_antragsteller.pdf); skips if absent.
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fitz", reason="PyMuPDF required for fitz_acroform fill tests")

from app.services.form_templates.kiz1_anlage_antragsteller import (
    L_HAS_PARTNER, L_VERMOEGEN, L_WARMWASSER,
    W_NAME_KGB, W_DATUM,
    W_LOHN_A, W_LOHN_P, W_AUSB_A, W_AUSB_P,
    W_MIETE, W_MIETVERTRAG, W_EIGENHEIM, W_SCHULDZINSEN,
    W_MEHRBEDARF, W_ENTBINDUNG,
    W_VERMOEGEN_JA, W_VERMOEGEN_NEIN,
    W_FK_KM_A, W_FK_TAGE_A,
)

ANA_PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "templates_source", "incoming", "kiz1_anlage_antragsteller.pdf",
)
EXPECTED_SHOWN = 81


@pytest.fixture(scope="module")
def ana_pdf_bytes() -> bytes:
    if not os.path.exists(ANA_PDF_PATH):
        pytest.skip(f"KiZ Anlage Antragsteller PDF not present at {ANA_PDF_PATH}")
    with open(ANA_PDF_PATH, "rb") as f:
        return f.read()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _process(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("kizana.pdf", pdf_bytes, "application/pdf")},
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

class TestAnaProcessRoute:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ana_pdf_bytes):
        self.body = _process(client, ana_pdf_bytes, "en")
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]

    def test_template_matched(self):
        assert self.report["template_id"] == "kiz1_anlage_antragsteller_v1"

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

    def test_logical_ids_present(self):
        ids = set(self.body["extracted_field_ids"])
        assert L_HAS_PARTNER in ids and L_VERMOEGEN in ids and L_WARMWASSER in ids

    def test_raw_vermoegen_widgets_not_extracted(self):
        ids = set(self.body["extracted_field_ids"])
        assert W_VERMOEGEN_JA not in ids and W_VERMOEGEN_NEIN not in ids


# ── 2. Partner + section gating ──────────────────────────────────────────────

class TestAnaGating:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ana_pdf_bytes):
        body = _process(client, ana_pdf_bytes, "en")
        self.by_id = {f["key"]: f for f in body["fields"]}

    def test_partner_fields_gated_on_has_partner(self):
        for fid in (W_AUSB_P, W_LOHN_P):
            cond = self.by_id[fid].get("condition")
            assert cond == {"type": "field_equals", "field_key": L_HAS_PARTNER,
                            "value": "yes"}, fid

    def test_applicant_fields_unconditioned(self):
        for fid in (W_AUSB_A, W_LOHN_A, W_NAME_KGB, L_VERMOEGEN, W_DATUM):
            assert self.by_id[fid].get("condition") in (None, {}), fid

    def test_rent_subitems_gated_on_miete(self):
        cond = self.by_id[W_MIETVERTRAG].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_MIETE, "value": "yes"}

    def test_own_subitems_gated_on_eigenheim(self):
        cond = self.by_id[W_SCHULDZINSEN].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_EIGENHEIM, "value": "yes"}

    def test_entbindung_gated_on_mehrbedarf(self):
        cond = self.by_id[W_ENTBINDUNG].get("condition")
        assert cond == {"type": "field_equals", "field_key": W_MEHRBEDARF, "value": "yes"}

    def test_fk_tage_gated_on_km(self):
        cond = self.by_id[W_FK_TAGE_A].get("condition")
        assert cond == {"type": "field_not_equals", "field_key": W_FK_KM_A, "value": "-"}


# ── 3. Fill round-trip ───────────────────────────────────────────────────────

class TestAnaFill:
    @pytest.fixture(autouse=True)
    def _setup(self, client, ana_pdf_bytes):
        self.client = client
        body = _process(client, ana_pdf_bytes, "en")
        self.token = body["pdf_token"]
        # Single-parent persona: no partner, rents, has wage income, no assets.
        self.answers = {
            W_NAME_KGB: "Diallo, Aminata",
            L_HAS_PARTNER: "no",
            W_MIETE: "yes",
            W_LOHN_A: "yes",
            L_VERMOEGEN: "nein",
            L_WARMWASSER: "zentral",
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
        assert rb.get(W_NAME_KGB) == "Diallo, Aminata"
        assert rb.get(W_DATUM) == "13.06.2026"

    def test_checkbox_and_radio_written(self):
        resp = _fill(self.client, self.token, self.answers)
        rb = _readback(resp.content)
        assert _norm(rb.get(W_MIETE)) == "yes"
        assert _norm(rb.get(W_LOHN_A)) == "yes"
        # Vermögen = nein → the "nein" widget checked, "ja" off
        assert _norm(rb.get(W_VERMOEGEN_NEIN)) == "yes"
        assert _norm(rb.get(W_VERMOEGEN_JA)) in ("off", "none")

    def test_synthetic_has_partner_not_a_widget(self):
        # L_HAS_PARTNER has no PDF widget — fill must still succeed (it is
        # ignored) and write the real fields.
        resp = _fill(self.client, self.token, self.answers)
        assert resp.status_code == 200
        rb = _readback(resp.content)
        assert L_HAS_PARTNER not in rb  # never a real widget

    def test_grounding_rejects_unknown_key(self):
        bad = dict(self.answers)
        bad["nope"] = "x"
        resp = _fill(self.client, self.token, bad)
        assert resp.status_code == 400
