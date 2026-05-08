"""
Phase F1/F2 — radio_group mechanism for verified AcroForm templates.

The mechanism: a verified template can declare that one logical user-facing
radio question maps to N AcroForm widgets, where the chosen option's widget
gets set to "Yes" and every other widget in the group gets "Off". This
mirrors how official German PDFs (e.g. KG1 Familienstand, KG1 Bankverbindung)
typically lay out radio choices.

These tests lock down:

  - validate_template() rejects ill-formed radio_groups
  - validate_template() accepts well-formed radio_groups
  - /fill-pdf expands a logical radio answer into Yes/Off writes on the
    correct widgets
  - Unselected option → all widgets Off (no widget set to Yes)
  - Unknown option value → all widgets Off + warning log
  - Jobcenter behavior unchanged (no radio_groups → no expansion)

Run with:  pytest tests/test_radio_group_fill.py -v
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient


# ── Fixture: synthetic 3-option radio PDF + matching template ────────────────

# A unique phrase the template fingerprints on. Kept ASCII-only to avoid
# encoding pitfalls in the hand-rolled PDF.
_FINGERPRINT_PHRASE = "synthetic-radio-group-fixture"

# Logical field_id the user answers. Distinct from the widget names so the
# tests can verify the expansion happened.
_LOGICAL_FIELD_ID = "applicant_marital_status"

# Three /Btn widgets that constitute the radio group on the synthetic PDF.
_WIDGET_LEDIG       = "ms_ledig"
_WIDGET_VERHEIRATET = "ms_verheiratet"
_WIDGET_GESCHIEDEN  = "ms_geschieden"


def _radio_group_pdf() -> bytes:
    """
    Hand-roll a minimal AcroForm PDF whose extracted text contains the
    fingerprint phrase AND whose /AcroForm tree has the three /Btn widgets
    referenced by the synthetic template.
    """
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    content = (
        f"BT /F1 12 Tf 50 750 Td ({_FINGERPRINT_PHRASE} ledig verheiratet geschieden) Tj ET"
    ).encode("ascii")

    objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R /AcroForm 5 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 7 0 R /Annots [10 0 R 11 0 R 12 0 R] >>"
        ),
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        5: b"<< /Fields [10 0 R 11 0 R 12 0 R] /DR << >> >>",
        7: (
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
            + content + b"\nendstream"
        ),
        10: (
            b"<< /Type /Annot /Subtype /Widget /FT /Btn "
            b"/T (" + _WIDGET_LEDIG.encode() + b") /Rect [50 700 70 720] /P 3 0 R >>"
        ),
        11: (
            b"<< /Type /Annot /Subtype /Widget /FT /Btn "
            b"/T (" + _WIDGET_VERHEIRATET.encode() + b") /Rect [50 670 70 690] /P 3 0 R >>"
        ),
        12: (
            b"<< /Type /Annot /Subtype /Widget /FT /Btn "
            b"/T (" + _WIDGET_GESCHIEDEN.encode() + b") /Rect [50 640 70 660] /P 3 0 R >>"
        ),
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
            out.write(b"0000000000 65535 f \n")
    out.write(b"trailer\n")
    out.write(f"<< /Size {n_objs} /Root 1 0 R >>\n".encode())
    out.write(f"startxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


@pytest.fixture
def install_synthetic_radio_template():
    """
    Inject a synthetic verified-acroform template with a single radio_group
    into _TEMPLATES_CACHE, plus the matching VERIFIED_BY_FIELD_ID entry so
    the question pre-resolution loop tags it as source="verified".

    Restored after the test.
    """
    from app.services import form_templates
    from app.services.form_templates.jobcenter_but import JobcenterButTemplate
    from app.services.pdf_pipeline import FieldMapEntry
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID

    class _SyntheticRadioTemplate(form_templates.VerifiedTemplate):
        template_id = "synthetic_radio_v1"
        name = "Synthetic Radio-Group Test Template"
        fill_strategy = "acroform"

        def fingerprint(self, full_text: str) -> bool:
            return _FINGERPRINT_PHRASE in full_text.lower()

        def get_field_map(self):
            # The logical radio field. Real underlying widget names do NOT
            # appear here; they're hidden behind the radio_group expansion.
            return [
                FieldMapEntry(
                    field_id=_LOGICAL_FIELD_ID,
                    original_label="Familienstand",
                    field_type="radio",
                    source_page=1,
                    options=["ledig", "verheiratet", "geschieden"],
                    confidence=1.0,
                    source="verified_template",
                    source_text="Familienstand",
                ),
            ]

        def get_radio_groups(self):
            return [
                form_templates.RadioGroup(
                    field_id=_LOGICAL_FIELD_ID,
                    widget_names=[_WIDGET_LEDIG, _WIDGET_VERHEIRATET, _WIDGET_GESCHIEDEN],
                    options=[
                        ("ledig",       _WIDGET_LEDIG),
                        ("verheiratet", _WIDGET_VERHEIRATET),
                        ("geschieden",  _WIDGET_GESCHIEDEN),
                    ],
                ),
            ]

    original_cache = form_templates._TEMPLATES_CACHE
    form_templates._TEMPLATES_CACHE = [JobcenterButTemplate(), _SyntheticRadioTemplate()]
    original_entry = VERIFIED_BY_FIELD_ID.get(_LOGICAL_FIELD_ID)
    VERIFIED_BY_FIELD_ID[_LOGICAL_FIELD_ID] = {
        "en": {"question": "What is your marital status?", "help": ""},
        "de": {"question": "Wie ist Ihr Familienstand?", "help": ""},
    }

    yield _SyntheticRadioTemplate

    form_templates._TEMPLATES_CACHE = original_cache
    if original_entry is None:
        VERIFIED_BY_FIELD_ID.pop(_LOGICAL_FIELD_ID, None)
    else:
        VERIFIED_BY_FIELD_ID[_LOGICAL_FIELD_ID] = original_entry


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _post_process(client, pdf_bytes: bytes) -> dict:
    resp = client.post(
        "/api/v1/process-pdf?user_language=en",
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fill(client, token: str, answers: dict):
    return client.post(
        "/api/v1/fill-pdf",
        json={"pdf_token": token, "answers": answers, "field_labels": {}},
    )


# ── 1. validate_template() — radio_group invariants ──────────────────────────

class TestValidateRadioGroup:
    """
    Direct unit tests of the validator. Each test builds a tiny VerifiedTemplate
    subclass that violates ONE invariant and asserts the error fires.
    """

    def _entry_factory(self, *, field_type="radio"):
        from app.services.pdf_pipeline import FieldMapEntry
        return FieldMapEntry(
            field_id="ms",
            original_label="Familienstand",
            field_type=field_type,
            source_page=1,
            options=["a", "b"],
            confidence=1.0,
            source="verified_template",
            source_text="Familienstand",
        )

    def _make_tmpl(self, *, fmap, rgroups):
        from app.services import form_templates

        class _T(form_templates.VerifiedTemplate):
            template_id = "_validate_test"
            name = "test"
            fill_strategy = "acroform"
            def fingerprint(self, t): return False
            def get_field_map(self): return fmap
            def get_radio_groups(self): return rgroups
        return _T()

    def test_radio_group_field_must_exist_in_field_map(self):
        from app.services.form_templates import RadioGroup, validate_template
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        VERIFIED_BY_FIELD_ID["ms"] = {"en": {"question": "?"}, "de": {"question": "?"}}
        try:
            t = self._make_tmpl(
                fmap=[self._entry_factory()],
                rgroups=[RadioGroup(
                    field_id="not_in_map",
                    widget_names=["w1", "w2"],
                    options=[("a", "w1"), ("b", "w2")],
                )],
            )
            errors = validate_template(t)
            assert any("RADIO_GROUP_MISSING_FIELD" in e for e in errors), errors
        finally:
            VERIFIED_BY_FIELD_ID.pop("ms", None)

    def test_radio_group_field_must_be_type_radio(self):
        from app.services.form_templates import RadioGroup, validate_template
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        VERIFIED_BY_FIELD_ID["ms"] = {"en": {"question": "?"}, "de": {"question": "?"}}
        try:
            t = self._make_tmpl(
                fmap=[self._entry_factory(field_type="text")],  # WRONG type
                rgroups=[RadioGroup(
                    field_id="ms",
                    widget_names=["w1", "w2"],
                    options=[("a", "w1"), ("b", "w2")],
                )],
            )
            errors = validate_template(t)
            assert any("RADIO_GROUP_WRONG_TYPE" in e for e in errors), errors
        finally:
            VERIFIED_BY_FIELD_ID.pop("ms", None)

    def test_option_widget_must_be_in_widget_names(self):
        from app.services.form_templates import RadioGroup, validate_template
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        VERIFIED_BY_FIELD_ID["ms"] = {"en": {"question": "?"}, "de": {"question": "?"}}
        try:
            t = self._make_tmpl(
                fmap=[self._entry_factory()],
                rgroups=[RadioGroup(
                    field_id="ms",
                    widget_names=["w1"],
                    options=[("a", "w1"), ("b", "w_missing")],
                )],
            )
            errors = validate_template(t)
            assert any("RADIO_GROUP_OPTION_WIDGET_MISSING" in e for e in errors), errors
        finally:
            VERIFIED_BY_FIELD_ID.pop("ms", None)

    def test_widget_names_must_be_unique_across_groups(self):
        from app.services.form_templates import RadioGroup, validate_template
        from app.services.pdf_pipeline import FieldMapEntry
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        for fid in ("ms", "bank"):
            VERIFIED_BY_FIELD_ID[fid] = {"en": {"question": "?"}, "de": {"question": "?"}}
        try:
            t = self._make_tmpl(
                fmap=[
                    FieldMapEntry(
                        field_id="ms", original_label="Familienstand",
                        field_type="radio", source_page=1, options=["a"],
                        confidence=1.0, source="verified_template",
                        source_text="Familienstand",
                    ),
                    FieldMapEntry(
                        field_id="bank", original_label="Bank",
                        field_type="radio", source_page=1, options=["a"],
                        confidence=1.0, source="verified_template",
                        source_text="Bank",
                    ),
                ],
                rgroups=[
                    RadioGroup(field_id="ms",   widget_names=["shared_w"],
                               options=[("a", "shared_w")]),
                    RadioGroup(field_id="bank", widget_names=["shared_w"],
                               options=[("a", "shared_w")]),
                ],
            )
            errors = validate_template(t)
            assert any("RADIO_GROUP_DUPLICATE_WIDGET" in e for e in errors), errors
        finally:
            for fid in ("ms", "bank"):
                VERIFIED_BY_FIELD_ID.pop(fid, None)

    def test_well_formed_radio_group_passes(self):
        from app.services.form_templates import RadioGroup, validate_template
        from app.services.verified_questions import VERIFIED_BY_FIELD_ID
        VERIFIED_BY_FIELD_ID["ms"] = {"en": {"question": "?"}, "de": {"question": "?"}}
        try:
            t = self._make_tmpl(
                fmap=[self._entry_factory()],
                rgroups=[RadioGroup(
                    field_id="ms",
                    widget_names=["w1", "w2", "w3"],
                    options=[("a", "w1"), ("b", "w2"), ("c", "w3")],
                )],
            )
            errors = validate_template(t)
            radio_errors = [e for e in errors if "RADIO_GROUP" in e]
            assert radio_errors == [], radio_errors
        finally:
            VERIFIED_BY_FIELD_ID.pop("ms", None)


# ── 2. End-to-end: fill_pdf expands radio_group answers ──────────────────────

class TestRadioGroupFillExpansion:
    """
    Drive the synthetic PDF + template through /process-pdf → /fill-pdf and
    assert that a single logical answer turns into the right Yes/Off pattern
    on the underlying widgets.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, install_synthetic_radio_template, client):
        self.client = client
        body = _post_process(client, _radio_group_pdf())
        self.body = body
        self.token = body["pdf_token"]

    def test_fingerprint_routed_to_synthetic_template(self):
        assert self.body["analysis_report"]["template_id"] == "synthetic_radio_v1"
        assert self.body["analysis_report"]["support_level"] == 1
        assert self.body["analysis_report"]["fill_strategy"] == "acroform"

    def test_logical_field_id_in_extracted_field_ids(self):
        # The user-facing logical field MUST be in extracted_field_ids so the
        # grounding guard accepts it. Underlying widget names MUST NOT be.
        ids = set(self.body["extracted_field_ids"])
        assert _LOGICAL_FIELD_ID in ids
        assert _WIDGET_LEDIG       not in ids
        assert _WIDGET_VERHEIRATET not in ids
        assert _WIDGET_GESCHIEDEN  not in ids

    def test_chosen_option_writes_yes_to_correct_widget(self):
        resp = _fill(self.client, self.token, {_LOGICAL_FIELD_ID: "verheiratet"})
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("X-Fill-Strategy") == "acroform"

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(resp.content))
        fields = reader.get_fields() or {}

        def _value(widget_name):
            entry = next(
                (v for k, v in fields.items() if k.lstrip("/") == widget_name),
                None,
            )
            assert entry is not None, f"{widget_name} not found in output: {list(fields)}"
            return str(entry.get("/V", "")).lstrip("/")

        # The chosen widget must carry "Yes"; siblings must carry "Off".
        assert _value(_WIDGET_VERHEIRATET).lower() == "yes"
        assert _value(_WIDGET_LEDIG).lower()       == "off"
        assert _value(_WIDGET_GESCHIEDEN).lower()  == "off"

    def test_unknown_option_value_writes_all_off(self, caplog):
        # If the user submits a value that doesn't match any option (e.g. a
        # client-side bug), every widget must end up "Off" — never silently
        # marked Yes on an arbitrary widget.
        import logging
        with caplog.at_level(logging.WARNING, logger="burokratie.fill_pdf"):
            resp = _fill(self.client, self.token, {_LOGICAL_FIELD_ID: "bizarre_value"})
        assert resp.status_code == 200

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(resp.content))
        fields = reader.get_fields() or {}
        for widget in (_WIDGET_LEDIG, _WIDGET_VERHEIRATET, _WIDGET_GESCHIEDEN):
            entry = next(v for k, v in fields.items() if k.lstrip("/") == widget)
            assert str(entry.get("/V", "")).lstrip("/").lower() == "off", (
                f"{widget} should be Off when the answer matches no option"
            )
        # And the warning log must mention the violation by template + value.
        assert any(
            "RADIO_GROUP_VALUE_NOT_IN_OPTIONS" in r.message
            and "bizarre_value" in r.message
            for r in caplog.records
        )

    def test_grounding_guard_still_rejects_unknown_logical_field(self):
        # The grounding guard sits BEFORE radio expansion. A widget name from
        # the synthetic radio group is NOT in extracted_field_ids; sending it
        # as an answer key must still 400.
        resp = _fill(self.client, self.token, {_WIDGET_LEDIG: "Yes"})
        assert resp.status_code == 400


