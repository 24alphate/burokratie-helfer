"""Claude vision AcroForm enrichment (Level 2) — Claude call mocked.

Mirrors test_vision_enrichment.py (the Gemini backend); both share the same
engine + output contract, so the assertions are identical aside from the
provider-specific key gate.
"""
import io
import re

import pytest

from app.services.pdf_pipeline import extract_acroform_fields
from app.services.vision import claude_form_vision as cv
import app.services.question_translator as qt


def _pdf_with(text_names, checkbox_names):
    """1-page AcroForm: some text fields + some checkboxes (creation order)."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 810, "Form")
    y = 760
    for name in text_names:
        c.drawString(72, y + 16, name)
        c.acroForm.textfield(name=name, x=72, y=y, width=180, height=14, borderWidth=0)
        y -= 40
    for name in checkbox_names:
        c.acroForm.checkbox(name=name, x=72, y=y, size=12)
        y -= 24
    c.save()
    return buf.getvalue()


def _fake_call(png, boxlist, key):
    """Mock Claude: text -> 'Familienname'; checkbox -> grouped under 'Geschlecht'."""
    out = []
    for line in boxlist.splitlines():
        m = re.search(r"box (\d+): type=(\w+)", line)
        if not m:
            continue
        idx, t = int(m.group(1)), m.group(2)
        if t == "checkbox":
            out.append({"index": idx, "question": "Geschlecht",
                        "checkbox_group": "g", "option_label": f"opt{idx}"})
        else:
            out.append({"index": idx, "question": "Familienname",
                        "checkbox_group": None, "option_label": None})
    return out


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    cv._CACHE.clear()
    # A usable key so enrich_acroform proceeds (overrides the offline fixture).
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "sk-ant-fake")
    yield
    cv._CACHE.clear()


def test_labels_and_group_recovered(monkeypatch):
    monkeypatch.setattr(cv, "_call_claude", _fake_call)
    pdf = _pdf_with(["Textfield"], ["chk0", "chk1", "chk2"])
    fields = extract_acroform_fields(pdf)
    enr = cv.enrich_acroform(fields, pdf)

    assert enr.used
    text_id = next(f.field_id for f in fields if f.field_type == "text")
    assert enr.labels.get(text_id) == "Familienname"
    assert len(enr.groups) == 1
    grp = enr.groups[0]
    assert grp.question == "Geschlecht"
    assert len(grp.options) == 3
    chk_ids = {f.field_id for f in fields if f.field_type == "checkbox"}
    assert enr.member_widgets == chk_ids
    assert {w for (_v, w, _on) in grp.options} == chk_ids


def test_invented_index_is_dropped(monkeypatch):
    def bad_call(png, boxlist, key):
        return [
            {"index": 0, "question": "Familienname", "checkbox_group": None},
            {"index": 999, "question": "Erfundenes Feld", "checkbox_group": None},
        ]
    monkeypatch.setattr(cv, "_call_claude", bad_call)
    pdf = _pdf_with(["Textfield"], [])
    fields = extract_acroform_fields(pdf)
    enr = cv.enrich_acroform(fields, pdf)
    assert len(enr.labels) == 1
    assert "Erfundenes Feld" not in enr.labels.values()


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "")
    monkeypatch.setattr(cv, "_call_claude", _fake_call)
    pdf = _pdf_with(["Textfield"], ["chk0"])
    fields = extract_acroform_fields(pdf)
    enr = cv.enrich_acroform(fields, pdf)
    assert enr.used is False
    assert enr.labels == {} and enr.groups == []


def test_call_failure_falls_back_to_empty(monkeypatch):
    def boom(png, boxlist, key):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(cv, "_call_claude", boom)
    pdf = _pdf_with(["Textfield"], ["chk0", "chk1"])
    fields = extract_acroform_fields(pdf)
    enr = cv.enrich_acroform(fields, pdf)
    assert enr.used is False
