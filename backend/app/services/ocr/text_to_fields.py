"""
Stage 4B — OCR-text-to-FieldMap extraction.

Takes an OCRDiagnostic (from Stage 4A) and applies the same regex heuristics
that drive extract_flat_fields() in pdf_pipeline.py — but against OCR-derived
text instead of pdfplumber output. The result feeds the rest of the pipeline
(translate → quality gate → questions) unchanged.

Anti-hallucination contract
---------------------------
Every emitted FieldMapEntry MUST satisfy:
  - source == "ocr"
  - source_text equals exactly the OCR line/block it was derived from
  - source_page set to the page the OCR block came from
  - confidence ∈ [0.50, 0.60] (Stage 4B is honest about uncertainty)

The validator (validate_no_hallucinations) downstream then checks that
every field_id in the produced map appears in the extracted_field_ids
list — same guarantee Levels 1/2/3 already provide.

Confidence policy
-----------------
Stage 4B sets confidence = 0.55. That's:
  - above CONF_SHOW_MIN (0.70)? NO — the user only sees fields here when
    the page-level OCR confidence is high enough. To prevent the visibility
    gate from blocking everything, we promote to 0.72 ONLY when the OCR
    block's confidence is itself >= 0.85. Anything below that stays at
    0.55 (manual / blocked from the question UI).

This means: clean, easy-to-OCR scans surface as questions; messy scans
get marked manual and the user is told to fix the input.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from app.services.ocr.diagnostic import (
    OCRDiagnostic,
    OCRPageResult,
    OCRTextBlock,
    STATUS_READABLE,
)
from app.services.pdf_pipeline import FieldMapEntry, MAX_FIELDS

log = logging.getLogger("burokratie.ocr_text_to_fields")

# ── Confidence bands ─────────────────────────────────────────────────────────

# Block-level OCR confidence above which we trust the field enough to show
# it directly (>= CONF_SHOW_MIN=0.70 in pdf_pipeline). Below this, fields
# are emitted with a lower confidence so they fall to manual.
HIGH_QUALITY_BLOCK_CONF = 0.85

# Confidence assigned to fields derived from high-quality OCR blocks.
SHOW_CONF = 0.72

# Confidence assigned to fields derived from lower-quality OCR blocks.
MANUAL_CONF = 0.55


# ── Regex heuristics (lifted from pdf_pipeline.extract_flat_fields) ──────────

_RE_BLANK_AFTER_COLON   = re.compile(r"^(.{2,80}):\s*_{3,}")
_RE_BLANKS_THEN_UNIT    = re.compile(r"^_{3,}\s+(.{2,60})")
_RE_UNICODE_CHECKBOX    = re.compile(r"(□|☐|\[\s*\]|\(\s*\))\s*(.{2,60})")
_RE_LETTER_CHECKBOX     = re.compile(r"^([A-Z])\s+(Leistung\w+\s.{5,80})")
_RE_ORT_DATUM           = re.compile(r"Ort.{0,5}Datum", re.IGNORECASE)
_RE_UNTERSCHRIFT        = re.compile(r"Unterschrift", re.IGNORECASE)
_RE_STANDALONE_LABEL    = re.compile(r"^([A-ZÄÖÜ][^:!?)]{2,120}[^:!?).])$")
_RE_BETRAG_KM           = re.compile(r"betr[äa]gt\s+km", re.IGNORECASE)
# Additional pattern: "Label _____" (label followed by underscores on the same line).
_RE_LABEL_THEN_BLANK    = re.compile(r"^(.{2,80})\s+_{3,}\s*$")

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
    if re.match(r"^[\d\s\.,\-\(\)%€/]+$", lo):
        return True
    return False


def _make_fid(label: str) -> str:
    """Stable field_id from a label string (matches extract_flat_fields)."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower().strip())[:80].strip("_")


# ── Block reassembly ─────────────────────────────────────────────────────────

