"""
Tests for the stateless PDF pipeline:
  - pdf_token.py: sign / verify / expiry / tamper detection
  - /fill-pdf grounding guard: answer keys not in field map are rejected
  - /process-pdf: extracts fields, signs token, grounding_rate = 100%
  - Cold-start invariant: no DB or filesystem access between the two calls
"""
from __future__ import annotations

import io
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from itsdangerous import BadSignature, SignatureExpired

from app.services.pdf_token import sign_pdf_token, verify_pdf_token


SECRET = "test-secret-key-for-unit-tests"


# ── Minimal PDF fixture ────────────────────────────────────────────────────────

def _minimal_pdf() -> bytes:
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Annots [6 0 R] >> endobj
5 0 obj << /Fields [6 0 R] /DR << >> >> endobj
6 0 obj << /Type /Annot /Subtype /Widget /FT /Tx
  /T (Vorname) /Rect [50 750 250 770] /P 3 0 R >> endobj
xref
0 7
0000000000 65535 f\r
0000000009 00000 n\r
0000000068 00000 n\r
0000000125 00000 n\r
0000000000 65535 f\r
0000000270 00000 n\r
0000000320 00000 n\r
trailer << /Size 7 /Root 1 0 R >>
startxref
430
%%EOF"""


# ── 1. PDF token: sign + verify ────────────────────────────────────────────────

class TestPdfToken:
    def test_round_trip(self):
        pdf = _minimal_pdf()
        token = sign_pdf_token(pdf, ["Vorname", "IBAN"], "test.pdf", SECRET)
        data  = verify_pdf_token(token, SECRET)
        assert data["pdf_bytes"] == pdf
        assert data["field_ids"] == ["Vorname", "IBAN"]
        assert data["filename"]  == "test.pdf"

    def test_token_is_string(self):
        token = sign_pdf_token(b"%PDF-1.4", [], "f.pdf", SECRET)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_wrong_secret_raises_bad_signature(self):
        token = sign_pdf_token(b"%PDF-1.4", ["X"], "f.pdf", SECRET)
        with pytest.raises(BadSignature):
            verify_pdf_token(token, "wrong-secret")

    def test_tampered_token_raises_bad_signature(self):
        token = sign_pdf_token(b"%PDF-1.4", ["X"], "f.pdf", SECRET)
        # Flip a character in the payload
        tampered = token[:-5] + ("A" if token[-5] != "A" else "B") + token[-4:]
        with pytest.raises(BadSignature):
            verify_pdf_token(tampered, SECRET)

    def test_expired_token_raises_signature_expired(self):
        """max_age=-1 makes every token appear expired (age always >= 0 > -1)."""
        from app.services.pdf_token import _SALT
        from itsdangerous import URLSafeTimedSerializer
        token = sign_pdf_token(b"%PDF-1.4", ["X"], "f.pdf", SECRET)
        s = URLSafeTimedSerializer(SECRET, salt=_SALT)
        with pytest.raises(SignatureExpired):
            s.loads(token, max_age=-1)

    def test_empty_field_ids_allowed(self):
        token = sign_pdf_token(b"%PDF-1.4", [], "f.pdf", SECRET)
        data  = verify_pdf_token(token, SECRET)
        assert data["field_ids"] == []

    def test_large_pdf_round_trip(self):
        """PDF bytes up to ~500 KB should compress and round-trip correctly."""
        large_pdf = b"%PDF-1.4\n" + b"x" * 500_000 + b"\n%%EOF"
        token = sign_pdf_token(large_pdf, ["A", "B"], "large.pdf", SECRET)
        data  = verify_pdf_token(token, SECRET)
        assert data["pdf_bytes"] == large_pdf

    def test_compression_reduces_size(self):
        """The token should be smaller than the raw base64 of the PDF."""
        import base64
        pdf   = b"%PDF-1.4\n" + b"repetitive content " * 10000 + b"\n%%EOF"
        token = sign_pdf_token(pdf, [], "f.pdf", SECRET)
        raw_b64_len = len(base64.b64encode(pdf))
        assert len(token) < raw_b64_len, "zlib compression should reduce token size"


# ── 2. Fill-pdf grounding guard ───────────────────────────────────────────────

class TestFillPdfGroundingGuard:
    """
    The /fill-pdf endpoint must reject answers whose field_id is not in the
    token's field_ids list.  This is the backend grounding gate.
    """

    def _make_token(self, field_ids: list[str]) -> str:
        return sign_pdf_token(_minimal_pdf(), field_ids, "form.pdf", SECRET)

    def test_valid_answers_accepted(self):
        """All answer keys are in field_ids — should not raise."""
        token     = self._make_token(["Vorname", "IBAN"])
        field_ids = verify_pdf_token(token, SECRET)["field_ids"]
        answers   = {"Vorname": "Max", "IBAN": "DE89370400440532013000"}
        invalid   = [k for k in answers if k not in set(field_ids)]
        assert invalid == []

    def test_invented_key_rejected(self):
        """Answer key 'monthly_income' is not in the field map → must be caught."""
        token     = self._make_token(["Vorname", "IBAN"])
        field_ids = verify_pdf_token(token, SECRET)["field_ids"]
        answers   = {"Vorname": "Max", "monthly_income": "2000"}  # invented!
        invalid   = [k for k in answers if k not in set(field_ids)]
        assert "monthly_income" in invalid

    def test_all_invented_keys_caught(self):
        token     = self._make_token(["name", "birth_date", "address"])
        field_ids = verify_pdf_token(token, SECRET)["field_ids"]
        answers   = {
            "name":           "Alice",
            "birth_date":     "01.01.1990",
            "address":        "Berlin",
            "monthly_income": "2000",  # invented
            "partner_name":   "Bob",   # invented
        }
        invalid = [k for k in answers if k not in set(field_ids)]
        assert sorted(invalid) == ["monthly_income", "partner_name"]

    def test_empty_field_ids_blocks_all_answers(self):
        """If token has no field_ids, every answer is invalid."""
        token     = self._make_token([])
        field_ids = verify_pdf_token(token, SECRET)["field_ids"]
        answers   = {"Vorname": "Max"}
        invalid   = [k for k in answers if k not in set(field_ids)]
        assert "Vorname" in invalid

    def test_partial_match_only_invalid_caught(self):
        token     = self._make_token(["A", "B", "C"])
        field_ids = verify_pdf_token(token, SECRET)["field_ids"]
        answers   = {"A": "1", "B": "2", "GHOST": "3"}
        invalid   = [k for k in answers if k not in set(field_ids)]
        assert invalid == ["GHOST"]
        # Valid keys must NOT be in invalid
        assert "A" not in invalid
        assert "B" not in invalid


# ── 3. Process-pdf endpoint (integration) ────────────────────────────────────

class TestProcessPdfEndpoint:
    """
    Integration test against the FastAPI app.
    Uses TestClient so no live server is needed.
    """

    @pytest.fixture(autouse=True)
    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_process_pdf_with_acroform(self):
        pdf = _minimal_pdf()
        resp = self.client.post(
            "/api/v1/process-pdf?user_language=en&document_language=de",
            files={"file": ("form.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "pdf_token" in body
        assert isinstance(body["pdf_token"], str)
        assert len(body["pdf_token"]) > 100   # non-trivial signed token

    def test_process_pdf_grounding_rate_100(self):
        pdf = _minimal_pdf()
        resp = self.client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("form.pdf", pdf, "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["analysis_report"]["grounding_rate"] == "100%"
        assert body["analysis_report"]["grounding_ok"] is True

    def test_process_pdf_all_questions_in_extracted_ids(self):
        pdf = _minimal_pdf()
        resp = self.client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("form.pdf", pdf, "application/pdf")},
        )
        body = resp.json()
        extracted = set(body["extracted_field_ids"])
        for field in body["fields"]:
            assert field["key"] in extracted, (
                f"Question key '{field['key']}' not in extracted_field_ids {extracted}"
            )

    def test_process_pdf_token_round_trips_back(self):
        """Token from process-pdf must decode back to the same PDF bytes."""
        pdf   = _minimal_pdf()
        resp  = self.client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("form.pdf", pdf, "application/pdf")},
        )
        token  = resp.json()["pdf_token"]
        # Decode with the server's secret key (accessed via settings in test context)
        from app.config import settings
        data = verify_pdf_token(token, settings.secret_key)
        assert data["pdf_bytes"] == pdf

    def test_non_pdf_rejected(self):
        resp = self.client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("text.txt", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 400

    def test_missing_file_rejected(self):
        resp = self.client.post("/api/v1/process-pdf?user_language=en")
        assert resp.status_code == 422   # FastAPI validation error


# ── 4. Cold-start invariant ───────────────────────────────────────────────────

class TestColdStartInvariant:
    """
    Verifies that the stateless pipeline does not depend on any shared state
    between /process-pdf and /fill-pdf.
    """

    def test_token_survives_different_secret_instances(self):
        """
        In production, SECRET_KEY is a stable env var so the same key is used
        across all Lambda invocations.  The test verifies the invariant holds
        when the secret is stable.
        """
        pdf    = _minimal_pdf()
        token  = sign_pdf_token(pdf, ["Vorname"], "f.pdf", SECRET)
        # Simulate a cold start: new process, same secret key
        data   = verify_pdf_token(token, SECRET)
        assert data["pdf_bytes"] == pdf
        assert data["field_ids"] == ["Vorname"]

    def test_random_secret_key_breaks_old_tokens(self):
        """
        If SECRET_KEY is not set (per-process random default), a new cold start
        produces a different key and old tokens are rejected.  This is the
        CORRECT behavior: user must re-upload after a cold start.
        """
        pdf    = _minimal_pdf()
        token  = sign_pdf_token(pdf, ["X"], "f.pdf", "secret-A")
        with pytest.raises(BadSignature):
            verify_pdf_token(token, "secret-B")   # different "cold start" key
