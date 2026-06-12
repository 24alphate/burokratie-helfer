"""
Phase F6 — fitz-based AcroForm fill engine.

Why this exists: PyPDFGenerator's _fill_acroform path uses PyPDF, which
relies on /AP/N (appearance streams) and standard /V values to write into
form widgets. That works for "born-acroform" PDFs (e.g. Jobcenter forms,
test fixtures we hand-roll). It does NOT work for XFA-styled PDFs whose
visual representation is managed by an XFA stream and whose AcroForm
/Btn widgets are bare stubs with no /AP, no /Kids, and no /V.

Familienkasse KG1 is the canonical example: 95 leaf widgets, all Familienstand
and Bankverbindung radio buttons are /Btn with no /AP — PyPDF "writes 0
fields" no matter what answers you pass.

PyMuPDF (fitz) walks the page-level annotation tree, finds widgets with
their on_state values, and can write /V directly via Widget.update().
That works for both born-acroform PDFs AND XFA-stub PDFs.

Public surface:
    fill_acroform_via_fitz(pdf_bytes, answers) -> FillResult

The strict-policy hooks live in fill_pdf.py; this module just performs
the writes and reports the count.

Fields not touched (no answer in `answers`) stay blank — this is what
makes manual widgets (confidence=0.5) work correctly: the engine writes
nothing to them, and they show empty in Adobe / any PDF reader.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass


log = logging.getLogger("burokratie.fitz_acroform_fill")


@dataclass
class FillResult:
    pdf_bytes: bytes
    field_count_filled: int
    warnings: list[str]
    # Strategy is hard-coded "acroform" so the strict-policy check in
    # fill_pdf.py treats it identically to PyPDF's acroform path. From the
    # outside there's no observable difference — both write into the
    # original PDF's AcroForm widgets and return the original PDF.
    strategy: str = "acroform"


def fill_acroform_via_fitz(
    pdf_bytes: bytes,
    answers: dict[str, str],
) -> FillResult:
    """
    Walk every page's widgets via PyMuPDF; for each widget whose
    fully-qualified field_name is a key in `answers`, set its value
    and call .update().

    Boolean / radio / checkbox widgets ('CheckBox' or 'RadioButton'
    field_type_string in fitz parlance):
      - "Yes"/"yes"/"1"/"true"/"on" or the widget's own on_state() →
        set field_value to the on_state string (typically "Yes")
      - "Off"/"off"/"0"/"false"/"" → set field_value to "Off"
      - other strings → treated as the literal export value

    Text widgets:
      - field_value set to the answer string verbatim.

    All other widget types (Signature, Button-pushbutton, etc.) are
    skipped silently — the engine never tries to fill them.
    """
    import fitz  # imported lazily so test environments without PyMuPDF
                 # can still import this module without crashing

    warnings: list[str] = []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        log.error("fitz_acroform_fill: failed to open PDF: %s", e)
        # Re-raise so fill_pdf's strict-policy wrapper sees a crash and
        # turns it into a friendly 500.
        raise

    filled = 0
    answers_remaining = dict(answers)

    try:
        for page in doc:
            widgets = page.widgets() or []
            for w in widgets:
                fname = w.field_name
                if fname not in answers_remaining:
                    continue
                value = answers_remaining.pop(fname)
                ftype = w.field_type_string

                # Pushbuttons are not data fields; never write to them.
                if ftype in ("PushButton",):
                    warnings.append(f"skipped pushbutton: {fname}")
                    continue

                # Signature widgets — fitz can't sign; skip.
                if ftype == "Signature":
                    warnings.append(f"skipped signature widget: {fname}")
                    continue

                if ftype in ("CheckBox", "RadioButton"):
                    # Read the widget's own on_state (typically "Yes" but
                    # can vary per PDF — e.g. "/Yes", "/On", or a custom
                    # name). Use it for truthy answers; "Off" for falsy.
                    #
                    # NOTE (verified empirically on KG1 + Anlage Kind):
                    # PyMuPDF's checkbox setter accepts only True/"Yes" to
                    # check a box — passing the widget's raw appearance
                    # value (e.g. "1" from button_states()) results in Off.
                    # fitz synthesizes the checked appearance itself on
                    # update(), so writing the on_state() string ("Yes") is
                    # correct even when the original /AP states are named
                    # differently. Do NOT "improve" this to button_states().
                    on_state_fn = getattr(w, "on_state", None)
                    on_state = on_state_fn() if callable(on_state_fn) else None
                    truthy = str(value).strip().lower() in {
                        "yes", "1", "true", "on", "x",
                    }
                    if str(value).strip() == "Off":
                        target = "Off"
                    elif truthy:
                        target = on_state or "Yes"
                    elif on_state and str(value) == on_state:
                        # Caller passed the literal on_state string ("Yes"
                        # in most cases) — honor it.
                        target = on_state
                    else:
                        # Non-truthy, not "Off", not the on_state — treat
                        # as Off to match PyPDF behavior.
                        target = "Off"
                    try:
                        w.field_value = target
                        w.update()
                        filled += 1
                    except Exception as e:
                        warnings.append(
                            f"checkbox/radio update failed for {fname}: {e}"
                        )
                    continue

                # Text / Choice / everything else: write verbatim.
                try:
                    w.field_value = str(value)
                    w.update()
                    filled += 1
                except Exception as e:
                    warnings.append(f"text update failed for {fname}: {e}")

        # Any answer keys we never matched to a widget: warn (these are
        # likely typos in the template's field map). NOT a fatal error —
        # the strict-policy zero-fill check in fill_pdf catches the worse
        # case where NOTHING got filled.
        for unmatched in answers_remaining:
            warnings.append(f"answer key not found in any widget: {unmatched}")

        out = io.BytesIO()
        # incremental=False writes a clean PDF (no append-only diff).
        # Required because we may have modified widget /V's inline.
        doc.save(out)
    finally:
        doc.close()

    return FillResult(
        pdf_bytes=out.getvalue(),
        field_count_filled=filled,
        warnings=warnings,
    )
