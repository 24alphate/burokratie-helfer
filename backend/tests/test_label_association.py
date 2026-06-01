"""Level-2 positional label association (recover labels for generic widgets)."""
import io

import pytest

from app.services.pdf_pipeline import (
    _is_weak_label,
    _associate_labels_by_position,
    extract_acroform_fields,
)


def _build_pdf(fields):
    """Build a 1-page AcroForm PDF. `fields` = list of (name, x, y, w, h).
    Also draws a text label per spec via the `labels` closure below."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for draw in fields:
        draw(c)
    c.save()
    return buf.getvalue()


def _label(text, x, y):
    return lambda c: c.drawString(x, y, text)


def _textfield(name, x, y, w=200, h=14):
    return lambda c: c.acroForm.textfield(name=name, x=x, y=y, width=w, height=h, borderWidth=0)


# ── _is_weak_label ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("label", ["Textfield", "Textfield-0", "Textfield-12", "Text Field 3",
                                   "Checkbox", "checkbox-2", "Feld", "", "  ", "12", "..--"])
def test_weak_labels(label):
    assert _is_weak_label(label) is True


@pytest.mark.parametrize("label", ["Familienname", "Vorname(n)", "Geburtsdatum", "IBAN",
                                   "Wohnort (PLZ, Ort)", "männlich"])
def test_strong_labels(label):
    assert _is_weak_label(label) is False


# ── positional association ────────────────────────────────────────────────────

def test_label_above_is_recovered():
    pdf = _build_pdf([
        _label("Familienname", 72, 760),
        _textfield("Textfield", 72, 742, w=200, h=14),
    ])
    fields = extract_acroform_fields(pdf)
    target = next(f for f in fields if f.field_id == "Textfield")
    assert _is_weak_label(target.original_label)  # before
    _associate_labels_by_position(fields, pdf)
    assert "Familienname" in target.original_label
    assert target.field_id == "Textfield"  # id never changes


def test_label_left_is_recovered():
    pdf = _build_pdf([
        _label("Telefon", 72, 700),
        _textfield("Textfield-1", 140, 698, w=200, h=12),
    ])
    fields = extract_acroform_fields(pdf)
    target = next(f for f in fields if f.field_id == "Textfield-1")
    _associate_labels_by_position(fields, pdf)
    assert "Telefon" in target.original_label


def test_far_away_label_not_matched():
    # Label is ~300pt above the box — beyond the cap; must stay weak.
    pdf = _build_pdf([
        _label("Familienname", 72, 780),
        _textfield("Textfield", 72, 400, w=200, h=14),
    ])
    fields = extract_acroform_fields(pdf)
    target = next(f for f in fields if f.field_id == "Textfield")
    _associate_labels_by_position(fields, pdf)
    assert _is_weak_label(target.original_label)


def test_good_label_untouched():
    # A widget whose own name is meaningful must not be overwritten.
    pdf = _build_pdf([
        _label("SomethingElse", 72, 760),
        _textfield("Familienname", 72, 742, w=200, h=14),
    ])
    fields = extract_acroform_fields(pdf)
    target = next(f for f in fields if f.field_id == "Familienname")
    before = target.original_label
    _associate_labels_by_position(fields, pdf)
    assert target.original_label == before
