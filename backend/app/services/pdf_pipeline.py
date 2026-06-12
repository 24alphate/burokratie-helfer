"""
Deterministic, field-map-first PDF processing pipeline.

Architecture:
    PDF bytes
      │
      ├─[1] detect_pdf_type()  →  "acroform" | "flat" | "scanned"
      │
      ├─[2] extract_field_map()  →  list[FieldMapEntry]
      │       Every entry has a field_id that is the GROUND TRUTH anchor.
      │       No field can be added that does not exist in the PDF.
      │
      ├─[3] translate_fields()  →  dict[field_id → {question, explanation, options}]
      │       AI may only translate / explain existing field_ids.
      │
      ├─[4] validate_no_hallucinations()
      │       Reject any field_id AI returned that is not in the extracted map.
      │       Add fallback (raw label) for any field AI missed.
      │
      └─[5] field_map_to_defs()  →  list[FieldDefinition]
              Applies confidence gate:
              conf >= 0.90  → show_question=True,  needs_review=False
              0.70–0.89     → show_question=True,  needs_review=True
              conf < 0.70   → show_question=False  (blocked, logged)

Anti-hallucination guarantee:
    After AI returns translations, EVERY key is checked against extracted_ids.
    Invented keys are discarded. Missing fields get the raw PDF label as fallback.
    This guarantees: |questions| == |extracted_fields| with no invented extras.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Optional

# ── Field type flags (AcroForm spec) ──────────────────────────────────────────
_FF_RADIO       = 1 << 15
_FF_PUSHBUTTON  = 1 << 16
_FF_MULTISELECT = 1 << 21

MAX_FIELDS = 200   # cap total extracted fields per document

# Confidence thresholds
CONF_SHOW_MIN     = 0.70   # below this → show_question=False (blocked)
CONF_REVIEW_MIN   = 0.90   # below this (but >= 0.70) → needs_review=True


# ── AcroForm technical-name cleanup ───────────────────────────────────────────

# Prefixes that signal a technical field name, not a user-visible label.
# Pattern: prefix immediately followed by a capital letter (CamelCase naming).
_ACROFORM_PREFIX_RE = re.compile(
    r'^(txtf|txt|datef?|chk|check|cb|rb|radio|btn|button|lbl|label|cmb|combo|lst|list|'
    r'fld|field|frm|form|grp|group|num|number|sel|select|img|image|sig|sign)(?=[A-Z_])',
    re.IGNORECASE,
)

# German abbreviations / compound fragments found inside AcroForm field names.
# Applied BEFORE camelCase splitting so they survive intact.
_DE_COMPOUND_RE: list[tuple] = [
    (re.compile(r'GebDatum', re.IGNORECASE), 'Geburtsdatum'),
    (re.compile(r'GebName',  re.IGNORECASE), 'Geburtsname'),
    (re.compile(r'GebOrt',   re.IGNORECASE), 'Geburtsort'),
    (re.compile(r'NrOrt',    re.IGNORECASE), 'Nummer Ort'),
    (re.compile(r'StNr',     re.IGNORECASE), 'Steuernummer'),
    (re.compile(r'AuswNr',   re.IGNORECASE), 'Ausweisnummer'),
    (re.compile(r'PLZ',      re.IGNORECASE), 'Postleitzahl'),
    (re.compile(r'TelNr',    re.IGNORECASE), 'Telefonnummer'),
    (re.compile(r'HausNr',   re.IGNORECASE), 'Hausnummer'),
    (re.compile(r'KtoNr',    re.IGNORECASE), 'Kontonummer'),
]

# Namespace group words to strip when they are the FIRST word after cleaning.
# These are organisational sections in German forms (Person/Adresse/etc.),
# not part of the label. Stripping them leaves just the meaningful term.
# Example: "Person Vorname" → "Vorname"; "Adresse Postleitzahl" → "Postleitzahl"
_NAMESPACE_WORDS = frozenset({
    "person", "antragsteller", "antragstellerin", "antragesteller",
    "adresse", "anschrift", "wohnort", "wohnadresse",
    "leistung", "leistungen",
    "arbeit", "beschaeftigung", "beschäftigung",
    "partner", "ehegatte", "ehefrau", "ehemann",
    "kind", "kinder",
    "bank", "konto", "bankverbindung",
    "angaben", "allgemein", "allgemeine",
    "zeuge", "vertreter",
})


def _clean_acroform_field_name(name: str) -> str:
    """
    Convert a technical AcroForm /T field name into a human-readable label.

    The result stays in the document language (usually German) so that the
    AI translator can produce a correct question in the user's language.

    Examples:
        txtfPersonVorname  → Vorname
        datePersonGebDatum → Geburtsdatum
        chkLeistungSGBII   → SGBII
        txtfAdressePLZ     → Postleitzahl
        txtfAdresseStrasse → Strasse
    """
    if not name or len(name) < 3:
        return name

    # 1. Strip known technical prefix (only if something follows it)
    cleaned = _ACROFORM_PREFIX_RE.sub('', name).strip()
    if not cleaned:
        cleaned = name

    # 2. Expand German compound abbreviations before splitting
    for pattern, replacement in _DE_COMPOUND_RE:
        cleaned = pattern.sub(replacement, cleaned)

    # 3. Split camelCase:  "PersonVorname" → "Person Vorname"
    cleaned = re.sub(r'([a-z\d])([A-Z])', r'\1 \2', cleaned)
    # Handle sequences like "SGBii" → keep SGBII together
    cleaned = re.sub(r'([A-Z]{2,})([A-Z][a-z])', r'\1 \2', cleaned)

    # 4. Replace underscores/dots
    cleaned = cleaned.replace('_', ' ').replace('.', ' ')

    # 5. Collapse whitespace
    cleaned = ' '.join(cleaned.split())

    # 6. Strip leading namespace group word (e.g. "Person", "Adresse")
    parts = cleaned.split(' ', 1)
    if len(parts) == 2 and parts[0].lower() in _NAMESPACE_WORDS:
        cleaned = parts[1].strip()

    return cleaned if cleaned else name


def _looks_like_technical_id(text: str) -> bool:
    """
    Return True when text appears to be a raw technical identifier rather
    than a readable question or label.  Used as a quality gate before
    showing text to the user.
    """
    if not text or len(text) < 3:
        return False
    # Starts with a known AcroForm technical prefix pattern
    if _ACROFORM_PREFIX_RE.match(text):
        return True
    # Long string with no spaces and mixed case (camelCase) = technical ID
    if ' ' not in text and len(text) > 8 and re.search(r'[a-z][A-Z]', text):
        return True
    return False


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class FieldMapEntry:
    """
    One form field. This is the ground truth.
    Every downstream question MUST reference exactly one FieldMapEntry.field_id.
    """
    field_id: str               # exact PDF widget name or generated id
    original_label: str         # label text as it appears in the PDF (document language)
    field_type: str             # text|date|number|checkbox|radio|select|multiselect|signature
    source_page: int            # 1-indexed
    bbox: Optional[list[float]] = None       # [x0, y0, x1, y1] in PDF points
    options: list[str] = field(default_factory=list)  # PDF-native option values
    # Human-readable label per option VALUE (document language), recovered from
    # the page text beside each choice box (Feature E). Maps option value →
    # German label, e.g. {"0": "Einzelfahrt", "1": "Tageskarte"}. The AI
    # translates these so the user sees real choices instead of "0"/"1".
    option_labels: dict = field(default_factory=dict)
    # Section header this field sits under in the PDF (document language),
    # e.g. "Datum des Schulausflugstages" (Feature D). Gives the AI translator
    # the context a bare field name ("Tag") lacks. Never affects field_id/filling.
    section_title: Optional[str] = None
    current_value: str = ""     # pre-filled value if any
    confidence: float = 1.0     # 1.0=AcroForm, 0.75=pdfplumber layout, 0.5=ocr
    source: str = "acroform"    # "acroform" | "pdfplumber" | "ocr"
    required: bool = False
    source_text: str = ""       # exact text from the PDF that grounds this field
    reason: str = "pdf_field"   # "pdf_field" | "derived_helper"
    guidance: Optional[dict] = None      # GuidanceText dict from verified template (never affects field_id/filling)
    semantic_key: Optional[str] = None   # e.g. "applicant.full_name" — for future answer reuse
    # Conditional-flow gate (Phase v2). When set, the question is only shown if
    # the condition evaluates True against the user's current answers. Uses the
    # same schema as FormEngine.evaluate_condition: field_equals / field_not_equals
    # / field_in / field_not_in / and / or. Evaluated CLIENT-SIDE in the stateless
    # pipeline (see frontend lib/conditions.ts) and re-applied at fill time when
    # the review page filters answers to currently-applicable fields.
    condition: Optional[dict] = None


@dataclass
class ExtractionResult:
    pdf_type: str                           # "acroform" | "flat" | "scanned" | "verified_template" | "unknown"
    fields: list[FieldMapEntry]
    total_pages: int = 0
    error: Optional[str] = None
    template_id: Optional[str] = None      # set when a verified template matched
    extraction_source: str = "auto"        # "verified_template" | "acroform" | "pdfplumber" | "auto"
    support_level: int = 4                 # 1=verified | 2=acroform | 3=flat | 4=scanned/unknown


@dataclass
class DocumentRoute:
    """
    Routing decision computed once per upload, before extraction runs.
    Centralizes the level/source/template_id selection so callers can log,
    test, and branch on a single value.
    """
    support_level: int          # 1 | 2 | 3 | 4
    extraction_source: str      # "verified_template" | "acroform" | "pdfplumber" | "auto"
    pdf_type: str               # "acroform" | "flat" | "scanned" | "verified_template" | "unknown"
    template_id: Optional[str] = None
    total_pages: int = 0


# Mapping: extraction_source → support_level
_EXTRACTION_SOURCE_TO_LEVEL = {
    "verified_template": 1,
    "acroform":          2,
    "pdfplumber":        3,
    "ocr":               3,   # Stage 4B promotion: scanned + OCR-derived fields → Level 3
    "auto":              4,
}


def support_level_for(extraction_source: str) -> int:
    """Single source of truth for support_level. Used by router and report builder."""
    return _EXTRACTION_SOURCE_TO_LEVEL.get(extraction_source, 4)


@dataclass
class HallucinationReport:
    """
    Result of validating AI-returned translations against the extracted field map.
    """
    is_clean: bool                  # True if AI invented no fields
    invented: list[str]             # field_ids AI returned that don't exist in field_map
    missing: list[str]              # field_ids in field_map that AI didn't translate
    cleaned_translations: dict      # safe dict: invented removed, missing backfilled


@dataclass
class AnalysisReport:
    """
    Accuracy report returned after field extraction.
    grounding_rate is always 100% by design (anti-hallucination validator enforces this).
    coverage_rate = what fraction of extracted fields became visible questions.
    """
    pdf_type: str
    total_pages: int
    field_count: int                # fields extracted from PDF
    questions_shown: int            # fields with show_question=True (conf >= 0.70)
    questions_blocked: int          # fields with show_question=False (conf < 0.70)
    low_confidence_fields: int      # conf in [0.70, 0.90) → shown but needs_review
    invented_questions_removed: int # AI-invented keys discarded by anti-hallucination
    coverage_rate: str              # questions_shown / field_count (as percentage)
    grounding_rate: str             # always "100%" — enforced by validator
    grounding_ok: bool              # True when grounding_rate == 100%


# ── PDF type detection ─────────────────────────────────────────────────────────

def detect_pdf_type(pdf_bytes: bytes) -> tuple[str, int]:
    """
    Returns (pdf_type, page_count).

    "acroform" — has AcroForm /Fields with ≥1 widget → can be filled programmatically
    "flat"     — has readable text but no AcroForm   → pdfplumber text+layout extraction
    "scanned"  — very little extractable text         → needs OCR
    "unknown"  — failed to parse
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)

        root = reader.trailer.get("/Root")
        if root:
            if hasattr(root, "get_object"):
                root = root.get_object()
            acroform = root.get("/AcroForm")
            if acroform:
                if hasattr(acroform, "get_object"):
                    acroform = acroform.get_object()
                fields_arr = acroform.get("/Fields", [])
                if hasattr(fields_arr, "get_object"):
                    fields_arr = fields_arr.get_object()
                if len(list(fields_arr)) > 0:
                    return "acroform", page_count

        total_chars = 0
        for page in reader.pages[:5]:
            try:
                total_chars += len((page.extract_text() or "").strip())
            except Exception:
                pass

        return ("flat" if total_chars > 200 else "scanned"), page_count

    except Exception:
        return "unknown", 0


