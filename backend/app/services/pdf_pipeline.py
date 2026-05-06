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
      └─[5] build_field_defs()  →  list[FieldDefinition]

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
    current_value: str = ""     # pre-filled value if any
    confidence: float = 1.0     # 1.0=AcroForm, 0.8=pdfplumber layout, 0.5=ocr
    source: str = "acroform"    # "acroform" | "pdfplumber" | "ocr"
    required: bool = False


@dataclass
class ExtractionResult:
    pdf_type: str                           # "acroform" | "flat" | "scanned" | "unknown"
    fields: list[FieldMapEntry]
    total_pages: int = 0
    error: Optional[str] = None


@dataclass
class HallucinationReport:
    """
    Result of validating AI-returned translations against the extracted field map.
    """
    is_clean: bool                  # True if AI invented no fields
    invented: list[str]             # field_ids AI returned that don't exist in field_map
    missing: list[str]              # field_ids in field_map that AI didn't translate
    cleaned_translations: dict      # safe dict: invented removed, missing backfilled


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

        # Check for AcroForm with at least one field
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

        # Check for readable text
        total_chars = 0
        for page in reader.pages[:5]:
            try:
                total_chars += len((page.extract_text() or "").strip())
            except Exception:
                pass

        return ("flat" if total_chars > 200 else "scanned"), page_count

    except Exception as e:
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


def _collect_widget_positions(reader) -> dict[str, tuple[int, Optional[list[float]]]]:
    """
    One-pass page walk: collect widget name → (page_num, bbox).
    Lightweight: only reads /T, /Rect, /Subtype — no AP stream resolution.
    Called once per document, O(pages × annotations).
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
) -> list[FieldMapEntry]:
    """
    Recursive AcroForm field-tree traversal.
    Handles intermediate group nodes (no /FT, has /Kids).
    """
    results: list[FieldMapEntry] = []
    for field_ref in list(fields_array):
        if len(seen) >= MAX_FIELDS:
            break
        try:
            f = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
            ft_raw = f.get("/FT")
            has_kids = "/Kids" in f

            # Intermediate group node — recurse
            if ft_raw is None and has_kids and depth < 5:
                kids = f.get("/Kids", [])
                if hasattr(kids, "get_object"):
                    kids = kids.get_object()
                results.extend(_walk_field_tree(kids, seen, widget_positions, depth + 1))
                continue

            # Leaf widget — extract name
            name = f.get("/T", "")
            if hasattr(name, "get_object"):
                name = name.get_object()
            clean = str(name).lstrip("/").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)

            # Field type
            ft_str = str(ft_raw) if ft_raw else "/Tx"
            try:
                flags = int(str(f.get("/Ff", "0")).split(".")[0] or "0")
            except (ValueError, TypeError):
                flags = 0
            ftype = _classify_field_type(ft_str, flags) or "text"

            # Current / default value
            val = f.get("/V") or f.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()
            if val in ("/Off", "Off", "None", "none"):
                val = ""
            elif val.startswith("/"):
                val = val[1:]

            # Options (choice fields)
            options: list[str] = []
            if ftype in ("select", "multiselect"):
                try:
                    raw_opts = f.get("/Opt", [])
                    for o in (raw_opts if isinstance(raw_opts, list) else []):
                        options.append(str(o[0]) if isinstance(o, (list, tuple)) else str(o))
                except Exception:
                    pass
            elif ftype == "radio" and has_kids:
                options = _radio_options_from_kids(f)

            # Page + bbox from the widget position map
            page_num, bbox = widget_positions.get(clean, (1, None))

            results.append(FieldMapEntry(
                field_id=clean,
                original_label=clean,
                field_type=ftype,
                source_page=page_num,
                bbox=bbox,
                options=options,
                current_value=val,
                confidence=1.0,
                source="acroform",
            ))
        except Exception:
            continue
    return results


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

        # One page walk for positions (lightweight — no AP resolution)
        widget_positions = _collect_widget_positions(reader)

        seen: set[str] = set()
        return _walk_field_tree(fields_arr, seen, widget_positions)

    except Exception:
        return []


# ── Flat PDF extraction (pdfplumber text + layout) ────────────────────────────

# Known German government form field patterns (calibrated on real Jobcenter forms).
# Every pattern is anchored to something actually IN the PDF — no topic-based invention.

_RE_BLANK_AFTER_COLON   = re.compile(r"^(.{2,80}):\s*_{3,}")          # "Label: ___"
_RE_BLANKS_THEN_UNIT    = re.compile(r"^_{3,}\s+(.{2,60})")           # "_____ EUR ..."
_RE_UNICODE_CHECKBOX    = re.compile(r"(□|☐|\[\s*\]|\(\s*\))\s*(.{2,60})")  # □ Option
_RE_LETTER_CHECKBOX     = re.compile(r"^([A-Z])\s+(Leistung\w+\s.{5,80})")  # A Leistungen für …
_RE_ORT_DATUM           = re.compile(r"Ort.{0,5}Datum", re.IGNORECASE)        # Ort/Datum …
_RE_UNTERSCHRIFT        = re.compile(r"Unterschrift", re.IGNORECASE)           # Unterschrift …
_RE_STANDALONE_LABEL    = re.compile(r"^([A-ZÄÖÜ][^:!?)]{2,120}[^:!?).])$")  # "Name, Vorname"
_RE_BETRAG_KM           = re.compile(r"betr[äa]gt\s+km", re.IGNORECASE)  # "beträgt km."

# Words that are structural text, not field labels — never generate a question for these
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
    # Skip lines that are mostly punctuation/numbers
    if re.match(r'^[\d\s\.,\-\(\)%€/]+$', lo):
        return True
    return False


def _make_fid(label: str) -> str:
    """Stable field_id from a label string."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower().strip())[:80].strip("_")