# ── 3. Jobcenter regression — no radio_groups, no expansion ──────────────────

class TestJobcenterUntouchedByRadioGroupCode:
    """
    Phase F1 must not change Jobcenter behavior. Jobcenter has fill_strategy
    = "fitz_overlay" so it never reaches the verified-acroform branch where
    radio_group expansion lives — but we double-check anyway by asserting
    the template returns the empty-list default for radio_groups.
    """

    def test_jobcenter_template_returns_empty_radio_groups(self):
        from app.services.form_templates.jobcenter_but import JobcenterButTemplate
        t = JobcenterButTemplate()
        assert t.get_radio_groups() == []

    def test_jobcenter_template_passes_validation_after_F1(self):
        from app.services.form_templates import validate_template
        from app.services.form_templates.jobcenter_but import JobcenterButTemplate
        errors = validate_template(JobcenterButTemplate())
        assert errors == [], errors


# ── 4. Defensive: get_radio_groups() default is empty ────────────────────────

class TestRadioGroupDefault:
    def test_base_class_default_is_empty_list(self):
        from app.services.form_templates import VerifiedTemplate

        class _NoRadios(VerifiedTemplate):
            template_id = "nope"
            name = "nope"
            def fingerprint(self, t): return False
            def get_field_map(self): return []
        assert _NoRadios().get_radio_groups() == []