# ── AcroForm extraction (fillable PDFs) ───────────────────────────────────────

def _classify_field_type(ft: str, flags: int) -> Optional[str]:
    if ft == "/Tx":   return "text"
    if ft == "/Sig":  return "signature"
    if ft == "/Ch":   return "multiselect" if (flags & _FF_MULTISELECT) else "select"
    if ft == "/Btn":
        if flags & _FF_PUSHBUTTON: return None
        return "radio" if (flags & _FF_RADIO) else "checkbox"
    return "text"


def _radio_options_from_kids(field_obj) -> list[str]:
    """Read radio export values from /Kids → /AP/N (field tree, no page walk)."""
    options: list[str] = []
    kids = field_obj.get("/Kids", [])
    if hasattr(kids, "get_object"):
        kids = kids.get_object()
    for kid_ref in list(kids)[:50]:
        try:
            kid = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            ap = kid.get("/AP")
            if ap is None:
                continue
            if hasattr(ap, "get_object"):
                ap = ap.get_object()
            normal = ap.get("/N")
            if normal is None:
                continue
            if hasattr(normal, "get_object"):
                normal = normal.get_object()
            for key in (normal.keys() if hasattr(normal, "keys") else []):
                val = str(key).lstrip("/")
                if val and val.lower() not in ("off", ""):
                    if val not in options:
                        options.append(val)
        except Exception:
            continue
    return options


def _radio_option_widgets(field_obj) -> list[tuple[str, list[float]]]:
    """
    Per-kid (export_value, rect) for a radio group — used to find the human
    label printed beside each option box (Feature E). rect is the kid widget's
    /Rect in PDF points (bottom-left origin), same convention as FieldMapEntry.bbox.
    """
    out: list[tuple[str, list[float]]] = []
    kids = field_obj.get("/Kids", [])
    if hasattr(kids, "get_object"):
        kids = kids.get_object()
    for kid_ref in list(kids)[:50]:
        try:
            kid = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            value = ""
            ap = kid.get("/AP")
            if ap is not None:
                if hasattr(ap, "get_object"):
                    ap = ap.get_object()
                normal = ap.get("/N")
                if normal is not None:
                    if hasattr(normal, "get_object"):
                        normal = normal.get_object()
                    for key in (normal.keys() if hasattr(normal, "keys") else []):
                        v = str(key).lstrip("/")
                        if v and v.lower() not in ("off", ""):
                            value = v
                            break
            rect = kid.get("/Rect")
            bbox: Optional[list[float]] = None
            if rect:
                try:
                    bbox = [float(x) for x in list(rect)[:4]]
                except Exception:
                    bbox = None
            if value and bbox:
                out.append((value, bbox))
        except Exception:
            continue
    return out


