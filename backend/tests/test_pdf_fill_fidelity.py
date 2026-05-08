"""
Tests for PDF fill fidelity — same PDF in, same PDF out with answers overlaid.

All tests use a minimal synthetic PDF created with reportlab (no real Jobcenter PDF
committed to the repo). The fixtures create a 2-page flat PDF with known German text
that mirrors the structure of the Jobcenter BuT form.

Hard dependency: PyMuPDF (`fitz`). It is declared in requirements.txt
(pymupdf==1.24.11) and is installed in CI. If a developer runs these tests
in an environment that lacks PyMuPDF, every test in this file is SKIPPED
with a clear reason (rather than ImportError-crashing collection). To run
the full fidelity suite locally:  `pip install pymupdf`.
"""
from __future__ import annotations

import io
import pytest

# Skip the whole file with a visible reason if PyMuPDF isn't installed.
# importorskip raises pytest.skip — collection succeeds, every test reports SKIPPED.
pytest.importorskip(
    "fitz",
    reason="PyMuPDF (`fitz`) is required for PDF fill fidelity tests. "
           "Install with: pip install pymupdf==1.24.11 (also in requirements.txt).",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_flat_pdf(text_per_page: list[str]) -> bytes:
    """Create a minimal multi-page flat PDF with known text strings."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    for text in text_per_page:
        c.setFont("Helvetica", 10)
        y = h - 80
        for line in text.split("\n"):
            c.drawString(50, y, line)
            y -= 20
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def flat_pdf_bytes() -> bytes:
    """Two-page flat PDF with German form-like text on both pages."""
    page1 = (
        "Name, Vorname\n"
        "Postanschrift\n"
        "Leistungen nach dem SGB II\n"
        "E Gemeinschaftliches Mittagessen\n"
        "Ort, Datum"
    )
    page2 = (
        "Kosten der Beförderung monatlich / vierteljährlich / jährlich\n"
        "Name des Essenanbieters\n"
        "in einer Schule oder einem Hort"
    )
    return make_flat_pdf([page1, page2])


@pytest.fixture
def acroform_pdf_bytes() -> bytes:
    """Minimal AcroForm PDF with one text field named 'Vorname'."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_annotation(
        page_number=0,
        annotation={
            "/Type": "/Annot",
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "Vorname",
            "/Rect": [50, 700, 300, 720],
        },
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ── Tests for pdf_token with template_id ─────────────────────────────────────

def test_template_id_round_trips_through_token(flat_pdf_bytes):
    """sign_pdf_token stores template_id; verify_pdf_token returns it."""
    from app.services.pdf_token import sign_pdf_token, verify_pdf_token

    token = sign_pdf_token(
        pdf_bytes=flat_pdf_bytes,
        field_ids=["name"],
        filename="test.pdf",
        secret_key="testsecret",
        template_id="jobcenter_but_v1",
    )
    data = verify_pdf_token(token, "testsecret")
    assert data["template_id"] == "jobcenter_but_v1"


def test_token_without_template_id_returns_none(flat_pdf_bytes):
    """Old tokens / AcroForm tokens return template_id=None."""
    from app.services.pdf_token import sign_pdf_token, verify_pdf_token

    token = sign_pdf_token(
        pdf_bytes=flat_pdf_bytes,
        field_ids=["name"],
        filename="test.pdf",
        secret_key="testsecret",
        # no template_id
    )
    data = verify_pdf_token(token, "testsecret")
    assert data["template_id"] is None


# ── Tests for fitz_overlay ────────────────────────────────────────────────────

def test_output_page_count_unchanged(flat_pdf_bytes):
    """Filled PDF must have the same number of pages as the original."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="name", field_type="text", source_page=1,
                  strategy="label_search", label_search="Name, Vorname",
                  offset_x=0, offset_y=12, font_size=9),
    ]
    out_bytes, _, _ = fill_with_fitz(flat_pdf_bytes, {"name": "Mamadou Bah"}, specs)

    original_doc = fitz.open(stream=flat_pdf_bytes, filetype="pdf")
    output_doc   = fitz.open(stream=out_bytes, filetype="pdf")
    assert len(output_doc) == len(original_doc)


def test_original_german_text_preserved(flat_pdf_bytes):
    """German labels must still be present in the output PDF."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    out_bytes, _, _ = fill_with_fitz(flat_pdf_bytes, {"name": "Test"}, [
        WriteSpec(field_id="name", field_type="text", source_page=1,
                  strategy="label_search", label_search="Name, Vorname",
                  offset_x=0, offset_y=12, font_size=9),
    ])
    doc = fitz.open(stream=out_bytes, filetype="pdf")
    page_text = doc[0].get_text()
    assert "Name, Vorname" in page_text


