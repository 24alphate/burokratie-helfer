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

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


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

    # Alternative search strings tried in order if label_search yields no results.
    # Use shorter or umlaut-free substrings that are still unique on the page.
    alt_label_searches: list = field(default_factory=list)


# ── RadioGroup: one logical radio question → many AcroForm widgets ───────────

@dataclass
class RadioGroup:
    """
    Phase F1 — Express a German-form-style "one option per widget" radio
    layout as a single user-facing radio question on a verified template.

    Why: many official German PDFs (e.g. KG1 Familienstand) put each option
    on its own /Btn widget. The user should see ONE question with N options;
    the engine then writes "Yes" to the widget for the chosen option and
    "Off" to all sibling widgets in the group.

    Scope: this mechanism applies ONLY to verified templates (Level 1 +
    fill_strategy="acroform"). It is intentionally not exposed in the
    Level 2 generic AcroForm path.

    Fields:
        field_id      The logical field_id the user answers. MUST also
                      appear as a FieldMapEntry with field_type="radio"
                      so the question UI can render it normally.
        widget_names  Every widget that belongs to this group. The fill
                      step writes "Off" to every widget in this list, then
                      "Yes" to the one chosen.
        options       Ordered list of (value, widget_name) pairs. `value`
                      is the option value the user submits; the matching
                      widget gets set to "Yes". Every widget_name in
                      `options` MUST also appear in `widget_names`.

    Hard rules enforced by validate_template():
        - Every option's widget_name appears in widget_names
        - widget_names are unique across all radio groups in this template
        - field_id appears in get_field_map() with field_type="radio"
    """
    field_id: str
    widget_names: list[str]
    options: list[tuple[str, str]] = field(default_factory=list)


# ── SplitField: one logical text question → several char-sliced widgets ──────

@dataclass
class SplitField:
    """
    Phase v2 — Express a value that the PDF splits across several adjacent
    widgets (e.g. the 11-digit Steuer-Identifikationsnummer on KG1, laid out
    as four comb boxes of 2 / 3 / 3 / 3 chars) as a SINGLE user-facing text
    question.

    Why: asking "digits 1-2 of your tax ID", "digits 3-5", … is hostile UX.
    The user answers once; the fill step strips non-digits and slices the
    value across the widgets according to `slices`.

    Scope: verified templates only (Level 1). Mirrors RadioGroup — the logical
    `field_id` is the only thing the user sees / answers and the only thing
    that appears in get_field_map(); the raw `widget_names` are known solely
    to the engine and never enter extracted_field_ids.

    Fields:
        field_id      Logical field the user answers. MUST appear in
                      get_field_map() as field_type="text".
        widget_names  Ordered PDF widget names that receive the slices.
        slices        Chars written to each widget, in order. len(slices)
                      MUST equal len(widget_names); sum(slices) is the
                      expected cleaned-answer length (e.g. 11 for a Steuer-ID).

    Hard rules enforced by validate_template():
        - len(slices) == len(widget_names)
        - field_id appears in get_field_map() with field_type="text"
        - widget_names are unique across all radio groups AND split fields
    """
    field_id: str
    widget_names: list[str]
    slices: list[int] = field(default_factory=list)


# ── VerifiedTemplate ABC ──────────────────────────────────────────────────────