def _collect_radio_option_widgets(
    pdf_bytes: bytes, names: set[str]
) -> dict[str, list[tuple[str, list[float]]]]:
    """Walk the AcroForm tree → {field_id: [(value, rect), ...]} for named radio fields."""
    result: dict[str, list[tuple[str, list[float]]]] = {}
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        root = reader.trailer.get("/Root")
        if root is None:
            return result
        if hasattr(root, "get_object"):
            root = root.get_object()
        acroform = root.get("/AcroForm")
        if acroform is None:
            return result
        if hasattr(acroform, "get_object"):
            acroform = acroform.get_object()
        fields_arr = acroform.get("/Fields", [])
        if hasattr(fields_arr, "get_object"):
            fields_arr = fields_arr.get_object()

        def walk(arr, depth=0):
            for ref in list(arr):
                try:
                    f = ref.get_object() if hasattr(ref, "get_object") else ref
                    name = f.get("/T", "")
                    if hasattr(name, "get_object"):
                        name = name.get_object()
                    clean = str(name).lstrip("/").strip()
                    has_kids = "/Kids" in f
                    if clean in names and has_kids:
                        ow = _radio_option_widgets(f)
                        if ow:
                            result[clean] = ow
                        continue  # kids are option widgets, not nested fields
                    if has_kids and depth < 5:
                        kids = f.get("/Kids", [])
                        if hasattr(kids, "get_object"):
                            kids = kids.get_object()
                        walk(kids, depth + 1)
                except Exception:
                    continue

        walk(fields_arr)
    except Exception:
        return result
    return result


# Option-label positional caps (PDF points): the human label sits to the RIGHT
# of the choice box on the same row — the common German-form convention.
_OPTION_LABEL_RIGHT_MAX_GAP = 280.0
_OPTION_LABEL_ROW_TOL = 4.0
_OPTION_LABEL_MAX_CHARS = 80


def _associate_option_labels(fields: list[FieldMapEntry], pdf_bytes: bytes) -> None:
    """
    Feature E (positional): for radio groups whose options are non-descriptive
    export values ("0"/"1"), recover the German label printed beside each box
    and store it in entry.option_labels {value: label}. Safe + additive: only
    fills option_labels; never changes field_id, type, or option values. Misses
    are left for the Claude-vision fallback (recover_option_labels_via_vision).
    """
    radio_ids = {f.field_id for f in fields if f.field_type == "radio"}
    if not radio_ids:
        return
    widgets_by_field = _collect_radio_option_widgets(pdf_bytes, radio_ids)
    if not widgets_by_field:
        return
    try:
        import pdfplumber
    except Exception:
        return

    by_field = {f.field_id: f for f in fields}
    by_page: dict[int, list[str]] = {}
    for fid in widgets_by_field:
        f = by_field.get(fid)
        if f:
            by_page.setdefault(f.source_page, []).append(fid)

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, fids in by_page.items():
                idx = page_num - 1
                if idx < 0 or idx >= len(pdf.pages):
                    continue
                page = pdf.pages[idx]
                H = float(page.height)
                try:
                    words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
                except Exception:
                    words = []
                cand = [w for w in words if (w.get("text") or "").strip()]
                if not cand:
                    continue
                for fid in fids:
                    entry = by_field[fid]
                    labels: dict[str, str] = {}
                    for value, rect in widgets_by_field[fid]:
                        x0, y0, x1, y1 = rect
                        box_right = max(x0, x1)
                        top = H - max(y0, y1)
                        bot = H - min(y0, y1)
                        cy = (top + bot) / 2.0
                        row = [
                            w for w in cand
                            if float(w["x0"]) >= box_right - 2
                            and (float(w["x0"]) - box_right) <= _OPTION_LABEL_RIGHT_MAX_GAP
                            and float(w["top"]) - _OPTION_LABEL_ROW_TOL <= cy
                            and cy <= float(w["bottom"]) + _OPTION_LABEL_ROW_TOL
                        ]
                        if not row:
                            continue
                        row.sort(key=lambda w: float(w["x0"]))
                        text = " ".join((w.get("text") or "").strip() for w in row).strip()
                        text = text[:_OPTION_LABEL_MAX_CHARS].strip()
                        if text and len(text) >= 2:
                            labels[value] = text
                    if labels:
                        entry.option_labels.update(labels)
    except Exception:
        return


def _collect_widget_positions(reader) -> dict[str, tuple[int, Optional[list[float]]]]:
    """
    One-pass page walk: collect widget name → (page_num, bbox).
    Lightweight: only reads /T, /Rect, /Subtype — no AP stream resolution.
    """
    positions: dict[str, tuple[int, Optional[list[float]]]] = {}
    for page_num, page in enumerate(reader.pages, 1):
        try:
            annots = page.get("/Annots", [])
            if hasattr(annots, "get_object"):
                annots = annots.get_object()
            for ref in list(annots or [])[:200]:
                try:
                    ann = ref.get_object() if hasattr(ref, "get_object") else ref
                    if str(ann.get("/Subtype", "")) != "/Widget":
                        continue
                    name = ann.get("/T", "")
                    if not name:
                        parent_ref = ann.get("/Parent")
                        if parent_ref and hasattr(parent_ref, "get_object"):
                            parent = parent_ref.get_object()
                            name = parent.get("/T", "")
                    if hasattr(name, "get_object"):
                        name = name.get_object()
                    name = str(name).lstrip("/").strip()
                    if not name or name in positions:
                        continue
                    rect = ann.get("/Rect")
                    bbox: Optional[list[float]] = None
                    if rect:
                        try:
                            bbox = [float(x) for x in list(rect)[:4]]
                        except Exception:
                            pass
                    positions[name] = (page_num, bbox)
                except Exception:
                    continue
        except Exception:
            continue
    return positions


