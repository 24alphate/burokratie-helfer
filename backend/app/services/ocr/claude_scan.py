"""
Stage 4C — Claude Vision form-structure extraction for scanned / photographed forms.

When a Level-4 PDF (a camera photo or scan with no text layer and no AcroForm)
can't be read deterministically, we render its pages to images and ask Claude to
list the BLANK fields a person must fill in. The result is a list of
FieldMapEntry compatible with the rest of the pipeline, so the normal
translate → quality-gate → grounding → questions flow runs unchanged.

Why this is allowed under "deterministic first, AI second":
    For a scanned image there is NO deterministic source — no widgets, no text
    layer. Claude Vision IS the extractor of last resort here. We mark these
    fields source="ocr" with moderate confidence so field_map_to_defs flags them
    needs_review, and the UI warns the user to verify. Field IDs are still the
    grounding anchor: every produced field_id flows through the same
    anti-hallucination + grounding guards as Levels 1–3.

Contract:
    - Never raises. Returns [] on: no API key, missing SDK/PyMuPDF, render
      failure, API error, or empty/garbage model output.
    - Every FieldMapEntry: source="ocr", source_text = the label Claude read,
      confidence in the shown band, field_type validated against the allow-list.
"""
from __future__ import annotations

import base64
import logging
import re
from typing import Optional

from app.services.pdf_pipeline import FieldMapEntry, MAX_FIELDS

log = logging.getLogger("burokratie.claude_scan")

# Vision-capable Claude model. Matches the existing ClaudeOCRService default.
CLAUDE_VISION_MODEL = "claude-sonnet-4-6"

# Cap pages sent to the model to bound latency/cost on large uploads.
MAX_SCAN_PAGES = 5

# Render DPI for page images. 150 is a good balance of legibility vs payload.
RENDER_DPI = 150

# Confidence assigned to vision-derived fields. Above CONF_SHOW_MIN (0.70) so
# they are shown, but below CONF_REVIEW_MIN (0.90) so field_map_to_defs marks
# them needs_review — honest about the uncertainty of reading a photo.
SCAN_CONF = 0.72

_VALID_TYPES = {
    "text", "date", "number", "checkbox",
    "radio", "select", "multiselect", "signature",
}

_EXTRACTION_PROMPT = """You are reading a scanned or photographed BLANK German government form.
List EVERY field a person must fill in. Do NOT invent fields that are not visible on the page.

Return ONLY a JSON object with this exact shape (no prose before or after):
{
  "fields": [
    {
      "label": "<the German label exactly as printed on the form>",
      "type": "text|date|number|checkbox|radio|select|multiselect|signature",
      "options": ["..."],
      "page": 1
    }
  ]
}

Rules:
- label: copy the German wording shown on the form. Do NOT translate it.
- type: choose the closest input type. A date line -> "date"; an amount or count
  -> "number"; a single yes/no box -> "checkbox"; a group of mutually exclusive
  boxes -> "radio" (with options); a group where several may be ticked ->
  "multiselect" (with options); a signature line -> "signature"; otherwise "text".
- options: the visible choice labels in German for radio/select/multiselect/
  checkbox groups; otherwise an empty array.
- page: the 1-indexed page the field appears on.
- Only list real blank inputs. Skip headings, instructions, legal text, logos,
  and page numbers.
- Return ONLY valid JSON."""


