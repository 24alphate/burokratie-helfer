"""Stage 4C — Claude Vision scan extraction: pure-logic + key-gate tests.

These never hit the network: they exercise the JSON→FieldMapEntry conversion and
the no-key short-circuit. The API call itself is a thin wrapper around these.
"""
from app.services.ocr import claude_scan
from app.services.ocr.claude_scan import _fields_from_payload, SCAN_CONF


def test_payload_basic_types_and_grounding():
    data = {"fields": [
        {"label": "Vorname", "type": "text", "options": [], "page": 1},
        {"label": "Geburtsdatum", "type": "date", "page": 1},
        {"label": "Familienstand", "type": "radio", "options": ["ledig", "verheiratet"], "page": 2},
    ]}
    fields = _fields_from_payload(data)
    assert [f.field_id for f in fields] == ["vorname", "geburtsdatum", "familienstand"]

    by_id = {f.field_id: f for f in fields}
    assert by_id["geburtsdatum"].field_type == "date"
    assert by_id["geburtsdatum"].source_page == 1
    fam = by_id["familienstand"]
    assert fam.field_type == "radio"
    assert fam.options == ["ledig", "verheiratet"]
    assert fam.source_page == 2

    # Provenance / grounding contract for every emitted field.
    for f in fields:
        assert f.source == "ocr"
        assert f.source_text == f.original_label   # grounded in what Claude read
        assert f.confidence == SCAN_CONF
        assert f.reason == "pdf_field"


def test_payload_invalid_type_coerced_to_text():
    fields = _fields_from_payload({"fields": [{"label": "Mystery", "type": "wizardry"}]})
    assert len(fields) == 1
    assert fields[0].field_type == "text"


def test_payload_drops_short_and_empty_labels_and_dedupes():
    data = {"fields": [
        {"label": "x"},          # too short
        {"label": "Vorname"},
        {"label": "vorname"},    # duplicate id
        {"label": ""},           # empty
    ]}
    fields = _fields_from_payload(data)
    assert [f.field_id for f in fields] == ["vorname"]


def test_payload_tolerates_bad_shapes():
    assert _fields_from_payload({}) == []
    assert _fields_from_payload({"fields": "nope"}) == []
    got = _fields_from_payload({"fields": [None, 5, {"label": "Ort", "options": "nope", "page": "x"}]})
    assert len(got) == 1
    assert got[0].field_id == "ort"
    assert got[0].options == []       # non-list options -> []
    assert got[0].source_page == 1    # non-int page -> 1


def test_no_key_returns_empty(monkeypatch):
    import app.services.question_translator as qt
    monkeypatch.setattr(qt, "_resolve_anthropic_key", lambda: "")
    # No key -> no render, no API call, just [].
    assert claude_scan.extract_fields_from_scan(b"%PDF-1.4 not-a-real-pdf") == []


def _scanned_like_pdf() -> bytes:
    """A no-text PDF → detect_pdf_type returns 'scanned' (Level 4)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f\r\n0000000009 00000 n\r\n"
        b"0000000068 00000 n\r\n0000000125 00000 n\r\n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n200\n%%EOF"
    )


def test_scanned_pdf_promoted_to_level3_via_claude(monkeypatch):
    """
    End-to-end wiring: with a key configured and Claude returning fields, a
    scanned (Level 4) PDF is promoted to Level 3 and its fields flow through the
    grounding guard. No network: the API call is mocked and both labels resolve
    from the deterministic table, so translate_fields is never reached.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.v1.process_pdf as endpoint
    from app.services.ocr import claude_scan as cs
    from app.services.pdf_pipeline import FieldMapEntry

    monkeypatch.setattr(endpoint, "anthropic_key_configured", lambda: True)
    fake = [
        FieldMapEntry(field_id="vorname", original_label="Vorname", field_type="text",
                      source_page=1, confidence=0.72, source="ocr",
                      source_text="Vorname", reason="pdf_field"),
        FieldMapEntry(field_id="familienstand", original_label="Familienstand",
                      field_type="radio", source_page=1, options=["ledig", "verheiratet"],
                      confidence=0.72, source="ocr", source_text="Familienstand",
                      reason="pdf_field"),
    ]
    monkeypatch.setattr(cs, "extract_fields_from_scan", lambda _b: fake)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/process-pdf?user_language=en",
        files={"file": ("scan.pdf", _scanned_like_pdf(), "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    report = body["analysis_report"]

    assert report["support_level"] == 3
    assert report["extraction_source"] == "ocr"
    ids = body["extracted_field_ids"]
    assert "vorname" in ids and "familienstand" in ids
    # Grounding: every shown question key is in the scanned field map.
    for f in body["fields"]:
        assert f["key"] in ids
    # The vision diagnostic is attached so the UI shows the "verify" banner.
    assert report["ocr_diagnostic"]["provider"] == "claude-vision"
    # radio field kept its options through the pipeline.
    fam = next(f for f in body["fields"] if f["key"] == "familienstand")
    assert [o["value"] for o in fam["options"]] == ["ledig", "verheiratet"]
    assert fam["input_type"] == "radio"
