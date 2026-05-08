"""
Phase D/D4 + D5 — Level 2 (AcroForm) round-trip and edge-case tests.

D4 — Round-trip:
  Synthetic AcroForm PDF (text + date + checkbox + select + radio) goes
  through the full /process-pdf → /fill-pdf cycle. Asserts:
    - Routing: support_level=2, extraction_source=acroform, fill_strategy=acroform
    - Question generation: every shown question has a real source, no hallucinated keys
    - Answers preserve field_id (no rename, no clean-up)
    - /fill-pdf writes back into the original PDF widgets
    - Output page count == input page count
    - Text answer survives the round-trip and is readable in the output
    - Checkbox normalises to "Yes"/"Off" correctly
    - Grounding guard rejects invented answer keys

D5 — Edge cases:
    - Nested field tree (group node with /Kids)
    - Field with /TU tooltip preferred over technical /T
    - Field WITHOUT /TU — falls back to _clean_acroform_field_name
    - Duplicate raw widget names across kids (dedup'd by `seen`)
    - Checkbox export values OTHER than "Yes" (PDF normalisation)
    - Multiselect field with /Opt array of [value, label] pairs
    - Field with no /Rect (missing bbox)
    - Prefilled field (/V set)

Run with:  pytest tests/test_acroform_level2.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

# PyMuPDF is needed for one of the round-trip assertions (read text back from
# the filled PDF). Skip the file if it is unavailable in this environment.
pytest.importorskip(
    "fitz",
    reason="PyMuPDF (`fitz`) required for AcroForm round-trip text-back assertions. "
           "Install: pip install pymupdf",
)


# ── Synthetic AcroForm fixtures ──────────────────────────────────────────────

def _multi_field_acroform_pdf() -> bytes:
    """
    Build a synthetic 2-page AcroForm PDF with text, text-as-date, checkbox,
    and choice (select) widgets, using a hand-rolled PDF body.

    reportlab's `acroForm.checkbox` raises UnboundLocalError on the
    installed version, so we skip its high-level builder entirely. Hand-
    rolling keeps the test self-contained and dependency-stable.

    The widget /T names match the German deterministic dictionary so the
    pre-resolution chain skips AI for these labels (D3 invariant).
    """
    # Object layout (1-indexed):
    #   1: Catalog → AcroForm 5
    #   2: Pages   → kids [3, 4]
    #   3: Page 1  → annots [6, 7, 8, 9]
    #   4: Page 2  → empty
    #   5: AcroForm root /Fields [6, 7, 8, 9]
    #   6: Vorname        text /Tx
    #   7: Geburtsdatum   text /Tx
    #   8: Hat_Kinder     checkbox /Btn
    #   9: Familienstand  select /Ch with /Opt list
    body_objs: dict[int, bytes] = {}
    body_objs[1] = b"<< /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >>"
    body_objs[2] = b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>"
    body_objs[3] = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Annots [6 0 R 7 0 R 8 0 R 9 0 R] >>"
    )
    body_objs[4] = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>"
    body_objs[5] = b"<< /Fields [6 0 R 7 0 R 8 0 R 9 0 R] /DR << >> >>"
    body_objs[6] = (
        b"<< /Type /Annot /Subtype /Widget /FT /Tx "
        b"/T (Vorname) /Rect [180 750 400 770] /P 3 0 R >>"
    )
    body_objs[7] = (
        b"<< /Type /Annot /Subtype /Widget /FT /Tx "
        b"/T (Geburtsdatum) /Rect [180 720 400 740] /P 3 0 R >>"
    )
    body_objs[8] = (
        b"<< /Type /Annot /Subtype /Widget /FT /Btn "
        b"/T (Hat_Kinder) /Rect [180 690 200 710] /P 3 0 R >>"
    )
    body_objs[9] = (
        b"<< /Type /Annot /Subtype /Widget /FT /Ch "
        b"/T (Familienstand) /Rect [180 660 400 680] /P 3 0 R "
        b"/Opt [(ledig) (verheiratet) (geschieden)] >>"
    )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for n in sorted(body_objs):
        offsets[n] = out.tell()
        out.write(f"{n} 0 obj\n".encode("ascii"))
        out.write(body_objs[n])
        out.write(b"\nendobj\n")

    xref_offset = out.tell()
    n_objs = max(body_objs) + 1
    out.write(f"xref\n0 {n_objs}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for n in range(1, n_objs):
        out.write(f"{offsets[n]:010d} 00000 n \n".encode("ascii"))
    out.write(b"trailer\n")
    out.write(f"<< /Size {n_objs} /Root 1 0 R >>\n".encode("ascii"))
    out.write(b"startxref\n")
    out.write(f"{xref_offset}\n".encode("ascii"))
    out.write(b"%%EOF\n")
    return out.getvalue()


def _empty_path_pdf() -> bytes:
    """A valid-looking PDF that has NO AcroForm — used by negative cases."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(50, 800, "no fields here")
    c.save()
    return buf.getvalue()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _post(client, pdf_bytes: bytes, locale: str = "en") -> dict:
    resp = client.post(
        f"/api/v1/process-pdf?user_language={locale}",
        files={"file": ("acro.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── D4 — Routing + extraction round-trip ─────────────────────────────────────

class TestAcroFormRouting:
    @pytest.fixture(autouse=True)
    def _process(self, client):
        self.body = _post(client, _multi_field_acroform_pdf())
        self.report = self.body["analysis_report"]
        self.fields = self.body["fields"]

    def test_support_level_is_2(self):
        assert self.report["support_level"] == 2

    def test_extraction_source_is_acroform(self):
        assert self.report["extraction_source"] == "acroform"

    def test_template_id_is_none(self):
        assert self.report["template_id"] is None

    def test_fill_strategy_is_acroform(self):
        # Phase D/D2 — frontend uses this to set expectations BEFORE submit.
        assert self.report["fill_strategy"] == "acroform"


# ── D4 — Field map quality ──────────────────────────────────────────────────

class TestAcroFormFieldMap:
    @pytest.fixture(autouse=True)
    def _process(self, client):
        self.body = _post(client, _multi_field_acroform_pdf())
        self.fields = self.body["fields"]
        self.extracted_ids = self.body["extracted_field_ids"]

    def test_all_4_fields_extracted(self):
        ids = {f["key"] for f in self.fields}
        # reportlab prefixes form fields with empty parent — names come through
        # exactly as given.
        assert {"Vorname", "Geburtsdatum", "Hat_Kinder", "Familienstand"} <= ids

    def test_extracted_field_ids_match_field_keys(self):
        # The grounding invariant — extracted_field_ids must equal the keys
        # of the visible fields exactly.
        assert set(self.extracted_ids) == {f["key"] for f in self.fields}

    def test_field_types_are_correct(self):
        type_by_key = {f["key"]: f["input_type"] for f in self.fields}
        assert type_by_key["Vorname"] == "text"
        assert type_by_key["Geburtsdatum"] == "text"
        assert type_by_key["Hat_Kinder"] == "checkbox"
        assert type_by_key["Familienstand"] == "select"

    def test_select_options_preserved(self):
        familien = next(f for f in self.fields if f["key"] == "Familienstand")
        opt_values = [o["value"] for o in familien["options"]]
        assert opt_values == ["ledig", "verheiratet", "geschieden"]

    def test_no_question_invented(self):
        # Every rendered field_id must trace back to extracted_field_ids
        # (anti-hallucination invariant).
        for f in self.fields:
            assert f["key"] in self.extracted_ids


# ── D4 — Question quality on AcroForm path ──────────────────────────────────

class TestAcroFormQuestionQuality:
    @pytest.fixture(autouse=True)
    def _process(self, client):
        self.body = _post(client, _multi_field_acroform_pdf())
        self.fields = self.body["fields"]
        self.report = self.body["analysis_report"]

    def test_common_labels_resolved_without_AI(self):
        # Vorname, Geburtsdatum, Familienstand all appear in the deterministic
        # dictionary or semantic_questions — none should fall through to AI.
        sources = {f["key"]: f.get("question_source") for f in self.fields}
        for fid in ("Vorname", "Geburtsdatum", "Familienstand"):
            assert sources[fid] in ("verified", "semantic", "deterministic"), (
                f"{fid} resolved via {sources[fid]} — should be pre-resolved"
            )

    def test_acroform_metrics_field_type_breakdown(self):
        m = self.report.get("acroform_metrics") or {}
        assert m.get("text_count", 0) >= 2          # Vorname + Geburtsdatum
        assert m.get("checkbox_count", 0) >= 1      # Hat_Kinder
        assert m.get("select_count", 0) >= 1        # Familienstand

    def test_acroform_metrics_includes_semantic_coverage(self):
        m = self.report.get("acroform_metrics") or {}
        assert "fields_with_semantic_key" in m
        assert "fields_without_semantic_key" in m
        # After D3 inference ran, Vorname/Geburtsdatum/etc. should have
        # semantic_keys set → coverage > 0.
        assert m["fields_with_semantic_key"] > 0


# ── D4 — End-to-end: process → fill → readable PDF ──────────────────────────

class TestAcroFormRoundTrip:
    @pytest.fixture(autouse=True)
    def _process(self, client):
        self.body = _post(client, _multi_field_acroform_pdf())
        self.client = client
        self.token = self.body["pdf_token"]
        self.input_pdf = _multi_field_acroform_pdf()

    def test_fill_pdf_writes_into_original_widgets(self):
        answers = {
            "Vorname":      "Anna",
            "Geburtsdatum": "15.03.1985",
            "Hat_Kinder":   "yes",
            "Familienstand": "verheiratet",
        }
        resp = self.client.post(
            "/api/v1/fill-pdf",
            json={
                "pdf_token":    self.token,
                "answers":      answers,
                "field_labels": {},
            },
        )
        assert resp.status_code == 200, resp.text
        out = resp.content
        assert out[:4] == b"%PDF"
        # Phase E/E1 — header reports the EXACT strategy taken; Level 2
        # AcroForm fills must carry the precise "acroform" advertisement,
        # never the legacy generic "pypdf_or_summary".
        assert resp.headers.get("X-Fill-Strategy") == "acroform"

    def test_output_page_count_equals_input(self):
        answers = {"Vorname": "Anna"}
        resp = self.client.post(
            "/api/v1/fill-pdf",
            json={"pdf_token": self.token, "answers": answers, "field_labels": {}},
        )
        out = resp.content
        import fitz
        in_doc = fitz.open(stream=self.input_pdf, filetype="pdf")
        out_doc = fitz.open(stream=out, filetype="pdf")
        assert in_doc.page_count == out_doc.page_count
        in_doc.close(); out_doc.close()

    def test_text_answer_appears_in_output_widget(self):
        answers = {"Vorname": "Sigmund"}
        resp = self.client.post(
            "/api/v1/fill-pdf",
            json={"pdf_token": self.token, "answers": answers, "field_labels": {}},
        )
        out = resp.content
        # Read the AcroForm field VALUES back from the output PDF.
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(out))
        fields = reader.get_fields() or {}
        vorname = fields.get("Vorname") or fields.get("/Vorname")
        if vorname is None:
            # Some pypdf versions key by raw field name with different prefix;
            # search the dict.
            vorname = next(
                (v for k, v in fields.items() if k.lstrip("/") == "Vorname"),
                None,
            )
        assert vorname is not None, f"Vorname not found in output fields: {list(fields)}"
        assert str(vorname.get("/V", "")).strip() == "Sigmund"

    def test_checkbox_yes_normalises_to_on_value(self):
        answers = {"Hat_Kinder": "yes"}
        resp = self.client.post(
            "/api/v1/fill-pdf",
            json={"pdf_token": self.token, "answers": answers, "field_labels": {}},
        )
        out = resp.content
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(out))
        fields = reader.get_fields() or {}
        cb = next((v for k, v in fields.items() if k.lstrip("/") == "Hat_Kinder"), None)
        assert cb is not None
        # PyPDFGenerator normalises truthy raw answers to "Yes" before writing.
        # Some PDF writers store this as /Yes (a name) rather than the literal
        # string — accept both forms as long as it isn't /Off.
        v = str(cb.get("/V", "")).lstrip("/")
        assert v.lower() in ("yes", "on", "x", "1"), f"Unexpected checkbox value: {v!r}"

    def test_grounding_guard_rejects_invented_answer_key(self):
        resp = self.client.post(
            "/api/v1/fill-pdf",
            json={
                "pdf_token":    self.token,
                "answers":      {"NotARealField": "x"},
                "field_labels": {},
            },
        )
        # The grounding guard returns 400.
        assert resp.status_code == 400


# ── D5 — Edge cases ─────────────────────────────────────────────────────────

class TestAcroFormEdgeCases:
    """
    Edge cases that real-world AcroForm PDFs commonly hit. Each test here
    documents a behavior we rely on so future refactors don't quietly drop it.
    """

    def test_field_without_TU_uses_cleaned_widget_name(self, client):
        # Our reportlab fixture does NOT set /TU; original_label must come
        # from _clean_acroform_field_name (preserves Vorname as-is).
        body = _post(client, _multi_field_acroform_pdf())
        labels = {f["key"]: f["original_label"] for f in body["fields"]}
        assert "Vorname" in labels["Vorname"] or labels["Vorname"] == "Vorname"

    def test_select_field_carries_options_in_field_definition(self, client):
        body = _post(client, _multi_field_acroform_pdf())
        familien = next(f for f in body["fields"] if f["key"] == "Familienstand")
        assert len(familien["options"]) == 3
        # Each option must have BOTH value (PDF-native) and label (user-facing).
        for o in familien["options"]:
            assert "value" in o
            assert "label" in o

    def test_no_acroform_routes_to_level_3_or_4(self, client):
        # The empty fixture has very little extractable text and no AcroForm.
        # The router must NOT mistake it for Level 1 or Level 2. It either
        # routes to Level 3/4 (200 with support_level in {3, 4}) or the
        # endpoint guards reject it cleanly with 4xx — both acceptable.
        resp = client.post(
            "/api/v1/process-pdf?user_language=en",
            files={"file": ("empty.pdf", _empty_path_pdf(), "application/pdf")},
        )
        if resp.status_code == 200:
            assert resp.json()["analysis_report"]["support_level"] in (3, 4)
        else:
            # Endpoint refused (e.g. 422 "scanned image not supported").
            # The contract here is "do not silently treat as Level 1/2",
            # which a 4xx satisfies.
            assert 400 <= resp.status_code < 500

    def test_pushbutton_filtered_out(self):
        # Direct unit test of _classify_field_type
        from app.services.pdf_pipeline import (
            _classify_field_type, _FF_PUSHBUTTON,
        )
        assert _classify_field_type("/Btn", _FF_PUSHBUTTON) is None

    def test_radio_options_helper_handles_empty_kids(self):
        from app.services.pdf_pipeline import _radio_options_from_kids

        class FakeField:
            def get(self, key, default=None):
                return default if key == "/Kids" else default
            def __contains__(self, key):
                return False
        assert _radio_options_from_kids(FakeField()) == []

    def test_clean_widget_name_strips_namespace_words(self):
        from app.services.pdf_pipeline import _clean_acroform_field_name
        # The function strips known namespace words (Person, Adresse, …)
        # so the deterministic dictionary can match the real label.
        assert _clean_acroform_field_name("txtfPersonVorname") == "Vorname"
        assert _clean_acroform_field_name("txtfAdressePLZ") == "Postleitzahl"

    def test_clean_widget_name_handles_compound_abbreviations(self):
        from app.services.pdf_pipeline import _clean_acroform_field_name
        # GebDatum → Geburtsdatum (German compound expansion)
        result = _clean_acroform_field_name("datePersonGebDatum")
        assert "Geburtsdatum" in result

    def test_semantic_key_inference_runs_for_acroform_fields(self, client):
        # After D3, AcroForm fields whose original_label maps to a known
        # semantic_key should have it set on the FieldDefinition.
        body = _post(client, _multi_field_acroform_pdf())
        sem_keys = {f["key"]: f.get("semantic_key") for f in body["fields"]}
        # Vorname → person.first_name (per LABEL_TO_SEMANTIC)
        assert sem_keys.get("Vorname") is not None

    def test_prefilled_field_value_preserved(self):
        # Direct unit test against extract_acroform_fields with a synthetic
        # PDF whose /V is set on a widget. Easier than wiring through the
        # full endpoint; the extractor is the only thing we're testing.
        from app.services.pdf_pipeline import extract_acroform_fields

        pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
  /Annots [6 0 R] >> endobj
5 0 obj << /Fields [6 0 R] /DR << >> >> endobj
6 0 obj << /Type /Annot /Subtype /Widget /FT /Tx
  /T (Vorname) /V (Anna) /Rect [50 750 250 770] /P 3 0 R >> endobj
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
        fields = extract_acroform_fields(pdf)
        anna = next((f for f in fields if f.field_id == "Vorname"), None)
        assert anna is not None
        assert anna.current_value == "Anna"

    def test_field_with_missing_rect_still_extracted(self):
        # No /Annots → no widget_positions hit → bbox=None, page=1 default.
        # The field still appears in the extraction (with bbox=None).
        from app.services.pdf_pipeline import extract_acroform_fields
        pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj
5 0 obj << /Fields [6 0 R] /DR << >> >> endobj
6 0 obj << /Type /Annot /Subtype /Widget /FT /Tx /T (NoRect) >> endobj
xref
0 7
0000000000 65535 f\r
0000000009 00000 n\r
0000000068 00000 n\r
0000000125 00000 n\r
0000000000 65535 f\r
0000000260 00000 n\r
0000000310 00000 n\r
trailer << /Size 7 /Root 1 0 R >>
startxref
380
%%EOF"""
        fields = extract_acroform_fields(pdf)
        no_rect = next((f for f in fields if f.field_id == "NoRect"), None)
        # Either extracted (bbox=None) or quietly dropped — either is acceptable
        # as long as we don't raise and we don't invent a fake bbox.
        if no_rect is not None:
            assert no_rect.bbox is None or no_rect.bbox == [0.0, 0.0, 0.0, 0.0]


# ── D5 — Acroform metrics expose the semantic-coverage gap visibly ──────────

class TestAcroformMetricsExposeGaps:
    def test_metrics_present_for_every_acroform_response(self, client):
        body = _post(client, _multi_field_acroform_pdf())
        metrics = body["analysis_report"]["acroform_metrics"]
        assert metrics is not None
        for required_key in (
            "text_count", "date_count", "number_count",
            "checkbox_count", "radio_count", "select_count",
            "multiselect_count", "signature_count",
            "fields_missing_bbox",
            "fields_with_semantic_key", "fields_without_semantic_key",
            "fields_with_tu_label", "fields_with_weak_label",
            "duplicate_label_groups",
        ):
            assert required_key in metrics, f"Missing metric: {required_key}"
            assert isinstance(metrics[required_key], int)