def _walk_field_tree(
    fields_array,
    seen: set[str],
    widget_positions: dict,
    depth: int = 0,
    inherited_ft=None,
    inherited_ff=None,
) -> list[FieldMapEntry]:
    """
    Recursive AcroForm field-tree traversal.
    Handles intermediate group nodes (no /FT, has /Kids).

    /FT and /Ff are *inheritable* attributes per the PDF spec: a terminal field
    may omit them and take the parent node's value. We thread the inherited
    values down the recursion so radio / checkbox / choice fields that rely on
    inheritance get their real type instead of silently defaulting to "text".
    """
    results: list[FieldMapEntry] = []
    for field_ref in list(fields_array):
        if len(seen) >= MAX_FIELDS:
            break
        try:
            f = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
            own_ft = f.get("/FT")
            ft_raw = own_ft if own_ft is not None else inherited_ft  # /FT inheritable
            has_kids = "/Kids" in f

            # /Ff (field flags: radio / pushbutton / multiselect bits) is
            # inheritable too — own flags else the parent's.
            own_ff = f.get("/Ff")
            ff_source = own_ff if own_ff is not None else inherited_ff

            # Non-terminal grouping node: no resolvable /FT but has kids →
            # recurse, propagating the inheritable /FT and /Ff to descendants.
            if ft_raw is None and has_kids and depth < 5:
                kids = f.get("/Kids", [])
                if hasattr(kids, "get_object"):
                    kids = kids.get_object()
                results.extend(_walk_field_tree(
                    kids, seen, widget_positions, depth + 1,
                    inherited_ft=ft_raw, inherited_ff=ff_source,
                ))
                continue

            name = f.get("/T", "")
            if hasattr(name, "get_object"):
                name = name.get_object()
            clean = str(name).lstrip("/").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)

            ft_str = str(ft_raw) if ft_raw else "/Tx"
            try:
                flags = int(str(ff_source).split(".")[0]) if ff_source is not None else 0
            except (ValueError, TypeError):
                flags = 0
            ftype = _classify_field_type(ft_str, flags) or "text"

            val = f.get("/V") or f.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()
            if val in ("/Off", "Off", "None", "none"):
                val = ""
            elif val.startswith("/"):
                val = val[1:]

            options: list[str] = []
            if ftype in ("select", "multiselect"):
                try:
                    raw_opts = f.get("/Opt", [])
                    for o in (raw_opts if isinstance(raw_opts, list) else []):
                        options.append(str(o[0]) if isinstance(o, (list, tuple)) else str(o))
                except Exception:
                    pass
            elif ftype == "radio":
                options = _radio_options_from_kids(f) if has_kids else []
                if not options:
                    # Some radio groups expose export values via /Opt on the
                    # parent instead of per-kid /AP/N — use it as a fallback.
                    try:
                        raw_opts = f.get("/Opt", [])
                        for o in (raw_opts if isinstance(raw_opts, list) else []):
                            v = str(o[0]) if isinstance(o, (list, tuple)) else str(o)
                            if v and v not in options:
                                options.append(v)
                    except Exception:
                        pass

            page_num, bbox = widget_positions.get(clean, (1, None))

            # ── Human-readable label: try /TU (tooltip/alternate text) first ──
            # /TU is the AcroForm standard field for user-visible labels.
            # Many professional PDF forms set it to a plain-language description.
            tu = f.get("/TU", "")
            if hasattr(tu, "get_object"):
                tu = tu.get_object()
            human_label = str(tu).strip() if tu else ""

            # Fall back to a cleaned version of the technical field name.
            # This strips prefixes (txtf/date/chk …) and splits camelCase
            # so the AI translator has meaningful context instead of noise.
            #
            # Also reject a WEAK /TU: some forms bake a junk tooltip (e.g. a
            # 2-char "we" placeholder) into /TU. Trusting it would surface "we"
            # as the question label, so when /TU is weak we prefer the cleaned
            # field name (e.g. "Startort_11" → "Startort"). _associate_labels_by_
            # position may still recover a better label from the page afterwards.
            if not human_label or human_label == clean or _is_weak_label(human_label):
                human_label = _clean_acroform_field_name(clean)

            results.append(FieldMapEntry(
                field_id=clean,               # unchanged — PDF filling relies on this
                original_label=human_label,   # now human-readable (not the technical ID)
                field_type=ftype,
                source_page=page_num,
                bbox=bbox,
                options=options,
                current_value=val,
                confidence=1.0,
                source="acroform",
                source_text=clean,            # keep raw widget name as grounding evidence
                reason="pdf_field",
            ))
        except Exception:
            continue
    return results


def _annotate_semantic_keys(fields: list[FieldMapEntry]) -> None:
    """
    Phase D/D3 — Best-effort post-extraction semantic_key inference.

    Walks each FieldMapEntry whose `semantic_key` is unset and tries to
    infer one from `original_label` via `infer_semantic_key()`. When a key
    is found, the priority-2 lookup (`lookup_semantic`) becomes available
    for that field, which means many common AcroForm labels (Vorname,
    Geburtsdatum, PLZ, Ort, …) get a multi-locale verified question
    without ever calling the AI translator.

    Safe and additive: never overwrites an existing semantic_key (e.g. set
    by a verified template), never raises, never changes field_id.
    """
    try:
        from app.services.semantic_questions import infer_semantic_key
    except Exception:
        return
    for f in fields:
        if f.semantic_key:
            continue
        try:
            key = infer_semantic_key(f.original_label or "")
        except Exception:
            key = None
        if key:
            f.semantic_key = key


def extract_acroform_fields(pdf_bytes: bytes) -> list[FieldMapEntry]:
    """
    Full AcroForm extraction with page numbers and coordinates.
    Returns ground-truth fields keyed by the exact PDF widget name.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

        root = reader.trailer.get("/Root")
        if root is None:
            return []
        if hasattr(root, "get_object"):
            root = root.get_object()
        acroform = root.get("/AcroForm")
        if acroform is None:
            return []
        if hasattr(acroform, "get_object"):
            acroform = acroform.get_object()
        fields_arr = acroform.get("/Fields", [])
        if hasattr(fields_arr, "get_object"):
            fields_arr = fields_arr.get_object()

        widget_positions = _collect_widget_positions(reader)

        seen: set[str] = set()
        return _walk_field_tree(fields_arr, seen, widget_positions)

    except Exception:
        return []


# ── Flat PDF extraction (pdfplumber text + layout) ────────────────────────────

_RE_BLANK_AFTER_COLON   = re.compile(r"^(.{2,80}):\s*_{3,}")
_RE_BLANKS_THEN_UNIT    = re.compile(r"^_{3,}\s+(.{2,60})")
_RE_UNICODE_CHECKBOX    = re.compile(r"(□|☐|\[\s*\]|\(\s*\))\s*(.{2,60})")
_RE_LETTER_CHECKBOX     = re.compile(r"^([A-Z])\s+(Leistung\w+\s.{5,80})")
_RE_ORT_DATUM           = re.compile(r"Ort.{0,5}Datum", re.IGNORECASE)
_RE_UNTERSCHRIFT        = re.compile(r"Unterschrift", re.IGNORECASE)
_RE_STANDALONE_LABEL    = re.compile(r"^([A-ZÄÖÜ][^:!?)]{2,120}[^:!?).])$")
_RE_BETRAG_KM           = re.compile(r"betr[äa]gt\s+km", re.IGNORECASE)

_SKIP_PHRASES = {
    "hinweis", "bitte", "gemeinschaftlichen", "anspruchsberechtigte",
    "ich versichere", "ich bin damit", "auf ihre rechte", "rechtsgrundlage",
    "hierf", "der/die beauftragte", "die daten", "impressum", "datenschutz",
    "jobcenter", "bundesagentur", "(bitte", "anlage",
    "freizeiten", "jugendamt", "erhoben", "sgb", "bkgg", "datenschutz-grundverordnung",
    "sozialgeheimnis", "sozialgesetz", "verarbeitet", "speicher", "widerrufen",
    "einverstanden", "leistungsanbieter", "pluxee",
}


def _skip(label: str) -> bool:
    lo = label.lower().strip()
    if len(lo) < 3 or len(lo) > 120:
        return True
    for phrase in _SKIP_PHRASES:
        if phrase in lo:
            return True
    if re.match(r'^[\d\s\.,\-\(\)%€/]+$', lo):
        return True
    return False


def _make_fid(label: str) -> str:
    """Stable field_id from a label string."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower().strip())[:80].strip("_")