class VerifiedTemplate(ABC):
    template_id: str
    name: str

    # Phase F/0-A — Fill-strategy declaration. Picks how /fill-pdf writes the
    # user's answers back into the original PDF. Default preserves the
    # pre-Phase-F Level 1 behavior (Jobcenter BuT etc.).
    #
    # Allowed values:
    #   "fitz_overlay" — overlay text via WriteSpecs onto the source PDF.
    #                    Required when the source has no AcroForm widgets,
    #                    or when WriteSpec coordinates are needed for any
    #                    other reason. The default.
    #   "acroform"     — write directly into the source PDF's AcroForm
    #                    widgets via PyPDFGenerator. WriteSpecs are not
    #                    needed. Engine still applies the Phase E1 strict
    #                    policy (no summary/minimal fallback, no zero-fill).
    #   "fitz_acroform"— PyMuPDF widget writer for XFA-stub PDFs whose /Btn
    #                    widgets lack /AP (KG1, KiZ). Checkboxes via on_state.
    #   "pypdf_native" — PyPDF writer for born-AcroForm PDFs with CUSTOM button
    #                    export values + native radios (e.g. Bürgergeld:
    #                    checkboxes export "selektiert", radios "0"/"1").
    #                    Writes the real on-state / export value.
    fill_strategy: str = "fitz_overlay"

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

        Templates declaring fill_strategy="acroform" may legitimately return
        an empty list — fill_pdf does not need WriteSpecs in that path.
        """
        return []

    def get_radio_groups(self) -> list[RadioGroup]:
        """
        Phase F1 — Return zero or more RadioGroup definitions.

        Only consulted by /fill-pdf when fill_strategy == "acroform".
        Default empty list preserves all existing template behavior.
        """
        return []

    def get_split_fields(self) -> list[SplitField]:
        """
        Phase v2 — Return zero or more SplitField definitions.

        Consulted by /fill-pdf's expand_logical_fields() for acroform-style
        fill strategies. Default empty list preserves existing behavior.
        """
        return []


# ── Registry ──────────────────────────────────────────────────────────────────

# Cached template list — built once on first use.
_TEMPLATES_CACHE: list[VerifiedTemplate] | None = None


def validate_template(t: VerifiedTemplate) -> list[str]:
    """
    Check a template against the Level 1 contract.
    Returns a list of error strings (empty = OK).
    Checks:
      - fill_strategy is one of the allowed values
      - field_ids are unique
      - every field_id has a VERIFIED_BY_FIELD_ID entry
      - every non-signature field_id has a WriteSpec
        (skipped for fill_strategy="acroform" — no WriteSpecs needed there)
      - en + de locales have non-empty question strings
    """
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID

    errors: list[str] = []
    field_map = t.get_field_map()
    field_ids = [f.field_id for f in field_map]

    # Phase F/0-A — fill_strategy must be one of the supported values.
    # Phase F6 added "fitz_acroform" for XFA-style PDFs whose /Btn widgets
    # have no /AP appearance (PyPDF can't write them; fitz can).
    strategy = getattr(t, "fill_strategy", "fitz_overlay")
    if strategy not in ("fitz_overlay", "acroform", "fitz_acroform", "pypdf_native"):
        errors.append(
            f"INVALID_FILL_STRATEGY: {strategy!r} "
            f"(must be 'fitz_overlay', 'acroform', 'fitz_acroform', or 'pypdf_native')"
        )

    # Unique field_ids
    seen: set[str] = set()
    for fid in field_ids:
        if fid in seen:
            errors.append(f"DUPLICATE_FIELD_ID: {fid}")
        seen.add(fid)

    spec_ids = {s.field_id for s in t.get_write_specs()}

    for f in field_map:
        is_signature = f.confidence <= 0.5
        if is_signature:
            continue  # Signature fields are excluded from Q&A flow; no verified question needed

        # Every non-signature field must have a verified question
        if f.field_id not in VERIFIED_BY_FIELD_ID:
            errors.append(f"NO_VERIFIED_QUESTION: {f.field_id}")
        # Every non-signature field must have a WriteSpec — UNLESS the
        # template uses an acroform-style strategy, in which case fill_pdf
        # writes directly into the PDF widgets without coordinates.
        if strategy == "fitz_overlay" and f.field_id not in spec_ids:
            errors.append(f"NO_WRITE_SPEC: {f.field_id}")

    # Required locales must have non-empty question text (non-signature fields only)
    for locale in ("en", "de"):
        for f in field_map:
            if f.confidence <= 0.5:
                continue
            entry = VERIFIED_BY_FIELD_ID.get(f.field_id, {})
            if not entry.get(locale, {}).get("question"):
                errors.append(f"MISSING_QUESTION locale={locale} field={f.field_id}")

    # Phase F1 — radio_group invariants (only when the template defines any)
    radio_groups = list(getattr(t, "get_radio_groups", lambda: [])())
    if radio_groups:
        radio_field_ids = {f.field_id for f in field_map}
        seen_widgets: set[str] = set()
        for rg in radio_groups:
            # 1. The logical field_id must appear in the field_map as a radio
            if rg.field_id not in radio_field_ids:
                errors.append(
                    f"RADIO_GROUP_MISSING_FIELD: {rg.field_id} not in get_field_map()"
                )
            else:
                fm_entry = next(f for f in field_map if f.field_id == rg.field_id)
                if fm_entry.field_type != "radio":
                    errors.append(
                        f"RADIO_GROUP_WRONG_TYPE: {rg.field_id} must have field_type='radio', got {fm_entry.field_type!r}"
                    )
            # 2. Every option's widget must be declared in widget_names
            for value, widget in rg.options:
                if widget not in rg.widget_names:
                    errors.append(
                        f"RADIO_GROUP_OPTION_WIDGET_MISSING: option {value!r} -> {widget!r} not in widget_names of {rg.field_id}"
                    )
            # 3. Widget names must be unique across all radio groups
            for w in rg.widget_names:
                if w in seen_widgets:
                    errors.append(f"RADIO_GROUP_DUPLICATE_WIDGET: {w}")
                seen_widgets.add(w)

    # Phase v2 — split_field invariants (only when the template defines any)
    split_fields = list(getattr(t, "get_split_fields", lambda: [])())
    if split_fields:
        text_field_ids = {f.field_id for f in field_map if f.field_type == "text"}
        for sf in split_fields:
            # 1. The logical field_id must appear in the field_map as text
            if sf.field_id not in text_field_ids:
                errors.append(
                    f"SPLIT_FIELD_MISSING_TEXT_FIELD: {sf.field_id} not in get_field_map() as field_type='text'"
                )
            # 2. slices must align 1:1 with widget_names
            if len(sf.slices) != len(sf.widget_names):
                errors.append(
                    f"SPLIT_FIELD_SLICE_MISMATCH: {sf.field_id} has {len(sf.slices)} slices "
                    f"for {len(sf.widget_names)} widgets"
                )
            # 3. Widget names must be unique across radio groups AND split fields
            for w in sf.widget_names:
                if w in seen_widgets:
                    errors.append(f"SPLIT_FIELD_DUPLICATE_WIDGET: {w}")
                seen_widgets.add(w)

    return errors


def _all_templates() -> list[VerifiedTemplate]:
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is None:
        from app.services.form_templates.jobcenter_but import JobcenterButTemplate
        from app.services.form_templates.familienkasse_kg1 import FamilienkasseKg1Template
        from app.services.form_templates.kg1_anlage_kind import Kg1AnlageKindTemplate
        from app.services.form_templates.kiz1_antrag import Kiz1AntragTemplate
        from app.services.form_templates.kiz1_anlage_kind import Kiz1AnlageKindTemplate
        from app.services.form_templates.kiz1_anlage_antragsteller import (
            Kiz1AnlageAntragstellerTemplate,
        )
        from app.services.form_templates.buergergeld_hauptantrag import (
            BuergergeldHauptantragTemplate,
        )
        _TEMPLATES_CACHE = [
            JobcenterButTemplate(),
            FamilienkasseKg1Template(),
            Kg1AnlageKindTemplate(),
            Kiz1AntragTemplate(),
            Kiz1AnlageKindTemplate(),
            Kiz1AnlageAntragstellerTemplate(),
            BuergergeldHauptantragTemplate(),
        ]
        for t in _TEMPLATES_CACHE:
            errors = validate_template(t)
            for err in errors:
                _log.error("Template %s contract violation: %s", t.template_id, err)
    return _TEMPLATES_CACHE


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
