"""
Phase E/E2 — fill_strategy enforcement tests.

These tests lock down the central output-safety promise:

  Level 1 (verified)  → /fill-pdf returns the original PDF with a fitz overlay,
                         OR a clean 500 error. NEVER a summary PDF.
  Level 2 (acroform)  → /fill-pdf returns the original PDF with AcroForm fields
                         filled, OR a clean 500 error. NEVER a summary PDF.
  Level 3 (flat)      → /fill-pdf MAY return a reportlab summary; the
                         X-Fill-Strategy header MUST advertise "summary" so the
                         frontend can warn the user.

Every test here exists because the original product had a path where Level 1/2
could silently return a summary PDF that LOOKED like a successful fill but was
actually an answer-summary document.

Run with:  pytest tests/test_fill_strategy_enforcement.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

# PyMuPDF is needed for the Level 1 paths (fitz_overlay).
pytest.importorskip("fitz", reason="PyMuPDF required for Level 1 fill_strategy tests.")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _but_pdf_bytes() -> bytes:
    """BuT-fingerprint flat PDF — routes Level 1."""
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
        c.drawString(50, y, line); y -= 22
    c.save()
    return buf.getvalue()


def _acroform_pdf_bytes() -> bytes:
    """Hand-rolled minimal AcroForm — routes Level 2."""
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Annots [6 0 R] >>",
        5: b"<< /Fields [6 0 R] /DR << >> >>",
        6: b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (Vorname) /Rect [50 750 250 770] /P 3 0 R >>",
    }
    offsets = {}
    for n in sorted(objs):
        offsets[n] = out.tell()
        out.write(f"{n} 0 obj\n".encode())
        out.write(objs[n])
        out.write(b"\nendobj\n")
    xref = out.tell()
    n_objs = max(objs) + 1
    out.write(f"xref\n0 {n_objs}\n0000000000 65535 f \n".encode())
    for n in range(1, n_objs):
        if n in offsets:
            out.write(f"{offsets[n]:010d} 00000 n \n".encode())
        else:
            # Free entry placeholder for skipped object numbers (e.g. 4)
            out.write(b"0000000000 65535 f \n")
    out.write(b"trailer\n")
    out.write(f"<< /Size {n_objs} /Root 1 0 R >>\n".encode())
    out.write(f"startxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def _post_process(client, pdf_bytes: bytes) -> dict:
    resp = client.post(
        "/api/v1/process-pdf?user_language=en",
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill(client, token: str, answers: dict) -> "Response":
    return client.post(
        "/api/v1/fill-pdf",
        json={"pdf_token": token, "answers": answers, "field_labels": {}},
    )


# ── Level 1 invariants ───────────────────────────────────────────────────────

class TestLevel1NeverReturnsSummary:
    def setup_method(self):
        from app.main import app
        self.client = TestClient(app)
        self.body = _post_process(self.client, _but_pdf_bytes())
        self.token = self.body["pdf_token"]

    def test_pdf_token_carries_support_level_1(self):
        from app.services.pdf_token import verify_pdf_token
        from app.config import settings
        decoded = verify_pdf_token(self.token, settings.secret_key)
        assert decoded["support_level"] == 1

    def test_successful_fill_advertises_fitz_overlay(self):
        # Use a key that exists in the BuT template
        answers = {"applicant_name_vorname": "Anna"}
        resp = _fill(self.client, self.token, answers)
        assert resp.status_code == 200
        assert resp.headers.get("X-Fill-Strategy") == "fitz_overlay"

    def test_fitz_failure_returns_500_not_summary(self, monkeypatch):
        # Force fitz_overlay to crash and assert we get a 500 (NOT a summary PDF).
        from app.services.pdf_generator import fitz_overlay

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated fitz failure")

        monkeypatch.setattr(fitz_overlay, "fill_with_fitz", _boom)
        # Patch the symbol where fill_pdf imports it (lazy import inside the
        # endpoint) — easier: patch the module-level reference.
        from app.services.pdf_generator.fitz_overlay import fill_with_fitz  # noqa
        # The endpoint does `from app.services.pdf_generator.fitz_overlay import fill_with_fitz`
        # inside the request handler, so patching the source module is enough.
        resp = _fill(self.client, self.token, {"applicant_name_vorname": "Anna"})
        assert resp.status_code == 500
        # The 500 body must be the friendly user message — NOT a PDF.
        assert resp.headers.get("content-type", "").startswith("application/json")
        # Specifically, the response must not advertise any "summary" strategy.
        assert resp.headers.get("X-Fill-Strategy") != "summary"


# ── Level 2 invariants ───────────────────────────────────────────────────────

class TestLevel2NeverReturnsSummary:
    def setup_method(self):
        from app.main import app
        self.client = TestClient(app)
        self.body = _post_process(self.client, _acroform_pdf_bytes())
        self.token = self.body["pdf_token"]

    def test_pdf_token_carries_support_level_2(self):
        from app.services.pdf_token import verify_pdf_token
        from app.config import settings
        decoded = verify_pdf_token(self.token, settings.secret_key)
        assert decoded["support_level"] == 2

    def test_successful_fill_advertises_acroform(self):
        resp = _fill(self.client, self.token, {"Vorname": "Anna"})
        assert resp.status_code == 200
        # The header MUST be the precise strategy. "summary" or "minimal" or
        # the legacy "pypdf_or_summary" would all be safety violations.
        assert resp.headers.get("X-Fill-Strategy") == "acroform"

    def test_pypdf_crash_returns_500_not_summary(self, monkeypatch):
        # Make the generator crash. Level 2 must surface a 500 with the
        # "fill failed" friendly message — NEVER fall through to a summary.
        from app.services.pdf_generator import pypdf_generator

        original_generate = pypdf_generator.PyPDFGenerator.generate

        async def _boom(self, request):
            raise RuntimeError("simulated pypdf failure")

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _boom)
        resp = _fill(self.client, self.token, {"Vorname": "Anna"})
        # Restore for cleanliness (monkeypatch handles this automatically too)
        pypdf_generator.PyPDFGenerator.generate = original_generate

        assert resp.status_code == 500
        assert resp.headers.get("content-type", "").startswith("application/json")
        # Critical: no summary PDF body, no "summary" advertisement.
        assert resp.headers.get("X-Fill-Strategy") != "summary"

    def test_zero_fill_with_answers_returns_500(self, monkeypatch):
        # Simulate an AcroForm fill that completes but writes 0 widgets while
        # the user provided answers. This is the silent-failure scenario E1
        # explicitly forbids for Level 2.
        from app.services.pdf_generator import pypdf_generator
        from app.services.pdf_generator.base import PDFGenerationResult

        async def _zero(self, request):
            return PDFGenerationResult(
                pdf_bytes=b"%PDF-1.4\n%fake\n",
                field_count_filled=0,
                warnings=["simulated: writer wrote nothing"],
                strategy="acroform",
            )

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _zero)
        resp = _fill(self.client, self.token, {"Vorname": "Anna"})
        assert resp.status_code == 500

    def test_summary_strategy_for_level_2_returns_500(self, monkeypatch):
        # Simulate the generator falling back to a reportlab summary for a
        # Level 2 PDF. The endpoint MUST refuse it.
        from app.services.pdf_generator import pypdf_generator
        from app.services.pdf_generator.base import PDFGenerationResult

        async def _summary(self, request):
            return PDFGenerationResult(
                pdf_bytes=b"%PDF-1.4\n%fake summary\n",
                field_count_filled=2,
                warnings=["fell back to summary"],
                strategy="summary",
            )

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _summary)
        resp = _fill(self.client, self.token, {"Vorname": "Anna"})
        assert resp.status_code == 500


# ── analysis_report.fill_strategy advertisement ──────────────────────────────

class TestFillStrategyAdvertisement:
    """
    The frontend reads `analysis_report.fill_strategy` BEFORE the fill request
    so it can show the right output-guarantee text. These tests assert the
    advertisement is correct and per-level honest.
    """

    def test_level_1_advertises_fitz_overlay(self):
        from app.main import app
        c = TestClient(app)
        body = _post_process(c, _but_pdf_bytes())
        assert body["analysis_report"]["fill_strategy"] == "fitz_overlay"
        assert body["analysis_report"]["support_level"] == 1

    def test_level_2_advertises_acroform(self):
        from app.main import app
        c = TestClient(app)
        body = _post_process(c, _acroform_pdf_bytes())
        assert body["analysis_report"]["fill_strategy"] == "acroform"
        assert body["analysis_report"]["support_level"] == 2

    def test_pdf_token_round_trip_preserves_support_level(self):
        # Defensive — sign + verify cycle keeps support_level intact.
        from app.services.pdf_token import sign_pdf_token, verify_pdf_token
        for level in (1, 2, 3, 4):
            token = sign_pdf_token(
                pdf_bytes=b"%PDF-1.4\n",
                field_ids=["a", "b"],
                filename="t.pdf",
                secret_key="test-secret",
                template_id="tpl_x" if level == 1 else None,
                support_level=level,
            )
            decoded = verify_pdf_token(token, "test-secret")
            assert decoded["support_level"] == level

    def test_pdf_token_without_support_level_decodes_to_none(self):
        # Backwards-compat: tokens signed before E1 don't carry support_level.
        # The verifier returns None — fill_pdf treats None as "non-strict".
        from app.services.pdf_token import sign_pdf_token, verify_pdf_token
        token = sign_pdf_token(
            pdf_bytes=b"%PDF-1.4\n",
            field_ids=["a"],
            filename="t.pdf",
            secret_key="test-secret",
            # support_level intentionally omitted
        )
        decoded = verify_pdf_token(token, "test-secret")
        assert decoded["support_level"] is None


# ── Phase F/0-C — Verified template + acroform fill_strategy ─────────────────

class TestVerifiedTemplateFillStrategyDispatch:
    """
    Phase F/0-C — When a verified template declares fill_strategy="acroform",
    /fill-pdf MUST route to the strict AcroForm path:
      - PyPDFGenerator crash → friendly 500
      - generator returns strategy="summary"/"minimal" → friendly 500
      - acroform fill writes 0 fields with answers > 0 → friendly 500
      - X-Fill-Strategy header advertises "acroform"
      - support_level remains 1

    The Jobcenter BuT template (fill_strategy="fitz_overlay" by default) MUST
    continue to use fitz overlay — the new branch must not change its behavior.

    These tests use a synthetic in-test verified template registered into the
    template cache so we can drive the new branch without modifying any
    production template module.
    """

    @pytest.fixture(autouse=True)
    def _install_synthetic_template(self, monkeypatch):
        """
        Inject a synthetic VerifiedTemplate that:
          - fingerprints on the literal phrase "synthetic-acroform-fixture"
          - returns a single 'Vorname' field
          - declares fill_strategy="acroform"

        Patches `_TEMPLATES_CACHE` and `_all_templates()` so both
        `find_matching_template()` and `find_template_by_id()` see it.
        """
        from app.services import form_templates
        from app.services.pdf_pipeline import FieldMapEntry

        class _SyntheticAcroFormTemplate(form_templates.VerifiedTemplate):
            template_id = "synthetic_acroform_v1"
            name = "Synthetic AcroForm Test Template"
            fill_strategy = "acroform"

            def fingerprint(self, full_text: str) -> bool:
                return "synthetic-acroform-fixture" in full_text.lower()

            def get_field_map(self):
                return [
                    FieldMapEntry(
                        field_id="Vorname",
                        original_label="Vorname",
                        field_type="text",
                        source_page=1,
                        confidence=1.0,
                        source="verified_template",
                        source_text="Vorname",
                    ),
                ]

        # Insert into the cache so both lookup paths see it. Save the
        # original cache for restoration after the test.
        original_cache = form_templates._TEMPLATES_CACHE
        from app.services.form_templates.jobcenter_but import JobcenterButTemplate
        form_templates._TEMPLATES_CACHE = [
            JobcenterButTemplate(),
            _SyntheticAcroFormTemplate(),
        ]
        # Also pre-register the synthetic field_id in VERIFIED_BY_FIELD_ID so
        # the question pre-resolution loop assigns it source="verified" and
        # the Level-1 weak/AI invariants stay satisfied. (We intentionally
        # use "Vorname" because it already exists in the deterministic
        # dictionary; without the verified entry we'd get source="deterministic".)
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        original_vorname = VERIFIED_BY_FIELD_ID.get("Vorname")
        VERIFIED_BY_FIELD_ID["Vorname"] = {
            "en": {"question": "What is your first name?", "help": ""},
            "de": {"question": "Wie ist Ihr Vorname?", "help": ""},
        }

        yield

        form_templates._TEMPLATES_CACHE = original_cache
        if original_vorname is None:
            VERIFIED_BY_FIELD_ID.pop("Vorname", None)
        else:
            VERIFIED_BY_FIELD_ID["Vorname"] = original_vorname

    def _synth_pdf_with_vorname_widget(self) -> bytes:
        """
        AcroForm PDF whose extracted text contains the synthetic fingerprint
        AND whose /AcroForm has a Vorname /Tx widget so PyPDFGenerator can
        actually fill it.
        """
        # Hand-rolled minimal AcroForm with a content stream printing the
        # fingerprint phrase. The 4-object content stream is the minimum
        # pdfplumber needs to extract readable text.
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        # Object 7 is a content stream that draws "synthetic-acroform-fixture"
        content = (
            b"BT /F1 12 Tf 50 750 Td (synthetic-acroform-fixture for Vorname filling) Tj ET"
        )
        objs = {
            1: b"<< /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 4 0 R >> >> "
                b"/Contents 7 0 R /Annots [6 0 R] >>"
            ),
            4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            5: b"<< /Fields [6 0 R] /DR << >> >>",
            6: (
                b"<< /Type /Annot /Subtype /Widget /FT /Tx "
                b"/T (Vorname) /Rect [50 700 250 720] /P 3 0 R >>"
            ),
            7: b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        }
        offsets = {}
        for n in sorted(objs):
            offsets[n] = out.tell()
            out.write(f"{n} 0 obj\n".encode())
            out.write(objs[n])
            out.write(b"\nendobj\n")
        xref = out.tell()
        n_objs = max(objs) + 1
        out.write(f"xref\n0 {n_objs}\n0000000000 65535 f \n".encode())
        for n in range(1, n_objs):
            out.write(f"{offsets[n]:010d} 00000 n \n".encode())
        out.write(b"trailer\n")
        out.write(f"<< /Size {n_objs} /Root 1 0 R >>\n".encode())
        out.write(f"startxref\n{xref}\n%%EOF\n".encode())
        return out.getvalue()

    # ── Routing assertions ───────────────────────────────────────────────────

    def test_synthetic_pdf_routes_to_verified_acroform_template(self):
        from app.main import app
        client = TestClient(app)
        body = _post_process(client, self._synth_pdf_with_vorname_widget())
        assert body["analysis_report"]["template_id"] == "synthetic_acroform_v1"
        assert body["analysis_report"]["support_level"] == 1
        # Phase F/0 follow-up: process_pdf now reads template.fill_strategy
        # for Level 1 templates instead of hard-coding "fitz_overlay". A
        # verified-acroform template MUST advertise "acroform" at process
        # time so the upload-page UX matches the actual fill behavior.
        assert body["analysis_report"]["fill_strategy"] == "acroform"

    def test_verified_acroform_fill_advertises_acroform_strategy(self):
        from app.main import app
        client = TestClient(app)
        body = _post_process(client, self._synth_pdf_with_vorname_widget())
        token = body["pdf_token"]
        resp = _fill(client, token, {"Vorname": "Anna"})
        assert resp.status_code == 200, resp.text
        # The header MUST be the strategy actually taken by the engine.
        assert resp.headers.get("X-Fill-Strategy") == "acroform"
        # And the support level was Level 1 throughout.
        assert resp.content[:4] == b"%PDF"

    # ── Strict-policy assertions ─────────────────────────────────────────────

    def test_verified_acroform_pypdf_crash_returns_500(self, monkeypatch):
        from app.main import app
        from app.services.pdf_generator import pypdf_generator

        client = TestClient(app)
        body = _post_process(client, self._synth_pdf_with_vorname_widget())
        token = body["pdf_token"]

        async def _boom(self, request):
            raise RuntimeError("simulated pypdf failure on verified-acroform path")

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _boom)
        resp = _fill(client, token, {"Vorname": "Anna"})
        assert resp.status_code == 500
        assert resp.headers.get("content-type", "").startswith("application/json")
        assert resp.headers.get("X-Fill-Strategy") != "summary"

    def test_verified_acroform_summary_strategy_returns_500(self, monkeypatch):
        from app.main import app
        from app.services.pdf_generator import pypdf_generator
        from app.services.pdf_generator.base import PDFGenerationResult

        client = TestClient(app)
        body = _post_process(client, self._synth_pdf_with_vorname_widget())
        token = body["pdf_token"]

        async def _summary(self, request):
            return PDFGenerationResult(
                pdf_bytes=b"%PDF-1.4\n%fake summary\n",
                field_count_filled=1,
                warnings=["fell back to summary"],
                strategy="summary",
            )

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _summary)
        resp = _fill(client, token, {"Vorname": "Anna"})
        assert resp.status_code == 500

    def test_verified_acroform_minimal_strategy_returns_500(self, monkeypatch):
        from app.main import app
        from app.services.pdf_generator import pypdf_generator
        from app.services.pdf_generator.base import PDFGenerationResult

        client = TestClient(app)
        body = _post_process(client, self._synth_pdf_with_vorname_widget())
        token = body["pdf_token"]

        async def _minimal(self, request):
            return PDFGenerationResult(
                pdf_bytes=b"%PDF-1.4",
                field_count_filled=0,
                warnings=["reportlab missing"],
                strategy="minimal",
            )

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _minimal)
        resp = _fill(client, token, {"Vorname": "Anna"})
        assert resp.status_code == 500

    def test_verified_acroform_zero_fill_with_answers_returns_500(self, monkeypatch):
        from app.main import app
        from app.services.pdf_generator import pypdf_generator
        from app.services.pdf_generator.base import PDFGenerationResult

        client = TestClient(app)
        body = _post_process(client, self._synth_pdf_with_vorname_widget())
        token = body["pdf_token"]

        async def _zero(self, request):
            return PDFGenerationResult(
                pdf_bytes=b"%PDF-1.4\n%fake\n",
                field_count_filled=0,
                warnings=["wrote nothing"],
                strategy="acroform",
            )

        monkeypatch.setattr(pypdf_generator.PyPDFGenerator, "generate", _zero)
        resp = _fill(client, token, {"Vorname": "Anna"})
        assert resp.status_code == 500


# ── Hard rule: BuT template still uses fitz_overlay ──────────────────────────

class TestJobcenterStillUsesFitzOverlay:
    """
    Phase F/0-D — Confirm the engine extension did NOT change Jobcenter's
    behavior. JobcenterButTemplate has no `fill_strategy` declaration in
    its module, which means it inherits the base-class default
    `"fitz_overlay"`. The fill path MUST take the fitz branch.
    """

    def test_jobcenter_template_inherits_fitz_overlay_default(self):
        from app.services.form_templates.jobcenter_but import JobcenterButTemplate
        t = JobcenterButTemplate()
        assert t.fill_strategy == "fitz_overlay"

    def test_jobcenter_fill_response_advertises_fitz_overlay(self):
        from app.main import app
        client = TestClient(app)
        body = _post_process(client, _but_pdf_bytes())
        token = body["pdf_token"]
        # Use a real BuT field_id from VERIFIED_BY_FIELD_ID
        resp = _fill(client, token, {"applicant_name_vorname": "Anna"})
        assert resp.status_code == 200
        assert resp.headers.get("X-Fill-Strategy") == "fitz_overlay"

    def test_jobcenter_process_response_advertises_fitz_overlay(self):
        # Phase F/0 follow-up: process_pdf MUST still advertise
        # "fitz_overlay" for Jobcenter at upload time. The new lookup that
        # reads template.fill_strategy must respect the BuT default.
        from app.main import app
        client = TestClient(app)
        body = _post_process(client, _but_pdf_bytes())
        report = body["analysis_report"]
        assert report["template_id"] == "jobcenter_but_v1"
        assert report["support_level"] == 1
        assert report["fill_strategy"] == "fitz_overlay"
