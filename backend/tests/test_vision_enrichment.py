"""Vision-LLM AcroForm enrichment (Level 2) — Gemini call mocked."""
import io
import re

import pytest

from app.services.pdf_pipeline import extract_acroform_fields
from app.services.vision import gemini_form_vision as gv


def _pdf_with(text_names, checkbox_names):
    """1-page AcroForm: some text fields + some checkboxes (creation order)."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 810, "Form")  # ensure page content exists before AcroForm fields
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


def _fake_call(png, boxlist, api_key):
    """Mock Gemini: read the box type list and label/group by type.
    text → labelled 'Familienname'; checkbox → grouped under 'Geschlecht'."""
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
def _clear_cache(monkeypatch):
    gv._CACHE.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    yield
    gv._CACHE.clear()


def test_labels_and_group_recovered(monkeypatch):
    monkeypatch.setattr(gv, "_call_gemini", _fake_call)
    pdf = _pdf_with(["Textfield"], ["chk0", "chk1", "chk2"])
    fields = extract_acroform_fields(pdf)
    enr = gv.enrich_acroform(fields, pdf)

    assert enr.used
    # the lone text field got a real label
    text_id = next(f.field_id for f in fields if f.field_type == "text")
    assert enr.labels.get(text_id) == "Familienname"
    # the 3 checkboxes collapsed into ONE radio group with 3 options
    assert len(enr.groups) == 1
    grp = enr.groups[0]
    assert grp.question == "Geschlecht"
    assert len(grp.options) == 3
    chk_ids = {f.field_id for f in fields if f.field_type == "checkbox"}
    assert enr.member_widgets == chk_ids
    # every option maps to a real checkbox widget (grounding)
    assert {w for (_v, w, _on) in grp.options} == chk_ids


def test_invented_index_is_dropped(monkeypatch):
    # Model references a box that doesn't exist → must be ignored.
    def bad_call(png, boxlist, api_key):
        return [
            {"index": 0, "question": "Familienname", "checkbox_group": None},
            {"index": 999, "question": "Erfundenes Feld", "checkbox_group": None},
        ]
    monkeypatch.setattr(gv, "_call_gemini", bad_call)
    pdf = _pdf_with(["Textfield"], [])
    fields = extract_acroform_fields(pdf)
    enr = gv.enrich_acroform(fields, pdf)
    assert len(enr.labels) == 1            # only the real box
    assert "Erfundenes Feld" not in enr.labels.values()


def test_no_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(gv, "_call_gemini", _fake_call)
    pdf = _pdf_with(["Textfield"], ["chk0"])
    fields = extract_acroform_fields(pdf)
    enr = gv.enrich_acroform(fields, pdf)
    assert enr.used is False
    assert enr.labels == {} and enr.groups == []


def test_call_failure_falls_back_to_empty(monkeypatch):
    def boom(png, boxlist, api_key):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(gv, "_call_gemini", boom)
    pdf = _pdf_with(["Textfield"], ["chk0", "chk1"])
    fields = extract_acroform_fields(pdf)
    enr = gv.enrich_acroform(fields, pdf)
    # per-page failure → no labels/groups, no exception
    assert enr.used is False


def test_group_fill_round_trip(monkeypatch):
    """End-to-end: a vision group answer ticks the chosen checkbox via /fill-pdf."""
    from fastapi.testclient import TestClient
    from pypdf import PdfReader
    from app.main import app
    from app.config import settings
    from app.services.pdf_token import sign_pdf_token

    pdf = _pdf_with([], ["chk0", "chk1", "chk2"])
    fields = extract_acroform_fields(pdf)
    chk = [f.field_id for f in fields if f.field_type == "checkbox"]
    group = {
        "field_id": "vis_grp_1",
        "options": [
            {"value": "männlich", "widget": chk[0], "on": "Yes"},
            {"value": "weiblich", "widget": chk[1], "on": "Yes"},
            {"value": "divers",   "widget": chk[2], "on": "Yes"},
        ],
    }
    token = sign_pdf_token(
        pdf_bytes=pdf, field_ids=["vis_grp_1"], filename="f.pdf",
        secret_key=settings.secret_key, template_id=None, support_level=2,
        vision_groups=[group],
    )
    client = TestClient(app)
    resp = client.post("/api/v1/fill-pdf",
                       json={"pdf_token": token, "answers": {"vis_grp_1": "weiblich"}, "field_labels": {}})
    assert resp.status_code == 200
    rb = {k: v.get("/V") for k, v in (PdfReader(io.BytesIO(resp.content)).get_fields() or {}).items()}
    assert str(rb.get(chk[1])).lstrip("/").lower() == "yes"     # chosen
    assert str(rb.get(chk[0])).lstrip("/").lower() == "off"     # sibling
    assert str(rb.get(chk[2])).lstrip("/").lower() == "off"     # sibling