def extract_flat_fields(pdf_bytes: bytes) -> list[FieldMapEntry]:
    """
    Field detection for flat (non-fillable) PDFs using pdfplumber text extraction.

    Handles German government form patterns:
    - "Label: ___..." (blanks after colon)
    - "_____ EUR / km" (leading underscores with unit)
    - "□ Option" / "A Leistungen für …" (checkbox-style options)
    - "Ort/Datum", "Unterschrift" (signature areas)
    - Standalone title-case label lines ("Name, Vorname", "Postanschrift")

    Every returned field_id is grounded in a real line of text from the PDF.
    No fields are invented from the topic of the document.
    confidence = 0.75 (below the needs_review threshold of 0.7? No — 0.75 > 0.7,
    but source="pdfplumber" triggers needs_review=True regardless).
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    results: list[FieldMapEntry] = []
    seen: set[str] = set()
    letter_checkbox_options: list[str] = []  # collect A,B,C... options for a group
    letter_checkbox_group_started = False

    def _add(label: str, ftype: str, page: int, opts: Optional[list[str]] = None) -> None:
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
                        _add(m.group(1).strip(), "text", page_num)
                        continue

                    # 2. "_____ EUR / km" — fill-in amount or distance
                    m = _RE_BLANKS_THEN_UNIT.match(line)
                    if m:
                        unit_label = m.group(1).strip()
                        _add(unit_label, "number", page_num)
                        continue

                    # 3. "beträgt km." — distance fill-in
                    if _RE_BETRAG_KM.search(line):
                        _add("Strecke_km", "number", page_num)
                        continue

                    # 4. "□ Option" or "☐ Option" — unicode checkbox
                    if _RE_UNICODE_CHECKBOX.search(line):
                        for m in _RE_UNICODE_CHECKBOX.finditer(line):
                            _add(m.group(2).strip(), "checkbox", page_num)
                        continue

                    # 5. "A Leistungen für …" — letter-prefixed checkbox group
                    m = _RE_LETTER_CHECKBOX.match(line)
                    if m:
                        full_label = m.group(0)
                        # Truncate at parenthesis (explanatory text starts there)
                        short_label = re.split(r'\(', full_label, 1)[0].strip()
                        letter_prefix = m.group(1)
                        option_label = f"{letter_prefix}: {short_label[2:].strip()}"[:100]
                        letter_checkbox_options.append(option_label)
                        letter_checkbox_group_started = True
                        continue

                    # 6. "Ort/Datum" — date+place signature area
                    if _RE_ORT_DATUM.search(line):
                        _add("Ort_Datum", "text", page_num)
                        continue

                    # 7. "Unterschrift …" — signature line
                    if _RE_UNTERSCHRIFT.search(line):
                        _add("Unterschrift", "signature", page_num)
                        continue

                    # 8. Standalone title-case label line (e.g. "Name, Vorname")
                    if _RE_STANDALONE_LABEL.match(line) and not _skip(line):
                        # Only treat as a label if the next non-empty line looks like
                        # another label or is blank (i.e. this line IS the field)
                        next_lines = [l.strip() for l in lines[i+1:i+3] if l.strip()]
                        next_is_label = (
                            not next_lines
                            or _RE_STANDALONE_LABEL.match(next_lines[0])
                            or len(next_lines[0]) < 6
                        )
                        if next_is_label:
                            _add(line, "text", page_num)

    except Exception:
        pass

    # Flush letter-checkbox group as a single multi-select radio group
    if letter_checkbox_options and len(letter_checkbox_options) >= 2:
        fid = "leistungsart_auswahl"
        if fid not in seen:
            seen.add(fid)
            results.append(FieldMapEntry(
                field_id=fid,
                original_label="Beantragte Leistung (A–G)",
                field_type="multiselect",
                source_page=1,
                options=letter_checkbox_options,
                confidence=0.75,
                source="pdfplumber",
            ))

    return results


# ── Main entry point ───────────────────────────────────────────────────────────

def extract_field_map(pdf_bytes: bytes) -> ExtractionResult:
    """
    Full pipeline entry point.
    Detects PDF type, runs the appropriate extractor, returns ExtractionResult.
    """
    pdf_type, total_pages = detect_pdf_type(pdf_bytes)

    if pdf_type == "acroform":
        fields = extract_acroform_fields(pdf_bytes)
        if not fields:
            # AcroForm found but no usable fields — fall through to flat
            fields = extract_flat_fields(pdf_bytes)
            effective_type = "flat" if fields else "acroform"
        else:
            effective_type = "acroform"
    elif pdf_type == "flat":
        fields = extract_flat_fields(pdf_bytes)
        effective_type = "flat"
    else:
        fields = []
        effective_type = pdf_type  # "scanned" or "unknown"

    return ExtractionResult(
        pdf_type=effective_type,
        fields=fields,
        total_pages=total_pages,
    )


# ── Anti-hallucination validator ───────────────────────────────────────────────

def validate_no_hallucinations(
    field_map: list[FieldMapEntry],
    translations: dict[str, dict],
) -> HallucinationReport:
    """
    Validates AI-returned translations against the extracted field map.

    Rules:
    - Any key in `translations` NOT in `field_map` → INVENTED → DISCARDED
    - Any field_id in `field_map` NOT in `translations` → MISSING → BACKFILLED
      with {question: original_label, explanation: "", translated_options: {}}

    Returns HallucinationReport with a clean, safe translations dict.
    """
    extracted_ids = {f.field_id for f in field_map}
    returned_ids  = set(translations.keys())

    invented = returned_ids - extracted_ids  # AI made these up
    missing  = extracted_ids - returned_ids  # AI missed these

    # Safe translations: only keep keys that exist in the extracted field map
    cleaned: dict[str, dict] = {
        k: v for k, v in translations.items() if k in extracted_ids
    }

    # Backfill missing fields with the raw PDF label as the question
    field_by_id = {f.field_id: f for f in field_map}
    for fid in missing:
        entry = field_by_id[fid]
        cleaned[fid] = {
            "question": entry.original_label,   # raw PDF label — never AI-invented
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
) -> list[dict]:
    """
    Convert FieldMapEntry list + validated translations → list of FieldDefinition dicts.
    One FieldDefinition per FieldMapEntry — no extras, no omissions.
    """
    from app.schemas.document import FieldDefinition, FieldOption

    defs: list[FieldDefinition] = []
    for i, entry in enumerate(field_map, 1):
        tr = validated_translations.get(entry.field_id, {})
        tr_opts = tr.get("translated_options", {})
        options = [
            FieldOption(value=v, label=tr_opts.get(v, v))
            for v in entry.options
        ]
        defs.append(FieldDefinition(
            key=entry.field_id,
            question={user_language: tr.get("question") or entry.original_label},
            explanation={user_language: tr.get("explanation", "")},
            input_type=entry.field_type,
            options=options,
            original_label=entry.original_label,
            document_language=document_language,
            source_page=entry.source_page,
            order=i,
            is_prefilled=(entry.field_id in prefilled_ids),
            confidence=entry.confidence,
            needs_review=(entry.confidence < 0.7 or entry.source != "acroform"),
        ))
    return defs