def extract_flat_fields(pdf_bytes: bytes) -> list[FieldMapEntry]:
    """
    Field detection for flat (non-fillable) PDFs using pdfplumber text extraction.

    Every returned field_id is grounded in a real line of text from the PDF.
    source_text is the exact matched PDF line — the evidence for why this question exists.
    No fields are invented from the topic of the document.
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    results: list[FieldMapEntry] = []
    seen: set[str] = set()
    letter_checkbox_options: list[str] = []
    letter_checkbox_source_lines: list[str] = []

    def _add(label: str, ftype: str, page: int,
             opts: Optional[list[str]] = None, source_text: str = "") -> None:
        fid = _make_fid(label)
        if not fid or fid in seen or _skip(label):
            return
        seen.add(fid)
        results.append(FieldMapEntry(
            field_id=fid,
            original_label=label.strip(),
            field_type=ftype,
            source_page=page,
            options=opts or [],
            confidence=0.75,
            source="pdfplumber",
            source_text=source_text or label.strip(),  # exact PDF text = grounding evidence
            reason="pdf_field",
        ))

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    continue

                lines = text.split("\n")
                for i, raw_line in enumerate(lines):
                    line = raw_line.strip()
                    if not line or len(results) >= MAX_FIELDS:
                        continue

                    # 1. "Label: ___" — explicit blank after colon
                    m = _RE_BLANK_AFTER_COLON.match(line)
                    if m:
                        _add(m.group(1).strip(), "text", page_num, source_text=line)
                        continue

                    # 2. "_____ EUR / km" — fill-in amount or distance
                    m = _RE_BLANKS_THEN_UNIT.match(line)
                    if m:
                        _add(m.group(1).strip(), "number", page_num, source_text=line)
                        continue

                    # 3. "beträgt km." — distance fill-in
                    if _RE_BETRAG_KM.search(line):
                        _add("Strecke_km", "number", page_num, source_text=line)
                        continue

                    # 4. "□ Option" — unicode checkbox
                    if _RE_UNICODE_CHECKBOX.search(line):
                        for m in _RE_UNICODE_CHECKBOX.finditer(line):
                            _add(m.group(2).strip(), "checkbox", page_num, source_text=line)
                        continue

                    # 5. "A Leistungen für …" — letter-prefixed checkbox group
                    m = _RE_LETTER_CHECKBOX.match(line)
                    if m:
                        full_label = m.group(0)
                        short_label = re.split(r'\(', full_label, 1)[0].strip()
                        letter_prefix = m.group(1)
                        option_label = f"{letter_prefix}: {short_label[2:].strip()}"[:100]
                        letter_checkbox_options.append(option_label)
                        letter_checkbox_source_lines.append(line)
                        continue

                    # 6. "Ort/Datum" — date+place
                    if _RE_ORT_DATUM.search(line):
                        _add("Ort_Datum", "text", page_num, source_text=line)
                        continue

                    # 7. "Unterschrift" — signature line
                    if _RE_UNTERSCHRIFT.search(line):
                        _add("Unterschrift", "signature", page_num, source_text=line)
                        continue

                    # 8. Standalone title-case label line ("Name, Vorname")
                    if _RE_STANDALONE_LABEL.match(line) and not _skip(line):
                        next_lines = [l.strip() for l in lines[i+1:i+3] if l.strip()]
                        next_is_label = (
                            not next_lines
                            or _RE_STANDALONE_LABEL.match(next_lines[0])
                            or len(next_lines[0]) < 6
                        )
                        if next_is_label:
                            _add(line, "text", page_num, source_text=line)

    except Exception:
        pass

    # Flush letter-checkbox group
    if letter_checkbox_options and len(letter_checkbox_options) >= 2:
        fid = "leistungsart_auswahl"
        if fid not in seen:
            seen.add(fid)
            source = " | ".join(letter_checkbox_source_lines[:3])
            results.append(FieldMapEntry(
                field_id=fid,
                original_label="Beantragte Leistung (A–G)",
                field_type="multiselect",
                source_page=1,
                options=letter_checkbox_options,
                confidence=0.75,
                source="pdfplumber",
                source_text=source,
                reason="pdf_field",
            ))

    return results


# ── Full-text extraction for fingerprinting ───────────────────────────────────

def _extract_full_text(pdf_bytes: bytes) -> str:
    """
    Extract concatenated text from all pages (up to 15 pages).
    Used only for template fingerprinting — not for field extraction.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts = []
            for page in pdf.pages[:15]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    pass
            return "\n".join(parts)
    except Exception:
        return ""


# ── Level-2 positional label association ──────────────────────────────────────

# Generic auto-generated widget names that carry no human meaning. When a
# field's label matches one of these (optionally followed by an index), we try
# to recover a real label from the page text next to the widget.
_WEAK_LABEL_RE = re.compile(
    r"^(text\s*field|textfeld|text|field|feld|checkbox|check\s*box|"
    r"kontrollk[aä]stchen|optionfield|option|undefined|untitled|comb)"
    r"[\s\-_.]*\d*$",
    re.IGNORECASE,
)

# Distance caps (PDF points) for matching a label to a widget.
_LABEL_ABOVE_MAX_GAP = 38.0   # label sits just above the box
_LABEL_LEFT_MAX_GAP  = 240.0  # label sits to the left, same row
_LABEL_MIN_OVERLAP   = 3.0    # required x- (above) or y- (left) overlap


def _is_weak_label(label: str) -> bool:
    """
    True when a label carries no human meaning — empty, too short, pure
    digits/punctuation, or a generic widget name like 'Textfield' / 'Checkbox-3'.
    Such labels are candidates for positional recovery from the page text.
    """
    lo = (label or "").strip()
    if len(lo) < 3:
        return True
    if re.fullmatch(r"[\d\s.\-_/]+", lo):
        return True
    if _WEAK_LABEL_RE.match(lo):
        return True
    return False


def _associate_labels_by_position(fields: list[FieldMapEntry], pdf_bytes: bytes) -> None:
    """
    Level-2 enrichment: for AcroForm fields whose label is weak (a generic
    widget name like 'Textfield'), recover a human label from the nearest page
    text. On German forms the visible label sits just ABOVE the box (common) or
    to its LEFT.

    Coordinates: widget bboxes are PDF points, bottom-left origin (y up);
    pdfplumber words are top-left origin (y down). We convert each widget to
    top-left via the page height before matching.

    Safe + additive: only `original_label` is changed (never field_id, type,
    bbox, confidence). Fields without a bbox or without a good match are left
    untouched, so this can never make labels worse than today.
    """
    weak = [f for f in fields if f.bbox and _is_weak_label(f.original_label)]
    if not weak:
        return
    try:
        import pdfplumber
    except Exception:
        return

    by_page: dict[int, list[FieldMapEntry]] = {}
    for f in weak:
        by_page.setdefault(f.source_page, []).append(f)

    def _hgap_ok(a0, a1, b0, b1):
        return min(a1, b1) - max(a0, b0) > _LABEL_MIN_OVERLAP

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page_fields in by_page.items():
                idx = page_num - 1
                if idx < 0 or idx >= len(pdf.pages):
                    continue
                page = pdf.pages[idx]
                H = float(page.height)
                try:
                    words = page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
                except Exception:
                    words = []
                # Keep only label-like words (drops instructions, page numbers, …).
                cand = [
                    w for w in words
                    if (w.get("text") or "").strip() and not _skip((w.get("text") or "").strip())
                ]
                if not cand:
                    continue

                for f in page_fields:
                    x0, y0, x1, y1 = f.bbox
                    w_x0, w_x1 = min(x0, x1), max(x0, x1)
                    w_top = H - max(y0, y1)   # flip bottom-left → top-left
                    w_bot = H - min(y0, y1)

                    # 1) Label ABOVE: words whose bottom is just above the box top
                    #    and which overlap the box horizontally. Take the nearest
                    #    line, then join its overlapping words left-to-right.
                    above = [
                        w for w in cand
                        if float(w["bottom"]) <= w_top + 2
                        and (w_top - float(w["bottom"])) <= _LABEL_ABOVE_MAX_GAP
                        and _hgap_ok(w_x0, w_x1, float(w["x0"]), float(w["x1"]))
                    ]
                    label = ""
                    if above:
                        nearest_bottom = max(float(w["bottom"]) for w in above)
                        line = sorted(
                            (w for w in above if abs(float(w["bottom"]) - nearest_bottom) <= 2.5),
                            key=lambda w: float(w["x0"]),
                        )
                        label = " ".join((w.get("text") or "").strip() for w in line).strip()

                    # 2) else Label LEFT: nearest word on the same row to the left.
                    if not label:
                        left = [
                            w for w in cand
                            if float(w["x1"]) <= w_x0 + 2
                            and (w_x0 - float(w["x1"])) <= _LABEL_LEFT_MAX_GAP
                            and _hgap_ok(w_top, w_bot, float(w["top"]), float(w["bottom"]))
                        ]
                        if left:
                            anchor = max(left, key=lambda w: float(w["x1"]))
                            row = sorted(
                                (w for w in left if abs(float(w["top"]) - float(anchor["top"])) <= 2.5),
                                key=lambda w: float(w["x0"]),
                            )
                            label = " ".join((w.get("text") or "").strip() for w in row).strip()

                    label = label.rstrip(":：").strip()
                    if label and len(label) >= 2:
                        f.original_label = label[:90]
    except Exception:
        return


