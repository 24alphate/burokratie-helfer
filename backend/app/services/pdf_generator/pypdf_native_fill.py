"""
PyPDF-based fill engine for "born-AcroForm" PDFs with custom button export
values and native radio groups.

Why this exists alongside fitz_acroform_fill:

  - fitz_acroform_fill (PyMuPDF) is needed for XFA-styled PDFs whose /Btn
    widgets are stubs without /AP appearance streams (KG1, KiZ). There, fitz
    synthesizes the checked appearance and only accepts True/"Yes".

  - This module is for the opposite case: real born-AcroForm PDFs (e.g. the
    Jobcenter Bürgergeld Hauptantrag) whose /Btn widgets DO have /AP streams
    with CUSTOM export values — checkboxes export "selektiert" (not "Yes"),
    and radios are native single fields with export values like "0"/"1".
    fitz mis-handles both (writes an invalid /Yes for "selektiert", and
    ignores the radio export). PyPDF writes the real export values correctly.

Contract (mirrors fitz_acroform_fill.fill_acroform_via_fitz):
    fill_native_acroform_via_pypdf(pdf_bytes, answers) -> FillResult

Behaviour per field:
    checkbox  truthy answer  → the widget's REAL on-state (read from /_States_,
                               e.g. "selektiert"); falsy/"Off"/empty → "Off".
    radio     non-empty      → the raw answer written as the export value
                               ("0"/"1"); the writer selects the matching kid.
    text      → written verbatim.

The strict-policy hooks (zero-fill refusal etc.) live in fill_pdf.py; this
module performs the writes and reports the count.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

log = logging.getLogger("burokratie.pypdf_native_fill")

_TRUTHY = {"yes", "ja", "true", "1", "x", "on", "selektiert", "checked"}

# AcroForm field-flag bits
_FF_RADIO      = 1 << 15
_FF_PUSHBUTTON = 1 << 16


@dataclass
class FillResult:
    pdf_bytes: bytes
    field_count_filled: int
    warnings: list[str]
    # "acroform" on the public surface — from the outside this is identical to
    # the other AcroForm fill paths (writes into the original PDF's widgets).
    strategy: str = "acroform"


def _widget_on_state(widget) -> str | None:
    """The non-Off /AP/N appearance key of a /Btn widget (its export value)."""
    ap = widget.get("/AP")
    if ap is None:
        return None
    ap = ap.get_object() if hasattr(ap, "get_object") else ap
    n = ap.get("/N")
    if n is None:
        return None
    n = n.get_object() if hasattr(n, "get_object") else n
    for k in (n.keys() if hasattr(n, "keys") else []):
        v = str(k).lstrip("/")
        if v.lower() != "off":
            return v
    return None


def _fix_button_appearance_states(writer, btn_vals: dict[str, str], warnings: list) -> None:
    """Set every /Btn widget's /AS to match the field's target value.

    For each widget whose field is in btn_vals: if the widget's own on-state
    equals the target value → /AS = that on-state (selected); else /AS = /Off.
    Handles checkboxes (terminal widget, on-state e.g. 'selektiert') and native
    radio kids (each kid on-state e.g. '0'/'1') uniformly.
    """
    from pypdf.generic import NameObject

    def widget_field_name(w):
        # Terminal widget carries /T; a radio kid inherits the name from /Parent.
        t = w.get("/T")
        if t is not None:
            return str(t).lstrip("/").strip()
        parent = w.get("/Parent")
        if parent is not None:
            parent = parent.get_object()
            pt = parent.get("/T")
            if pt is not None:
                return str(pt).lstrip("/").strip()
        return None

    for page in writer.pages:
        annots = page.get("/Annots")
        if annots is None:
            continue
        for ref in annots.get_object():
            try:
                w = ref.get_object()
                if str(w.get("/Subtype", "")) != "/Widget":
                    continue
                name = widget_field_name(w)
                if name is None or name not in btn_vals:
                    continue
                on = _widget_on_state(w)
                if on is None:
                    continue
                target = str(btn_vals[name])
                w[NameObject("/AS")] = NameObject(
                    "/" + on if on == target else "/Off"
                )
            except Exception as e:
                warnings.append(f"AS fixup warning: {e}")


def _checkbox_on_state(field_obj) -> str:
    """Real on-state export for a checkbox, read from pypdf's /_States_
    (e.g. ['/Off', '/selektiert'] → 'selektiert'). Falls back to 'Yes'."""
    states = field_obj.get("/_States_")
    if states:
        for s in states:
            v = str(s).lstrip("/")
            if v.lower() != "off":
                return v
    return "Yes"


def fill_native_acroform_via_pypdf(pdf_bytes: bytes, answers: dict[str, str]) -> FillResult:
    from pypdf import PdfReader, PdfWriter

    warnings: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        fields = reader.get_fields() or {}
    except Exception as e:
        log.error("pypdf_native_fill: failed to read PDF: %s", e)
        raise

    # Classify every /Btn field as radio or checkbox, and record the
    # checkbox on-state. Text/choice fields are everything else.
    radio_fields: set[str] = set()
    checkbox_on: dict[str, str] = {}
    for name, f in fields.items():
        clean = str(name).lstrip("/").strip()
        ft = str(f.get("/FT", ""))
        try:
            ff = int(str(f.get("/Ff", "0") or "0").split(".")[0])
        except (ValueError, TypeError):
            ff = 0
        if ft == "/Btn" and not (ff & _FF_PUSHBUTTON):
            if ff & _FF_RADIO:
                radio_fields.add(clean)
            else:
                checkbox_on[clean] = _checkbox_on_state(f)

    # Build the value maps. Buttons (radio + checkbox) and text are written in
    # separate passes — pypdf is happier updating like-typed fields together.
    text_vals: dict[str, str] = {}
    btn_vals: dict[str, str] = {}
    for key, raw in answers.items():
        k = str(key).lstrip("/").strip()
        if k in radio_fields:
            v = str(raw).strip()
            if v:
                btn_vals[k] = v               # native export value, e.g. "0"/"1"
        elif k in checkbox_on:
            truthy = str(raw).strip().lower() in _TRUTHY
            btn_vals[k] = checkbox_on[k] if truthy else "Off"
        else:
            text_vals[k] = str(raw)

    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        try:
            if text_vals:
                writer.update_page_form_field_values(page, text_vals, auto_regenerate=False)
            if btn_vals:
                writer.update_page_form_field_values(page, btn_vals, auto_regenerate=False)
        except Exception as e:
            warnings.append(f"page field update warning: {e}")

    # ── Appearance-state (/AS) fixup ─────────────────────────────────────────
    # pypdf's update_page_form_field_values sets the field /V but does NOT
    # reliably update each /Btn WIDGET's /AS for custom export values. Adobe
    # and many viewers render the box from /AS, not /V — so without this a
    # checked box/radio would still display empty. We walk every /Btn widget
    # and set /AS = its own on-state when the field's target value selects it,
    # else /Off. This is what makes the filled PDF actually look filled.
    _fix_button_appearance_states(writer, btn_vals, warnings)

    writer.add_metadata({"/Producer": "Bürokratie-Helfer"})

    # field_count_filled = text fields written + buttons set to a non-Off value.
    filled = len(text_vals) + sum(1 for v in btn_vals.values() if str(v).lower() != "off")

    out = io.BytesIO()
    writer.write(out)
    return FillResult(
        pdf_bytes=out.getvalue(),
        field_count_filled=filled,
        warnings=warnings,
    )
