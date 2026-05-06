"""
Verified form template registry.

A verified template:
  - Has a fingerprint() method that checks stable PDF text for known strings.
  - Has a get_field_map() method that returns a hand-verified list of FieldMapEntry.
  - Sets confidence=1.0 for every field (manually confirmed to exist in the PDF).
  - Returns source="verified_template" so callers know not to trust the regex extractor.

Usage in extract_field_map():
  text = _extract_full_text(pdf_bytes)
  tmpl = find_matching_template(text)
  if tmpl:
      return ExtractionResult(pdf_type="verified_template", fields=tmpl.get_field_map(), ...)

Registering a new template:
  1. Create a new module in this package.
  2. Subclass VerifiedTemplate.
  3. Add an instance to _TEMPLATES below.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class VerifiedTemplate(ABC):
    template_id: str
    name: str

    @abstractmethod
    def fingerprint(self, full_text: str) -> bool:
        """Return True if full_text matches this template."""

    @abstractmethod
    def get_field_map(self) -> list:
        """Return a list of FieldMapEntry for every field in this form."""


def find_matching_template(full_text: str) -> VerifiedTemplate | None:
    """
    Check all registered templates in priority order.
    Returns the first match, or None if no template recognises the PDF.
    """
    from app.services.form_templates.jobcenter_but import JobcenterButTemplate
    _TEMPLATES: list[VerifiedTemplate] = [
        JobcenterButTemplate(),
    ]
    for tmpl in _TEMPLATES:
        if tmpl.fingerprint(full_text):
            return tmpl
    return None