# ── Section-header association (Feature D) ────────────────────────────────────
# A field name like "Tag" or "Ort" is meaningless out of context. The real
# meaning lives in the numbered/bold section header above it ("Datum des
# Schulausflugstages", "Name und Anschrift der Schule"). We detect those
# headers and attach the nearest one above each field, giving the AI translator
# the context it needs to write a correct question instead of guessing "your".

_SECTION_NUM_RE = re.compile(r"^\s*\d{1,2}[\s.):]+(.+)$")
_SECTION_MAX_GAP = 230.0    # a field may sit at most this far below its header (pts)
_SECTION_MAX_LEN = 70


def _median(nums: list[float]) -> float:
    vals = sorted(v for v in nums if v)
    if not vals:
        return 0.0
    n = len(vals)
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2.0


_COLUMN_SPLIT_GAP = 40.0   # horizontal gap (pts) that separates two columns


def _group_words_into_lines(words: list[dict]) -> list[dict]:
    """
    Bucket pdfplumber words into visual lines with geometry + font info.

    A row is further split into column SEGMENTS wherever two consecutive words
    are separated by more than _COLUMN_SPLIT_GAP, so side-by-side section headers
    ("2 Klasse    3 Datum …") become two distinct lines instead of one merged blob.
    """
    rows: dict[int, list[dict]] = {}
    for w in words:
        key = round(float(w.get("top", 0.0)) / 3.0)   # ~3pt buckets
        rows.setdefault(key, []).append(w)
    lines: list[dict] = []
    for ws in rows.values():
        ws.sort(key=lambda w: float(w.get("x0", 0.0)))
        segments: list[list[dict]] = []
        seg: list[dict] = []
        prev_x1: Optional[float] = None
        for w in ws:
            if prev_x1 is not None and float(w.get("x0", 0.0)) - prev_x1 > _COLUMN_SPLIT_GAP:
                segments.append(seg)
                seg = []
            seg.append(w)
            prev_x1 = float(w.get("x1", 0.0))
        if seg:
            segments.append(seg)
        for s in segments:
            text = " ".join((w.get("text") or "").strip() for w in s).strip()
            if not text:
                continue
            size = max((float(w.get("size", 0.0)) for w in s), default=0.0)
            fontname = next((str(w.get("fontname")) for w in s if w.get("fontname")), "")
            top = min((float(w.get("top", 0.0)) for w in s), default=0.0)
            x0 = min((float(w.get("x0", 0.0)) for w in s), default=0.0)
            x1 = max((float(w.get("x1", 0.0)) for w in s), default=0.0)
            lines.append({"top": top, "x0": x0, "x1": x1, "text": text,
                          "size": size, "fontname": fontname})
    lines.sort(key=lambda ln: ln["top"])
    return lines


def _clean_section_title(text: str) -> str:
    t = text.strip()
    m = _SECTION_NUM_RE.match(t)
    if m:
        t = m.group(1).strip()
    return t[:_SECTION_MAX_LEN].strip()


def _associate_section_titles(fields: list[FieldMapEntry], pdf_bytes: bytes) -> None:
    """
    Attach the section header each field sits under to entry.section_title.

    Header heuristic (any of): a numbered line ("3 Datum …"), a bold line, or a
    line set noticeably larger than the page's body text. Each field is matched
    to the nearest qualifying header above it within _SECTION_MAX_GAP points.

    Safe + additive: only sets section_title; never touches field_id, type, or
    options. Fields with no header above keep section_title=None (no change in
    behavior). pdfplumber coords are top-left; widget bboxes are bottom-left, so
    we flip via page height before comparing.
    """
    targets = [f for f in fields if f.bbox]
    if not targets:
        return
    try:
        import pdfplumber
    except Exception:
        return

    by_page: dict[int, list[FieldMapEntry]] = {}
    for f in targets:
        by_page.setdefault(f.source_page, []).append(f)

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page_fields in by_page.items():
                idx = page_num - 1
                if idx < 0 or idx >= len(pdf.pages):
                    continue
                page = pdf.pages[idx]
                H = float(page.height)
                try:
                    words = page.extract_words(
                        use_text_flow=False, keep_blank_chars=False,
                        extra_attrs=["size", "fontname"],
                    ) or []
                except Exception:
                    words = []
                lines = _group_words_into_lines(words)
                if not lines:
                    continue
                body_size = _median([ln["size"] for ln in lines])

                def _looks_like_sentence(t: str) -> bool:
                    # Section headers are terse labels, not prose. Instruction
                    # paragraphs (often bold on German forms) end with sentence
                    # punctuation or run long — exclude them.
                    return t.endswith((",", ".", ";", ":")) or len(t.split()) > 9

                # Strip a trailing parenthetical ("(inkl. …)", "(Bei …)") so a
                # header like "4 Anzahl … (inkl. Lehrkraft …)" isn't rejected by
                # the length cap and resolves to its core title.
                def _core(t: str) -> str:
                    return re.sub(r"\s*\(.*$", "", t).strip()

                numbered: list[tuple] = []
                soft: list[tuple] = []
                for ln in lines:
                    txt = _core(ln["text"].strip())
                    if not txt or len(txt) > _SECTION_MAX_LEN or _looks_like_sentence(txt):
                        continue
                    title = _clean_section_title(txt)
                    # Require a real word — drops junk like "= 6" or lone numbers.
                    if len(title) < 3 or not re.search(r"[A-Za-zÄÖÜäöüß]{3,}", title):
                        continue
                    geom = (ln["top"], float(ln["x0"]), float(ln["x1"]), title)
                    if _SECTION_NUM_RE.match(txt):
                        numbered.append(geom)
                        continue
                    is_bold = "bold" in (ln["fontname"] or "").lower()
                    is_large = body_size > 0 and ln["size"] >= body_size * 1.12
                    if is_bold or is_large:
                        soft.append(geom)

                # Numbered headers ("3 Datum …") are an unambiguous structural
                # signal. When a page has them, trust ONLY those and ignore the
                # bold/large fallback (bold instruction paragraphs would mislead).
                headers = numbered or soft
                if not headers:
                    continue

                for f in page_fields:
                    x0, y0, x1, y1 = f.bbox
                    f_top = H - max(y0, y1)        # field top, flipped to top-left
                    fx0, fx1 = min(x0, x1), max(x0, x1)
                    above = [
                        (f_top - htop, hx0, hx1, ht)
                        for (htop, hx0, hx1, ht) in headers
                        if 0 <= f_top - htop <= _SECTION_MAX_GAP
                    ]
                    if not above:
                        continue
                    # Column-aware: prefer headers whose x-range overlaps the
                    # field's (handles side-by-side sections like "2 Klasse |
                    # 3 Datum"); else fall back to all candidates. Then nearest.
                    overlap = [c for c in above if min(c[2], fx1) - max(c[1], fx0) > -2.0]
                    best = min(overlap or above, key=lambda c: c[0])[3]
                    if best and best.lower() != (f.original_label or "").strip().lower():
                        f.section_title = best
    except Exception:
        return


# ── Main entry point ───────────────────────────────────────────────────────────

