"""
Vision-LLM AcroForm enrichment (Level 2) — Claude backend.

Same job and output contract as gemini_form_vision: render each page, draw a
numbered marker on every REAL widget ("set-of-marks"), ask the model to label
each box and group sibling checkboxes, and return a VisionEnrichment. Only the
model call differs — the dataclasses, prompt, grounding rule (answers keyed by
OUR marker index, so the model can't invent a field), grouping/build logic, and
the downstream application in process_pdf are shared with the Gemini backend.

Enable with VISION_BACKEND=claude (needs ANTHROPIC_API_KEY). Any error returns an
empty enrichment, so the caller falls back to the positional heuristic.
"""
from __future__ import annotations

import base64
import hashlib
import logging

# Reuse the stable shared definitions from the Gemini backend so both providers
# produce an identical VisionEnrichment that process_pdf already knows how to
# apply (labels, groups, member_widgets, vision_groups at fill time).
from app.services.vision.gemini_form_vision import (
    VisionEnrichment,
    GroupSpec,
    _on_value,
    _parse_json,
    _PROMPT,
    _MAX_PAGES,
    _DPI,
    _MAX_LABEL,
)

log = logging.getLogger("burokratie.vision_claude")

CLAUDE_VISION_MODEL = "claude-sonnet-4-6"

# Per-process cache keyed by sha256(pdf_bytes): re-uploads and multi-locale calls
# reuse the result instead of re-billing the API.
_CACHE: dict[str, VisionEnrichment] = {}


def _call_claude(png: bytes, boxlist: str, key: str) -> list[dict]:
    """One Claude vision call for a page image. Returns the parsed `fields` list."""
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    content = [
        {"type": "image", "source": {
            "type": "base64", "media_type": "image/png",
            "data": base64.standard_b64encode(png).decode("ascii"),
        }},
        {"type": "text", "text": _PROMPT.format(boxlist=boxlist)},
    ]
    resp = client.messages.create(
        model=CLAUDE_VISION_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text if resp.content else ""
    data = _parse_json(raw or "")
    fields = data.get("fields", [])
    return fields if isinstance(fields, list) else []


def enrich_acroform(fields: list, pdf_bytes: bytes) -> VisionEnrichment:
    """
    Enrich Level-2 AcroForm widgets with Claude-derived labels + checkbox groups.
    Pure read of `fields` (needs .field_id, .field_type); never mutates them.
    Returns an empty (used=False) enrichment on any problem.
    """
    # Imported here (not at module load) so the offline test fixture that patches
    # question_translator._resolve_anthropic_key governs this path too.
    from app.services.question_translator import _resolve_anthropic_key
    key = _resolve_anthropic_key()
    if not key:
        return VisionEnrichment()

    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if digest in _CACHE:
        return _CACHE[digest]

    try:
        import fitz  # PyMuPDF
    except Exception:
        return VisionEnrichment()

    fields_by_id = {f.field_id: f for f in fields}
    enr = VisionEnrichment()
    group_accum: dict[tuple, dict] = {}

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return VisionEnrichment()

    try:
        for pno in range(min(doc.page_count, _MAX_PAGES)):
            page = doc[pno]
            try:
                widgets = [w for w in (page.widgets() or []) if w.field_name in fields_by_id]
            except Exception:
                widgets = []
            if not widgets:
                continue

            indexed = []  # (idx, field_name, on_value)
            box_lines = []
            for idx, w in enumerate(widgets):
                ftype = fields_by_id[w.field_name].field_type
                onv = _on_value(w) if ftype in ("checkbox", "radio") else ""
                indexed.append((idx, w.field_name, onv))
                box_lines.append(f"  box {idx}: type={ftype}")
                try:
                    page.draw_rect(w.rect, color=(1, 0, 0), width=0.8)
                    page.insert_text((w.rect.x0 + 1, max(w.rect.y0 - 1, 6)),
                                     str(idx), color=(1, 0, 0), fontsize=7)
                except Exception:
                    pass

            try:
                png = page.get_pixmap(dpi=_DPI).tobytes("png")
                items = _call_claude(png, "\n".join(box_lines), key)
            except Exception as e:
                log.warning("claude vision page %d failed: %s", pno, e)
                continue

            for it in items:
                try:
                    i = int(it.get("index"))
                except (TypeError, ValueError):
                    continue
                if i < 0 or i >= len(indexed):
                    continue  # grounding: index must reference a real widget
                _, wid, onv = indexed[i]
                grp = it.get("checkbox_group")
                q = (it.get("question") or "").strip()
                if grp:
                    gk = (pno, str(grp))
                    acc = group_accum.setdefault(gk, {"question": q, "members": []})
                    if q and not acc["question"]:
                        acc["question"] = q
                    opt = (it.get("option_label") or "").strip() or wid.split(".")[-1]
                    acc["members"].append((opt[:_MAX_LABEL], wid, onv or "Yes"))
                elif q:
                    enr.labels[wid] = q[:_MAX_LABEL]
    finally:
        doc.close()

    n = 0
    for (pno, _), g in group_accum.items():
        members = g["members"]
        question = (g["question"] or "Bitte wählen").strip()[:_MAX_LABEL]
        if len(members) < 2:
            if members:
                enr.labels[members[0][1]] = question
            continue
        n += 1
        enr.groups.append(GroupSpec(
            field_id=f"vis_grp_{n}",
            question=question,
            options=[(opt, wid, onv) for (opt, wid, onv) in members],
            source_page=pno + 1,
        ))
        for _, wid, _ in members:
            enr.member_widgets.add(wid)

    enr.used = bool(enr.labels or enr.groups)
    _CACHE[digest] = enr
    return enr
