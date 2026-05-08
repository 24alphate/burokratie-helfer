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


def _find_label(page, primary: str, alts: list) -> list:
    """
    Try progressively shorter / simpler search strings until a match is found.

    Order:
      1. Primary string (full)
      2. Each alt string in order
      3. First 40 chars of primary
      4. First 25 chars of primary
      5. First 12 chars of primary  ← last resort, may be ambiguous

    Returns the first non-empty rect list found, or [].
    """
    for candidate in [primary] + list(alts):
        rects = page.search_for(candidate)
        if rects:
            return rects

    # Progressive prefix fallbacks on the primary string
    for n in (40, 25, 12):
        if len(primary) > n:
            rects = page.search_for(primary[:n])
            if rects:
                return rects

    return []


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

            alts = getattr(spec, "alt_label_searches", [])
            rects = _find_label(page, spec.label_search, alts)

            if not rects:
                log.warning(
                    "fitz_overlay: label NOT FOUND for %s (type=%s) — tried %d candidates: primary=%r alts=%r",
                    field_id, spec.field_type, 1 + len(alts), spec.label_search, alts,
                )
                skipped.append(field_id)
                if debug:
                    page.draw_line(
                        fitz.Point(20, 20 + page_idx * 10),
                        fitz.Point(30, 30 + page_idx * 10),
                        color=(1, 0, 0), width=1,
                    )
                continue

            label_rect = rects[0]  # use the first occurrence
            write_x = label_rect.x0 + spec.offset_x
            write_y = label_rect.y1 + spec.offset_y   # below bottom of label

            if spec.field_type == "checkbox":
                log.info(
                    "fitz_overlay: CHECKBOX %s — label found at (%.1f, %.1f)-(%.1f, %.1f) "
                    "→ X center at (%.1f, %.1f) size=%.1f",
                    field_id,
                    label_rect.x0, label_rect.y0, label_rect.x1, label_rect.y1,
                    write_x, write_y, spec.checkbox_size,
                )

        elif spec.strategy == "fixed":
            write_x = spec.fixed_x
            write_y = spec.fixed_y

        if write_x is None or write_y is None:
            skipped.append(field_id)
            continue

        # ── Write the answer ───────────────────────────────────────────────────
        try:
            if spec.field_type == "checkbox":
                # Draw a bold X centered at (write_x, write_y)
                s = spec.checkbox_size
                cx, cy = write_x, write_y
                page.draw_line(
                    fitz.Point(cx - s, cy - s), fitz.Point(cx + s, cy + s),
                    color=(0, 0, 0), width=2.0,
                )
                page.draw_line(
                    fitz.Point(cx - s, cy + s), fitz.Point(cx + s, cy - s),
                    color=(0, 0, 0), width=2.0,
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