def route_document(pdf_bytes: bytes) -> DocumentRoute:
    """
    Decide which extraction engine to run BEFORE running it.

    Single source of truth for support_level routing. Returns the routing
    decision so callers can log it, branch on it, and test it independently
    of the extraction engines themselves.
    """
    # Lazy import to avoid circular dependency at module load time.
    from app.services.form_templates import find_matching_template

    full_text = _extract_full_text(pdf_bytes)
    pdf_type, total_pages = detect_pdf_type(pdf_bytes)

    template = find_matching_template(full_text)
    if template:
        return DocumentRoute(
            support_level=1,
            extraction_source="verified_template",
            pdf_type="verified_template",
            template_id=template.template_id,
            total_pages=total_pages,
        )

    if pdf_type == "acroform":
        return DocumentRoute(
            support_level=2,
            extraction_source="acroform",
            pdf_type="acroform",
            total_pages=total_pages,
        )
    if pdf_type == "flat":
        return DocumentRoute(
            support_level=3,
            extraction_source="pdfplumber",
            pdf_type="flat",
            total_pages=total_pages,
        )
    # scanned or unknown
    return DocumentRoute(
        support_level=4,
        extraction_source="auto",
        pdf_type=pdf_type,
        total_pages=total_pages,
    )


def extract_field_map(pdf_bytes: bytes) -> ExtractionResult:
    """
    Full pipeline entry point.

    Routes via route_document() then runs the matching extraction engine.
      1. Verified template — hand-verified field map (confidence=1.0)
      2. AcroForm — programmatically fillable PDFs
      3. pdfplumber — flat PDFs with regex heuristics
      4. Scanned/unknown — empty field list (Level 4 not yet supported)
    """
    route = route_document(pdf_bytes)

    # Level 1: verified template
    if route.support_level == 1:
        from app.services.form_templates import find_template_by_id
        template = find_template_by_id(route.template_id) if route.template_id else None
        fields = template.get_field_map() if template else []
        return ExtractionResult(
            pdf_type=route.pdf_type,
            fields=fields,
            total_pages=route.total_pages,
            template_id=route.template_id,
            extraction_source=route.extraction_source,
            support_level=route.support_level,
        )

    # Level 2: AcroForm — may degrade to pdfplumber if widgets are empty
    if route.support_level == 2:
        fields = extract_acroform_fields(pdf_bytes)
        # Recover human labels for generically-named widgets ('Textfield', …)
        # from nearby page text BEFORE semantic-key inference runs.
        _associate_labels_by_position(fields, pdf_bytes)
        # Feature E — recover real choice labels (e.g. "Einzelfahrt"/"Tageskarte")
        # for radio groups whose options are bare export values ("0"/"1").
        _associate_option_labels(fields, pdf_bytes)
        # Feature D — attach each field's section header ("Datum des
        # Schulausflugstages", …) so the AI translator has real context.
        _associate_section_titles(fields, pdf_bytes)
        # Phase D/D3 — inferring semantic_key from the cleaned label lets the
        # priority-2 layer fire for AcroForm fields. Skipped for Level 1
        # (templates set semantic_key explicitly) and Level 3+ (handled below).
        _annotate_semantic_keys(fields)
        if not fields:
            fields = extract_flat_fields(pdf_bytes)
            effective_type    = "flat" if fields else "acroform"
            extraction_source = "pdfplumber" if fields else "acroform"
            support_level     = 3 if fields else 2
        else:
            effective_type    = "acroform"
            extraction_source = "acroform"
            support_level     = 2
        return ExtractionResult(
            pdf_type=effective_type,
            fields=fields,
            total_pages=route.total_pages,
            extraction_source=extraction_source,
            support_level=support_level,
        )

    # Level 3: flat PDF
    if route.support_level == 3:
        fields = extract_flat_fields(pdf_bytes)
        return ExtractionResult(
            pdf_type="flat",
            fields=fields,
            total_pages=route.total_pages,
            extraction_source="pdfplumber",
            support_level=3,
        )

    # Level 4: scanned/unknown — no fields extracted
    return ExtractionResult(
        pdf_type=route.pdf_type,
        fields=[],
        total_pages=route.total_pages,
        extraction_source="auto",
        support_level=4,
    )


# ── Anti-hallucination validator ───────────────────────────────────────────────

def validate_no_hallucinations(
    field_map: list[FieldMapEntry],
    translations: dict[str, dict],
    user_language: str = "en",
) -> HallucinationReport:
    """
    Validates AI-returned translations against the extracted field map.

    Rules:
    - Any key in `translations` NOT in `field_map` → INVENTED → DISCARDED
    - Any field_id in `field_map` NOT in `translations` → MISSING → BACKFILLED
      using deterministic table first, then original_label.

    Returns HallucinationReport with a clean, safe translations dict.
    """
    from app.services.question_translator import get_deterministic_translation

    extracted_ids = {f.field_id for f in field_map}
    returned_ids  = set(translations.keys())

    invented = returned_ids - extracted_ids
    missing  = extracted_ids - returned_ids

    cleaned: dict[str, dict] = {
        k: v for k, v in translations.items() if k in extracted_ids
    }

    field_by_id = {f.field_id: f for f in field_map}
    for fid in missing:
        entry = field_by_id[fid]
        # Try deterministic translation before falling back to raw German label
        question = (
            get_deterministic_translation(entry.original_label, user_language)
            or entry.original_label
        )
        cleaned[fid] = {
            "question": question,
            "explanation": "",
            "translated_options": {opt: opt for opt in entry.options},
        }

    return HallucinationReport(
        is_clean=len(invented) == 0,
        invented=sorted(invented),
        missing=sorted(missing),
        cleaned_translations=cleaned,
    )


# ── Field definition builder ──────────────────────────────────────────────────