def _blocks_to_lines(blocks: list[OCRTextBlock]) -> list[tuple[str, OCRTextBlock]]:
    """
    Tesseract returns one OCRTextBlock per word. Group words on the same
    visual line (close in y-coordinate) into a single text line, sorted by
    x-coordinate. Returns a list of (joined_line_text, representative_block).

    The representative block is the leftmost word in the line — used to
    derive bbox + page + confidence for the resulting FieldMapEntry.
    """
    if not blocks:
        return []

    # Sort by y first, then x
    sorted_blocks = sorted(blocks, key=lambda b: (round(b.bbox[1]), b.bbox[0]))

    # Group into lines by y-tolerance (use median word height as tolerance)
    median_height = sorted(
        [b.bbox[3] - b.bbox[1] for b in sorted_blocks if b.bbox[3] > b.bbox[1]]
    )[len(sorted_blocks) // 2] if sorted_blocks else 12
    y_tol = max(8, int(median_height * 0.6))

    lines: list[list[OCRTextBlock]] = []
    for b in sorted_blocks:
        if not lines:
            lines.append([b])
            continue
        last_line = lines[-1]
        last_y = last_line[0].bbox[1]
        if abs(b.bbox[1] - last_y) <= y_tol:
            last_line.append(b)
        else:
            lines.append([b])

    out: list[tuple[str, OCRTextBlock]] = []
    for line in lines:
        line.sort(key=lambda b: b.bbox[0])
        text = " ".join(b.text for b in line if b.text.strip())
        if not text.strip():
            continue
        # Compose a representative block whose bbox spans the whole line.
        x0 = min(b.bbox[0] for b in line)
        y0 = min(b.bbox[1] for b in line)
        x1 = max(b.bbox[2] for b in line)
        y1 = max(b.bbox[3] for b in line)
        avg_conf = sum(b.confidence for b in line) / len(line)
        rep = OCRTextBlock(
            text=text,
            page=line[0].page,
            bbox=[x0, y0, x1, y1],
            confidence=round(avg_conf, 4),
            language=line[0].language,
        )
        out.append((text, rep))
    return out


# ── Main extraction ──────────────────────────────────────────────────────────


def _confidence_for_block(rep: OCRTextBlock) -> float:
    """Map an OCR block's reported confidence to a pdf_pipeline confidence band."""
    return SHOW_CONF if rep.confidence >= HIGH_QUALITY_BLOCK_CONF else MANUAL_CONF


def extract_fields_from_ocr(diag: OCRDiagnostic) -> list[FieldMapEntry]:
    """
    Apply Level-3 regex heuristics to OCR-derived text blocks.

    Returns an empty list when:
      - diagnostic_status != "readable"  (low_conf / no_text / unavailable / failed)
      - no blocks were extracted
      - every line was filtered out as boilerplate

    Never raises. Anti-hallucination: every FieldMapEntry.source_text equals
    the exact OCR line text it was derived from, on the page it came from.
    """
    if diag.diagnostic_status != STATUS_READABLE:
        return []

    results: list[FieldMapEntry] = []
    seen: set[str] = set()
    letter_checkbox_options: list[str] = []
    letter_checkbox_source_lines: list[str] = []
    letter_checkbox_pages: list[int] = []
    letter_checkbox_confs: list[float] = []

    def _add(
        label: str,
        ftype: str,
        rep: OCRTextBlock,
        opts: list[str] | None = None,
        source_text: str = "",
    ) -> None:
        fid = _make_fid(label)
        if not fid or fid in seen or _skip(label):
            return
        if len(results) >= MAX_FIELDS:
            return
        seen.add(fid)
        conf = _confidence_for_block(rep)
        results.append(FieldMapEntry(
            field_id=fid,
            original_label=label.strip(),
            field_type=ftype,
            source_page=rep.page,
            bbox=list(rep.bbox),
            options=opts or [],
            confidence=conf,
            source="ocr",
            source_text=source_text or label.strip(),
            reason="pdf_field",
        ))

    for page_result in diag.pages:
        if not isinstance(page_result, OCRPageResult):
            continue
        if not page_result.blocks:
            continue
        if not page_result.quality.readable:
            # Page-level quality gate — skip pages OCR couldn't read confidently
            continue

        lines = _blocks_to_lines(page_result.blocks)

        for i, (line, rep) in enumerate(lines):
            stripped = line.strip()
            if not stripped or len(results) >= MAX_FIELDS:
                continue

            # 1. "Label: ___" — explicit blank after colon
            m = _RE_BLANK_AFTER_COLON.match(stripped)
            if m:
                _add(m.group(1).strip(), "text", rep, source_text=stripped)
                continue

            # 1b. "Label _____" — underscores on same line without colon
            m = _RE_LABEL_THEN_BLANK.match(stripped)
            if m:
                _add(m.group(1).strip(), "text", rep, source_text=stripped)
                continue

            # 2. "_____ EUR / km"
            m = _RE_BLANKS_THEN_UNIT.match(stripped)
            if m:
                _add(m.group(1).strip(), "number", rep, source_text=stripped)
                continue

            # 3. "beträgt km."
            if _RE_BETRAG_KM.search(stripped):
                _add("Strecke_km", "number", rep, source_text=stripped)
                continue

            # 4. "□ Option" — unicode checkbox
            if _RE_UNICODE_CHECKBOX.search(stripped):
                for m in _RE_UNICODE_CHECKBOX.finditer(stripped):
                    _add(m.group(2).strip(), "checkbox", rep, source_text=stripped)
                continue

            # 5. "A Leistungen für …" — letter-prefixed checkbox group
            m = _RE_LETTER_CHECKBOX.match(stripped)
            if m:
                full_label = m.group(0)
                short_label = re.split(r"\(", full_label, 1)[0].strip()
                letter_prefix = m.group(1)
                option_label = f"{letter_prefix}: {short_label[2:].strip()}"[:100]
                letter_checkbox_options.append(option_label)
                letter_checkbox_source_lines.append(stripped)
                letter_checkbox_pages.append(rep.page)
                letter_checkbox_confs.append(rep.confidence)
                continue

            # 6. "Ort/Datum"
            if _RE_ORT_DATUM.search(stripped):
                _add("Ort_Datum", "text", rep, source_text=stripped)
                continue

            # 7. "Unterschrift"
            if _RE_UNTERSCHRIFT.search(stripped):
                _add("Unterschrift", "signature", rep, source_text=stripped)
                continue

            # 8. Standalone title-case label line — but only when followed by
            # something that looks like ANOTHER label (i.e. likely an answer
            # blank afterwards). For OCR we relax slightly: the next line
            # exists and is not boilerplate.
            if _RE_STANDALONE_LABEL.match(stripped) and not _skip(stripped):
                next_lines = [t for (t, _r) in lines[i + 1: i + 3]]
                next_is_label = (
                    not next_lines
                    or _RE_STANDALONE_LABEL.match(next_lines[0])
                    or len(next_lines[0]) < 6
                )
                if next_is_label:
                    _add(stripped, "text", rep, source_text=stripped)

    # Flush letter-checkbox group if we collected ≥ 2 options
    if len(letter_checkbox_options) >= 2:
        fid = "leistungsart_auswahl"
        if fid not in seen and len(results) < MAX_FIELDS:
            seen.add(fid)
            avg_conf = sum(letter_checkbox_confs) / len(letter_checkbox_confs)
            conf = SHOW_CONF if avg_conf >= HIGH_QUALITY_BLOCK_CONF else MANUAL_CONF
            results.append(FieldMapEntry(
                field_id=fid,
                original_label="Beantragte Leistung (A–G)",
                field_type="multiselect",
                source_page=letter_checkbox_pages[0],
                options=letter_checkbox_options,
                confidence=conf,
                source="ocr",
                source_text=" | ".join(letter_checkbox_source_lines[:3]),
                reason="pdf_field",
            ))

    log.info(
        "ocr_text_to_fields fields=%d readable_pages=%d total_pages=%d",
        len(results),
        sum(1 for p in diag.pages if isinstance(p, OCRPageResult) and p.quality.readable),
        diag.page_count,
    )
    return results
