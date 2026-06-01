"""
Vision-LLM AcroForm enrichment (Level 2).

Renders each PDF page, draws a numbered marker on every REAL widget rect
("set-of-marks" prompting), then asks Gemini 2.0 Flash to (a) write a human
question for each numbered box and (b) group sibling checkboxes (gender,
marital status, Nein/Ja…) into one radio question.

Grounding is strict: the model answers are keyed by OUR marker index, so it can
only label/group widgets that actually exist — it can never invent a field. The
PDF widget type stays authoritative for filling; the model supplies the label
and the grouping only. Any error returns an empty enrichment so the caller falls
back to the positional heuristic. Free-tier safe: page cap + per-PDF cache.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field

log = logging.getLogger("burokratie.vision")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)
_MAX_PAGES = 10
_DPI = 150
_TIMEOUT = 45.0
_MAX_LABEL = 90

# Per-process cache keyed by sha256(pdf_bytes): re-uploads and multi-locale
# calls reuse the result instead of re-billing the API.
_CACHE: dict[str, "VisionEnrichment"] = {}


@dataclass
class GroupSpec:
    """A 'tick one of many boxes' question recovered from the page.

    options: list of (value, widget_name, on_value) — `value` is shown/answered,
    `on_value` is the export state written to that widget when chosen.
    """
    field_id: str
    question: str
    options: list[tuple[str, str, str]] = field(default_factory=list)
    source_page: int = 1


@dataclass
class VisionEnrichment:
    labels: dict[str, str] = field(default_factory=dict)        # field_id -> question
    groups: list[GroupSpec] = field(default_factory=list)
    member_widgets: set[str] = field(default_factory=set)       # widgets absorbed into groups
    used: bool = False                                          # a real call produced output


_PROMPT = """You are reading a German government form. The image has RED numbered \
boxes drawn over the fillable fields. For EACH numbered box, tell me what to ask \
the applicant.

Return ONLY JSON, no prose:
{{"fields":[{{"index":<int>,"question":"<short German label/question for this box>",\
"checkbox_group":<string id or null>,"option_label":"<German label of this option or null>"}}]}}

Rules:
- One entry per numbered box you can identify. Use the box number as "index".
- For a normal input box: set "question" to the field's German label \
(e.g. "Familienname", "Geburtsdatum"), "checkbox_group"=null, "option_label"=null.
- For a checkbox/radio that is ONE choice among several for the same question \
(e.g. Geschlecht: männlich/weiblich/divers, or Nein/Ja), give all of them the \
SAME "checkbox_group" id and the SAME "question" (the shared question), and set \
"option_label" to THIS box's choice (e.g. "männlich").
- Keep questions short and in German. Do not invent boxes that are not numbered.

The numbered boxes on this page are:
{boxlist}
"""


def _on_value(widget) -> str:
    """Best-effort 'on' export state for a checkbox/radio widget."""
    try:
        fn = getattr(widget, "on_state", None)
        if callable(fn):
            v = fn()
            if v and str(v).lower() != "off":
                return str(v)
    except Exception:
        pass
    try:
        states = widget.button_states() or {}
        for group in states.values():
            for s in group:
                if s and str(s).lower() != "off":
                    return str(s)
    except Exception:
        pass
    return "Yes"


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{[\s\S]*\}", text)
    return json.loads(m.group()) if m else {}


def _call_gemini(png: bytes, boxlist: str, api_key: str) -> list[dict]:
    """One sync Gemini call for a page image. Returns the parsed `fields` list."""
    import httpx

    payload = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png",
                                 "data": base64.standard_b64encode(png).decode("ascii")}},
                {"text": _PROMPT.format(boxlist=boxlist)},
            ]
        }],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4000},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(f"{GEMINI_URL}?key={api_key}", json=payload)
        resp.raise_for_status()
        result = resp.json()
    raw = result["candidates"][0]["content"]["parts"][0]["text"]
    data = _parse_json(raw)
    fields = data.get("fields", [])
    return fields if isinstance(fields, list) else []


def enrich_acroform(fields: list, pdf_bytes: bytes) -> VisionEnrichment:
    """
    Enrich Level-2 AcroForm widgets with vision-derived labels + checkbox groups.
    Pure read of `fields` (needs .field_id, .field_type); never mutates them.
    Returns an empty (used=False) enrichment on any problem.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "REPLACE_WITH_YOUR_KEY":
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
    # group_key -> {"question": str, "members": [(option_label, widget_name, on_value)]}
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
                items = _call_gemini(png, "\n".join(box_lines), api_key)
            except Exception as e:
                log.warning("vision page %d failed: %s", pno, e)
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

    # Build groups (≥2 members); a single-member "group" is just a labeled field.
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