def test_text_answer_written_to_output(flat_pdf_bytes):
    """The user's answer must appear in the output PDF text."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="name", field_type="text", source_page=1,
                  strategy="label_search", label_search="Name, Vorname",
                  offset_x=0, offset_y=12, font_size=9),
    ]
    out_bytes, filled, _ = fill_with_fitz(flat_pdf_bytes, {"name": "Mamadou Bah"}, specs)

    doc = fitz.open(stream=out_bytes, filetype="pdf")
    text = doc[0].get_text()
    assert "Mamadou Bah" in text
    assert "name" in filled


def test_checkbox_true_creates_drawing(flat_pdf_bytes):
    """When answer is 'yes', a checkbox X drawing is added to the page."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="mittagessen", field_type="checkbox", source_page=1,
                  strategy="label_search",
                  label_search="E Gemeinschaftliches Mittagessen",
                  offset_x=-12, offset_y=-3, checkbox_size=4),
    ]
    out_bytes, filled, _ = fill_with_fitz(
        flat_pdf_bytes, {"mittagessen": "yes"}, specs
    )
    doc = fitz.open(stream=out_bytes, filetype="pdf")
    # After drawing an X, the page should have drawing paths
    drawings = doc[0].get_drawings()
    assert len(drawings) > 0, "Expected at least one drawing (X mark) on page"
    assert "mittagessen" in filled


def test_checkbox_false_leaves_no_mark(flat_pdf_bytes):
    """When answer is 'no', no X drawing is added for that checkbox."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="mittagessen", field_type="checkbox", source_page=1,
                  strategy="label_search",
                  label_search="E Gemeinschaftliches Mittagessen",
                  offset_x=-12, offset_y=-3, checkbox_size=4),
    ]
    out_bytes, filled, skipped = fill_with_fitz(
        flat_pdf_bytes, {"mittagessen": "no"}, specs
    )
    doc = fitz.open(stream=out_bytes, filetype="pdf")
    drawings = doc[0].get_drawings()
    assert len(drawings) == 0, "No drawing expected when checkbox is 'no'"
    assert "mittagessen" in skipped


def test_skip_strategy_not_fillable(flat_pdf_bytes):
    """strategy='skip' → field in skipped_ids, nothing written."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="signature", field_type="signature", source_page=1,
                  strategy="skip"),
    ]
    out_bytes, filled, skipped = fill_with_fitz(
        flat_pdf_bytes, {"signature": "signed"}, specs
    )
    assert "signature" in skipped
    assert "signature" not in filled


def test_label_not_found_is_skipped(flat_pdf_bytes):
    """If label_search text is absent from the PDF, field goes to skipped_ids."""
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="nonexistent", field_type="text", source_page=1,
                  strategy="label_search",
                  label_search="ZZZZZ_LABEL_THAT_DOES_NOT_EXIST",
                  offset_y=12),
    ]
    _, filled, skipped = fill_with_fitz(
        flat_pdf_bytes, {"nonexistent": "value"}, specs
    )
    assert "nonexistent" in skipped
    assert "nonexistent" not in filled


def test_page2_fields_written_to_correct_page(flat_pdf_bytes):
    """Fields on page 2 must be written to page 2, not page 1."""
    import fitz
    from app.services.pdf_generator.fitz_overlay import fill_with_fitz
    from app.services.form_templates import WriteSpec

    specs = [
        WriteSpec(field_id="essenanbieter", field_type="text", source_page=2,
                  strategy="label_search", label_search="Name des Essenanbieters",
                  offset_x=0, offset_y=12, font_size=9),
    ]
    out_bytes, filled, _ = fill_with_fitz(
        flat_pdf_bytes, {"essenanbieter": "Schulkantine GmbH"}, specs
    )
    doc = fitz.open(stream=out_bytes, filetype="pdf")
    page1_text = doc[0].get_text()
    page2_text = doc[1].get_text()
    assert "Schulkantine GmbH" not in page1_text
    assert "Schulkantine GmbH" in page2_text
    assert "essenanbieter" in filled


# ── Tests for template registry ───────────────────────────────────────────────

def test_find_template_by_id():
    """find_template_by_id returns the correct template."""
    from app.services.form_templates import find_template_by_id
    tmpl = find_template_by_id("jobcenter_but_v1")
    assert tmpl is not None
    assert tmpl.template_id == "jobcenter_but_v1"


def test_find_template_by_id_unknown():
    """find_template_by_id returns None for unknown IDs."""
    from app.services.form_templates import find_template_by_id
    assert find_template_by_id("does_not_exist") is None


def test_jobcenter_write_specs_cover_all_shown_fields():
    """Every non-signature field in get_field_map() must have a WriteSpec."""
    from app.services.form_templates.jobcenter_but import JobcenterButTemplate
    tmpl = JobcenterButTemplate()
    field_map   = tmpl.get_field_map()
    write_specs = tmpl.get_write_specs()
    spec_ids    = {s.field_id for s in write_specs}

    # All shown fields (confidence >= 0.70) must have a write spec
    for entry in field_map:
        assert entry.field_id in spec_ids, (
            f"Missing WriteSpec for field '{entry.field_id}' "
            f"(label: {entry.original_label})"
        )
