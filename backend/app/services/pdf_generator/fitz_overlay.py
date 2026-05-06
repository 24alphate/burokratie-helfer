"""
PyMuPDF-based overlay filler for flat (non-AcroForm) PDFs.

Strategy
--------
For each WriteSpec:
  1. "label_search": find spec.label_search text on the page → write relative to it.
  2. "fixed": write at absolute (fixed_x, fixed_y) coordinates.
  3. "skip": do not write (e.g. signature fields).

For text/date/number fields: insert the answer text below the label.
For checkbox fields: if the answer is truthy, draw a small X to the left of the
  label text (where the checkbox box is on the form).

Coordinate system
-----------------
PyMuPDF uses top-left origin, y-axis grows downward, units in PDF points (1 pt = 1/72").
page.search_for() returns Rect(x0, y0, x1, y1) where y0 < y1 (top < bottom).
page.insert_text(point, text) baseline anchors at `point`.

Debug overlay
-------------
When debug=True, draws a semi-transparent red rectangle around each write target.
Helps verify write positions without modifying real content.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.form_templates import WriteSpec

log = logging.getLogger("burokratie.fitz_overlay")

_TRUTHY = {"yes", "ja", "true", "1", "x", "on", "checked"}


def _is_truthy(value: str) -> bool:
    return str(value).strip().lower() in _TRUTHY


def fill_with_fitz(
    pdf_bytes: bytes,
    answers: dict[str, str],
    write_specs: list[WriteSpec],
    debug: bool = False,
) -> tuple[bytes, list[str], list[str]]:
    """
    Overlay answers onto the original PDF bytes.

    Returns:
        (output_pdf_bytes, filled_field_ids, skipped_field_ids)

    filled_field_ids  — fields that were successfully written to the PDF
    skipped_field_ids — fields with strategy="skip", label not found, or no answer
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    filled: list[str] = []
    skipped: list[str] = []

    for spec in write_specs:
        field_id = spec.field_id
        answer   = answers.get(field_id, "")

        # ── Skip strategy (signatures etc.) ───────────────────────────────────
        if spec.strategy == "skip":
            skipped.append(field_id)
            continue

        # ── No answer provided for this field ─────────────────────────────────
        if not answer:
            # For checkboxes: no answer = unchecked = intentionally blank
            if spec.field_type == "checkbox":
                pass   # leave blank — correct behaviour
            skipped.append(field_id)
            continue

        # ── Checkbox: only draw X if truthy answer ────────────────────────────
        if spec.field_type == "checkbox" and not _is_truthy(answer):
            skipped.append(field_id)
            continue

        # ── Get the page (0-indexed) ───────────────────────────────────────────
        page_idx = spec.source_page - 1
        if page_idx < 0 or page_idx >= len(doc):
            log.warning("fitz_overlay: field %s page %d out of range (doc has %d pages)",
                        field_id, spec.source_page, len(doc))
            skipped.append(field_id)
            continue
        page = doc[page_idx]

        # ── Resolve write point ────────────────────────────────────────────────
        write_x, write_y = None, None

        if spec.strategy == "label_search":
            if not spec.label_search:
                log.warning("fitz_overlay: field %s has label_search strategy but empty label_search", field_id)
                skipped.append(field_id)
                continue

            rects = page.search_for(spec.label_search)
            if not rects:
                # Try a shorter prefix of the label (first 30 chars)
                short = spec.label_search[:30]
                rects = page.search_for(short)

            if not rects:
                log.warning("fitz_overlay: label not found for %s: %r", field_id, spec.label_search)
                skipped.append(field_id)
                if debug:
                    # Draw a red cross to mark the miss
                    page.draw_line(
                        fitz.Point(20, 20 + page_idx * 10),
                        fitz.Point(30, 30 + page_idx * 10),
                        color=(1, 0, 0), width=1,
                    )
                continue

            label_rect = rects[0]  # use the first occurrence
            write_x = label_rect.x0 + spec.offset_x
            write_y = label_rect.y1 + spec.offset_y   # below bottom of label

        elif spec.strategy == "fixed":
            write_x = spec.fixed_x
            write_y = spec.fixed_y

        if write_x is None or write_y is None:
            skipped.append(field_id)
            continue

        # ── Write the answer ───────────────────────────────────────────────────
        try:
            if spec.field_type == "checkbox":
                # Draw an X centered at (write_x, write_y)
                s = spec.checkbox_size
                cx, cy = write_x, write_y
                page.draw_line(
                    fitz.Point(cx - s, cy - s), fitz.Point(cx + s, cy + s),
                    color=(0, 0, 0), width=1.5,
                )
                page.draw_line(
                    fitz.Point(cx - s, cy + s), fitz.Point(cx + s, cy - s),
                    color=(0, 0, 0), width=1.5,
                )
            else:
                # Insert text (truncated to max_chars)
                text = str(answer)[:spec.max_chars]
                page.insert_text(
                    fitz.Point(write_x, write_y),
                    text,
                    fontsize=spec.font_size,
                    color=(0, 0, 0),
                )

            filled.append(field_id)

            # Debug: draw a semi-transparent red rectangle around write area
            if debug:
                if spec.field_type == "checkbox":
                    debug_rect = fitz.Rect(write_x - 8, write_y - 8, write_x + 8, write_y + 8)
                else:
                    w = min(spec.font_size * len(answer), 200)
                    debug_rect = fitz.Rect(write_x, write_y - spec.font_size,
                                           write_x + w, write_y + 2)
                page.draw_rect(debug_rect, color=(1, 0, 0), width=0.5)
                page.insert_text(
                    fitz.Point(write_x, write_y - spec.font_size - 2),
                    field_id[:20],
                    fontsize=5,
                    color=(1, 0, 0),
                )

        except Exception as e:
            log.error("fitz_overlay: failed to write field %s: %s", field_id, e)
            skipped.append(field_id)

    output_bytes = doc.tobytes()
    doc.close()

    log.info(
        "fitz_overlay DONE: filled=%d skipped=%d total_specs=%d",
        len(filled), len(skipped), len(write_specs),
    )
    return output_bytes, filled, skipped