def field_map_to_defs(
    field_map: list[FieldMapEntry],
    validated_translations: dict[str, dict],
    prefilled_ids: set[str],
    user_language: str,
    document_language: str,
) -> list:
    """
    Convert FieldMapEntry list + validated translations → list of FieldDefinition dicts.
    One FieldDefinition per FieldMapEntry — no extras, no omissions.

    Confidence gate:
        conf >= 0.90  → show_question=True,  needs_review=False
        0.70 ≤ conf   → show_question=True,  needs_review=True
        conf < 0.70   → show_question=False  (question blocked, not shown to user)
    """
    from app.schemas.document import FieldDefinition, FieldOption

    from app.schemas.document import GuidanceText

    defs = []
    for i, entry in enumerate(field_map, 1):
        tr = validated_translations.get(entry.field_id, {})
        tr_opts = tr.get("translated_options", {})
        # Option label priority: AI/verified translation → recovered German
        # label (Feature E) → the raw export value as a last resort. This is why
        # a radio whose PDF options are "0"/"1" can still show "Einzelfahrt"/
        # "Tageskarte" instead of meaningless codes.
        options = [
            FieldOption(value=v, label=(tr_opts.get(v) or entry.option_labels.get(v) or v))
            for v in entry.options
        ]

        show_question = entry.confidence >= CONF_SHOW_MIN
        needs_review  = show_question and (
            entry.confidence < CONF_REVIEW_MIN or entry.source != "acroform"
        )

        guidance = None
        if isinstance(entry.guidance, dict):
            try:
                guidance = GuidanceText(**entry.guidance)
            except Exception:
                guidance = None

        # ── Resolve question text with explicit source tracking ──────────────────
        # The _source key is set by process_pdf.py when pre-resolving fields.
        # field_map_to_defs acts as a final safety net for anything that slipped through.
        resolved_source = tr.get("_source", "")

        if resolved_source in ("verified", "semantic", "deterministic") and tr.get("question"):
            # Already resolved at a high-quality level upstream — trust it
            raw_question = tr["question"]
        else:
            # Apply quality gates to AI or unknown-source questions
            raw_question = tr.get("question") or ""

            # Gate 1: empty or technical ID
            if not raw_question or _looks_like_technical_id(raw_question):
                from app.services.question_translator import get_deterministic_translation
                raw_question = (
                    get_deterministic_translation(entry.original_label, user_language)
                    or entry.original_label
                )
                if raw_question != tr.get("question", ""):
                    resolved_source = "deterministic" if raw_question != entry.original_label else "label"

            # Gate 2: AI returned source-language label unchanged
            elif raw_question == entry.original_label and user_language != document_language:
                from app.services.question_translator import get_deterministic_translation
                raw_question = (
                    get_deterministic_translation(entry.original_label, user_language)
                    or entry.original_label
                )
                if raw_question != entry.original_label:
                    resolved_source = "deterministic"
                else:
                    resolved_source = "label"

        if not resolved_source:
            resolved_source = "ai" if tr.get("question") else "label"

        # Build explanation: prefer AI's help field > explanation > empty
        raw_explanation = (
            tr.get("help") or tr.get("explanation", "")
        )

        # Build example and format from the translation dict
        tr_example = tr.get("example", "")
        tr_format  = tr.get("format", "")

        # ── Populate all Tier-A locales in question dict ────────────────────
        # The frontend uses field.question[selected_locale] as the primary
        # source of truth. To make Level 1 language switches instant (no
        # reprocessing) we pre-fill every Tier-A locale here using the same
        # priority chain as the user's locale: verified > semantic > deterministic.
        # Anything missing falls through to the user's resolved text and finally
        # the original German label (never English silently for Tier-A).
        TIER_A = ("en", "de", "fr", "ar", "tr", "sq")
        question_dict: dict[str, str] = {user_language: raw_question}

        from app.services.question_translator import get_deterministic_translation
        from app.services.verified_questions import lookup_verified_strict as _lv_strict
        from app.services.semantic_questions import lookup_semantic_strict as _ls_strict

        for loc in TIER_A:
            if loc in question_dict and question_dict[loc]:
                continue
            # Priority 1: verified
            vq = _lv_strict(entry.field_id, entry.original_label, loc)
            if vq and vq.get("question"):
                question_dict[loc] = vq["question"]
                continue
            # Priority 2: semantic
            if entry.semantic_key:
                sem = _ls_strict(entry.semantic_key, loc)
                if sem and sem.get("question"):
                    question_dict[loc] = sem["question"]
                    continue
            # Priority 3: deterministic
            det = get_deterministic_translation(entry.original_label, loc)
            if det:
                question_dict[loc] = det
                continue

        # Document-language fallback (raw label) so the original PDF wording
        # remains visible as secondary text on the review page.
        if document_language not in question_dict:
            question_dict[document_language] = entry.original_label

        # ── Guidance injection — Tier-A complete ────────────────────────────
        # Every Tier-A locale must have help/example/format text whenever
        # verified_questions has it, regardless of whether the template
        # itself authored a per-locale GuidanceText. Strategy:
        #   1. Start from the template's GuidanceText (may have en/de only).
        #   2. For each Tier-A locale, look up the verified entry. If
        #      verified has `help`/`example`/`format` for that locale AND
        #      the corresponding GuidanceText slot is missing it, fill it in.
        #   3. Always include the user_language slot (sourced from tr).
        # Result: BuT (template authored en/de only) gains fr/ar/tr/sq help
        # via verified_questions; KG1 (already complete) is unchanged.
        plain_dict: dict[str, str] = {}
        format_dict: dict[str, str] = {}
        example_dict: dict[str, str] = {}
        why_dict: dict[str, str] = {}
        where_dict: dict[str, str] = {}
        required_docs_dict: dict[str, list[str]] = {}
        common_mistakes_dict: dict[str, list[str]] = {}
        warning_dict: dict[str, str] = {}

        if guidance is not None:
            plain_dict.update(guidance.plain_language or {})
            format_dict.update(guidance.format_hint or {})
            example_dict.update(guidance.example or {})
            why_dict.update(guidance.why_needed or {})
            where_dict.update(guidance.where_to_find or {})
            required_docs_dict.update(guidance.required_documents or {})
            common_mistakes_dict.update(guidance.common_mistakes or {})
            warning_dict.update(guidance.warning or {})

        # Always seed user_language from this run's tr (AI/verified/semantic)
        if raw_explanation:
            plain_dict.setdefault(user_language, raw_explanation)
        if tr_format:
            format_dict.setdefault(user_language, tr_format)
        if tr_example:
            example_dict.setdefault(user_language, tr_example)

        # Tier-A backfill from verified_questions per-locale entries
        for loc in TIER_A:
            vq = _lv_strict(entry.field_id, entry.original_label, loc)
            if not vq:
                continue
            v_help = (vq.get("help") or "").strip()
            v_example = (vq.get("example") or "").strip()
            v_format = (vq.get("format") or "").strip()
            if v_help and not plain_dict.get(loc):
                plain_dict[loc] = v_help
            if v_example and not example_dict.get(loc):
                example_dict[loc] = v_example
            if v_format and not format_dict.get(loc):
                format_dict[loc] = v_format

        any_guidance = (
            plain_dict or format_dict or example_dict or why_dict or where_dict
            or required_docs_dict or common_mistakes_dict or warning_dict
        )
        effective_guidance: Optional[GuidanceText] = None
        if any_guidance:
            try:
                effective_guidance = GuidanceText(
                    plain_language=plain_dict,
                    format_hint=format_dict,
                    example=example_dict,
                    why_needed=why_dict,
                    where_to_find=where_dict,
                    required_documents=required_docs_dict,
                    common_mistakes=common_mistakes_dict,
                    warning=warning_dict,
                )
            except Exception:
                effective_guidance = None

        # ── Explanation dict — Tier-A complete ──────────────────────────────
        # Mirrors plain_dict so QuestionCard.explanation_text and
        # GuidancePanel.plain_language stay in sync.
        explanation_dict = dict(plain_dict)

        defs.append(FieldDefinition(
            key=entry.field_id,
            question=question_dict,
            explanation=explanation_dict,
            input_type=entry.field_type,
            options=options,
            original_label=entry.original_label,
            document_language=document_language,
            source_page=entry.source_page,
            order=i,
            is_prefilled=(entry.field_id in prefilled_ids),
            confidence=entry.confidence,
            needs_review=needs_review,
            show_question=show_question,
            source_text=entry.source_text,
            reason=entry.reason,
            question_type=entry.reason,
            guidance=effective_guidance,
            semantic_key=entry.semantic_key,
            question_source=resolved_source,
            condition=entry.condition,
        ))
    return defs


# ── Analysis report builder ────────────────────────────────────────────────────

def build_analysis_report(
    extraction: ExtractionResult,
    field_defs: list,
    hallucination_report: HallucinationReport,
) -> AnalysisReport:
    """
    Compute accuracy metrics for the extraction result.
    Called after field_map_to_defs() to report on what was shown vs blocked.
    """
    field_count  = len(extraction.fields)
    shown        = sum(1 for d in field_defs if getattr(d, "show_question", True))
    blocked      = field_count - shown
    low_conf     = sum(
        1 for f in extraction.fields
        if CONF_SHOW_MIN <= f.confidence < CONF_REVIEW_MIN
    )
    invented_ct  = len(hallucination_report.invented)

    coverage_pct = round(shown / field_count * 100) if field_count > 0 else 0

    return AnalysisReport(
        pdf_type=extraction.pdf_type,
        total_pages=extraction.total_pages,
        field_count=field_count,
        questions_shown=shown,
        questions_blocked=blocked,
        low_confidence_fields=low_conf,
        invented_questions_removed=invented_ct,
        coverage_rate=f"{coverage_pct}%",
        grounding_rate="100%",   # guaranteed by validate_no_hallucinations
        grounding_ok=True,
    )
