"""
Live check for the Anthropic-backed features (translation + Claude Vision scan).

Makes REAL API calls — run it only after pasting a real ANTHROPIC_API_KEY into
backend/.env. With no key it prints guidance and exits 0, so it's safe to run
anytime.

    cd backend
    python live_ai_check.py

What it verifies:
  1. Translation: two uncommon German labels (not in the deterministic table, so
     they actually reach Anthropic) are translated to French and Arabic, and the
     Arabic output is script-checked.
  2. Scanning: a synthetic image-only PDF (no text layer, like a phone photo) is
     read by Claude Vision and its blank fields are listed.
"""
from __future__ import annotations

import io


def _make_scanned_pdf() -> bytes:
    """Render a few German form lines to an image-only PDF (no text layer)."""
    from PIL import Image, ImageDraw, ImageFont
    import fitz  # PyMuPDF

    img = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=40)
    except TypeError:  # older Pillow without size kwarg
        font = ImageFont.load_default()

    lines = [
        "Antrag auf Leistungen",
        "Vorname: ______________",
        "Nachname: ______________",
        "Geburtsdatum: __ . __ . ____",
        "Familienstand:  ledig [ ]   verheiratet [ ]",
        "Unterschrift: ______________",
    ]
    y = 90
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 110

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(0, 0, 595, 842), stream=buf.getvalue())
    out = doc.tobytes()
    doc.close()
    return out


def main() -> int:
    from app.services.question_translator import (
        anthropic_key_configured,
        translate_fields,
        _looks_like_language,
    )

    if not anthropic_key_configured():
        print(
            "No usable ANTHROPIC_API_KEY found (settings/.env still has the "
            "REPLACE placeholder).\nPaste a real key into backend/.env, then "
            "re-run:  python live_ai_check.py"
        )
        return 0

    print("== Translation (real Anthropic call) ==")
    fields = [
        {"field_name": "f_miete", "field_type": "number", "options": [],
         "original_label": "Nettokaltmiete"},
        {"field_name": "f_bg", "field_type": "text", "options": [],
         "original_label": "Bedarfsgemeinschaft"},
    ]
    for lang in ("fr", "ar"):
        tr = translate_fields(fields, lang)
        print(f"\n[{lang}]")
        for fid, v in tr.items():
            q = v.get("question", "")
            print(f"  {fid}: {q!r}  script_ok={_looks_like_language(q, lang)}")

    print("\n== Scan extraction (real Claude Vision call) ==")
    try:
        pdf = _make_scanned_pdf()
    except Exception as e:
        print(f"  (could not build sample scan: {e})")
        return 0
    from app.services.ocr.claude_scan import extract_fields_from_scan
    scan_fields = extract_fields_from_scan(pdf)
    print(f"  fields extracted: {len(scan_fields)}")
    for f in scan_fields:
        print(f"   - {f.field_id}: type={f.field_type} "
              f"label={f.original_label!r} opts={f.options}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