def _make_fid(label: str) -> str:
    """Stable field_id from a label (mirrors pdf_pipeline / text_to_fields)."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower().strip())[:80].strip("_")


def _fields_from_payload(data: dict) -> list[FieldMapEntry]:
    """
    Convert the model's parsed JSON payload into grounded FieldMapEntry objects.

    Pure + side-effect free so it can be unit-tested without the API. Drops
    entries with empty/too-short labels, duplicate ids, or invalid shapes;
    coerces unknown types to "text".
    """
    raw_fields = data.get("fields", []) if isinstance(data, dict) else []
    if not isinstance(raw_fields, list):
        return []

    results: list[FieldMapEntry] = []
    seen: set[str] = set()
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if len(label) < 2:
            continue

        ftype = str(item.get("type", "text")).strip().lower()
        if ftype not in _VALID_TYPES:
            ftype = "text"

        opts_raw = item.get("options", []) or []
        options = (
            [str(o).strip() for o in opts_raw if str(o).strip()]
            if isinstance(opts_raw, list) else []
        )

        try:
            page = int(item.get("page", 1))
        except (ValueError, TypeError):
            page = 1

        fid = _make_fid(label)
        if not fid or fid in seen:
            continue
        seen.add(fid)

        results.append(FieldMapEntry(
            field_id=fid,
            original_label=label,
            field_type=ftype,
            source_page=max(1, page),
            options=options,
            confidence=SCAN_CONF,
            source="ocr",
            source_text=label,   # what Claude read = grounding evidence
            reason="pdf_field",
        ))
        if len(results) >= MAX_FIELDS:
            break

    return results


def _render_page_images(pdf_bytes: bytes) -> list[tuple[int, bytes]]:
    """Render up to MAX_SCAN_PAGES pages to PNG bytes. Returns (page_no, png)."""
    import fitz  # PyMuPDF — already a backend dependency
    out: list[tuple[int, bytes]] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        zoom = RENDER_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i in range(min(doc.page_count, MAX_SCAN_PAGES)):
            pix = doc[i].get_pixmap(matrix=mat, alpha=False)
            out.append((i + 1, pix.tobytes("png")))
    finally:
        doc.close()
    return out


def extract_fields_from_scan(pdf_bytes: bytes) -> list[FieldMapEntry]:
    """
    Read a scanned/photographed form via Claude Vision → list[FieldMapEntry].

    Returns [] (never raises) when no usable Anthropic key is configured, the
    SDK / PyMuPDF is missing, rendering fails, the API errors, or the model
    returns nothing parseable.
    """
    # Lazy imports + key resolution shared with the translator (reads settings,
    # so backend/.env works locally; also honors a real env var in deploy).
    from app.services.question_translator import _resolve_anthropic_key, _extract_json

    key = _resolve_anthropic_key()
    if not key:
        return []

    try:
        import anthropic
    except ImportError:
        return []

    try:
        page_images = _render_page_images(pdf_bytes)
    except Exception as e:
        log.warning("claude_scan render failed: %s", e)
        return []
    if not page_images:
        return []

    content: list[dict] = []
    for page_no, png in page_images:
        content.append({"type": "text", "text": f"Page {page_no}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.standard_b64encode(png).decode("ascii"),
            },
        })
    content.append({"type": "text", "text": _EXTRACTION_PROMPT})

    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model=CLAUDE_VISION_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": content}],
        )
        text = resp.content[0].text if resp.content else ""
        data = _extract_json(text or "")
    except Exception as e:
        log.warning("claude_scan API call failed: %s", e)
        return []

    fields = _fields_from_payload(data)
    log.info("claude_scan extracted fields=%d pages=%d", len(fields), len(page_images))
    return fields


def recover_option_labels_via_vision(pdf_bytes: bytes, fields: list) -> None:
    """
    Feature E fallback: fill `option_labels` for radio fields that the positional
    page-text pass missed, by reading the rendered page with Claude Vision.

    Mutates each target FieldMapEntry in place (sets entry.option_labels). Pure
    best-effort: a no-op when there are no targets, no usable key/SDK/PyMuPDF,
    render fails, the API errors, or the model returns a mismatched shape. Never
    raises. The option VALUES are never changed — only their display labels.

    Value↔label mapping is preserved by ordering each group's option widgets
    top-to-bottom (then left-to-right) and asking Claude for labels in that same
    visual order, so label[i] maps to the i-th widget's export value.
    """
    from app.services.question_translator import _resolve_anthropic_key, _extract_json
    from app.services.pdf_pipeline import _collect_radio_option_widgets

    targets = [
        f for f in fields
        if getattr(f, "field_type", "") == "radio"
        and getattr(f, "options", None)
        and not getattr(f, "option_labels", None)
    ]
    if not targets:
        return

    key = _resolve_anthropic_key()
    if not key:
        return
    try:
        import anthropic
        import fitz  # PyMuPDF
    except ImportError:
        return

    widgets = _collect_radio_option_widgets(pdf_bytes, {f.field_id for f in targets})
    if not widgets:
        return

    by_field = {f.field_id: f for f in targets}
    by_page: dict[int, list[str]] = {}
    for fid in widgets:
        f = by_field.get(fid)
        if f:
            by_page.setdefault(f.source_page, []).append(fid)

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        log.warning("recover_option_labels_via_vision render open failed: %s", e)
        return

    try:
        client = anthropic.Anthropic(api_key=key)
        zoom = RENDER_DPI / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for page_num, fids in by_page.items():
            pidx = page_num - 1
            if pidx < 0 or pidx >= doc.page_count:
                continue
            try:
                png = doc[pidx].get_pixmap(matrix=mat, alpha=False).tobytes("png")
            except Exception:
                continue

            # Order each field's options top-to-bottom (PDF y is bottom-left, so
            # a larger y-centre is higher on the page), then left-to-right.
            field_specs: list[tuple[str, list[str]]] = []
            for fid in fids:
                ordered = sorted(
                    widgets[fid],
                    key=lambda vr: (-((vr[1][1] + vr[1][3]) / 2.0), vr[1][0]),
                )
                field_specs.append((fid, [v for (v, _r) in ordered]))

            listing = "\n".join(
                f'{i + 1}. field "{fid}" has {len(vals)} options (listed top to bottom)'
                for i, (fid, vals) in enumerate(field_specs)
            )
            prompt = (
                "This is a German government form page. For each multiple-choice "
                "field listed below, read the German label printed next to each "
                "option box, in order from top to bottom.\n"
                f"{listing}\n"
                'Return ONLY a JSON object mapping each field name to an array of '
                'its option labels, with EXACTLY the stated number of labels per '
                'field, copied verbatim in German (do not translate). Example: '
                '{"field_x": ["Option A", "Option B"]}'
            )
            content = [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png",
                    "data": base64.standard_b64encode(png).decode("ascii"),
                }},
                {"type": "text", "text": prompt},
            ]
            try:
                resp = client.messages.create(
                    model=CLAUDE_VISION_MODEL,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": content}],
                )
                data = _extract_json(resp.content[0].text if resp.content else "")
            except Exception as e:
                log.warning("recover_option_labels_via_vision API failed: %s", e)
                continue

            for fid, vals in field_specs:
                labels = data.get(fid) if isinstance(data, dict) else None
                if isinstance(labels, list) and len(labels) == len(vals):
                    entry = by_field[fid]
                    for v, lbl in zip(vals, labels):
                        lbl = str(lbl).strip()
                        if lbl:
                            entry.option_labels[v] = lbl
            log.info("recover_option_labels_via_vision page=%d fields=%d", page_num, len(field_specs))
    finally:
        doc.close()
