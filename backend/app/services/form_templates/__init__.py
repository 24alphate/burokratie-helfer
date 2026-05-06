"""
Verified form template registry.

A verified template:
  - Has a fingerprint() method that checks stable PDF text for known strings.
  - Has a get_field_map() method that returns a hand-verified list of FieldMapEntry.
  - Has a get_write_specs() method that returns WriteSpec for every field —
    telling the fitz_overlay engine exactly where to write answers onto the PDF.
  - Sets confidence=1.0 for every field (manually confirmed to exist in the PDF).
  - Returns source="verified_template" so callers know not to trust the regex extractor.

Usage in extract_field_map():
  text = _extract_full_text(pdf_bytes)
  tmpl = find_matching_template(text)
  if tmpl:
      return ExtractionResult(pdf_type="verified_template", fields=tmpl.get_field_map(), ...)

Usage in fill_pdf.py:
  tmpl = find_template_by_id(template_id)
  if tmpl:
      specs = tmpl.get_write_specs()
      out_bytes, filled, skipped = fill_with_fitz(pdf_bytes, answers, specs)

Registering a new template:
  1. Create a new module in this package.
  2. Subclass VerifiedTemplate.
  3. Add an instance to _TEMPLATES / _BY_ID below.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ── WriteSpec: fill-time positioning data per field ───────────────────────────

@dataclass
class WriteSpec:
    """
    Tells fitz_overlay where to write one field's answer onto the PDF.

    strategy values:
      "label_search"  PyMuPDF searches for label_search text on the page,
                      then writes at an offset relative to the found rect.
      "fixed"         Write at an absolute (fixed_x, fixed_y) coordinate.
      "skip"          Do not write this field (e.g. signatures).

    Coordinates are in PDF points (1 pt = 1/72 inch), origin top-left (PyMuPDF).
    """
    field_id:   str
    field_type: str          # "text" | "checkbox" | "date" | "number" | "signature"
    source_page: int         # 1-indexed page number

    strategy: str = "label_search"   # "label_search" | "fixed" | "skip"

    # label_search: search this exact text on source_page
    label_search: str = ""

    # Offset from the found rect to the write point (PDF points):
    #   For text: offset_y > 0 = below the label bottom edge
    #   For checkboxes: offset_x < 0 = to the left of the label (where box is)
    offset_x: float = 0.0
    offset_y: float = 10.0   # default: write 10pt below the label

    # fixed strategy: write at these absolute coordinates
    fixed_x: float = 0.0
    fixed_y: float = 0.0

    # Typography
    font_size: float = 9.0
    max_chars: int   = 60

    # Checkbox X mark geometry (used when field_type="checkbox")
    checkbox_size: float = 5.0   # half-size of the X arms in points


# ── VerifiedTemplate ABC ──────────────────────────────────────────────────────

class VerifiedTemplate(ABC):
    template_id: str
    name: str

    @abstractmethod
    def fingerprint(self, full_text: str) -> bool:
        """Return True if full_text matches this template."""

    @abstractmethod
    def get_field_map(self) -> list:
        """Return a list of FieldMapEntry for every field in this form."""

    def get_write_specs(self) -> list[WriteSpec]:
        """
        Return fill-time positioning for every field.
        Empty list → all fields are reported as not_fillable_yet.
        """
        return []


# ── Registry ──────────────────────────────────────────────────────────────────

def _all_templates() -> list[VerifiedTemplate]:
    from app.services.form_templates.jobcenter_but import JobcenterButTemplate
    return [JobcenterButTemplate()]


def find_matching_template(full_text: str) -> VerifiedTemplate | None:
    """
    Check all registered templates in priority order.
    Returns the first match, or None if no template recognises the PDF.
    """
    for tmpl in _all_templates():
        if tmpl.fingerprint(full_text):
            return tmpl
    return None


def find_template_by_id(template_id: str) -> VerifiedTemplate | None:
    """Look up a template by its template_id string (used by fill_pdf.py)."""
    for tmpl in _all_templates():
        if tmpl.template_id == template_id:
            return tmpl
    return None
