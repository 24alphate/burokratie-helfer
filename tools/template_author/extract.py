"""
PDF field extraction for the template authoring workflow.

Reuses backend extraction services so the CLI sees exactly what the production
pipeline sees. Output is a JSON-serializable dict with:
  - acroform_fields: list of widget-extracted fields (high-confidence)
  - pdfplumber_fields: list of label-detected fields (medium-confidence)
  - text_sample: first 500 chars of extracted text (for fingerprint authoring)
  - page_count: number of pages
"""
from __future__ import annotations

from typing import Any


def extract_pdf_fields(pdf_bytes: bytes) -> dict[str, Any]:
    from app.services.pdf_pipeline import (
        detect_pdf_type,
        extract_acroform_fields,
        _extract_full_text,
    )

    pdf_type = detect_pdf_type(pdf_bytes)
    full_text = _extract_full_text(pdf_bytes)

    acroform = []
    if pdf_type == "acroform":
        try:
            acroform_entries = extract_acroform_fields(pdf_bytes)
            for e in acroform_entries:
                acroform.append({
                    "field_id": e.field_id,
                    "original_label": e.original_label,
                    "field_type": e.field_type,
                    "source_page": e.source_page,
                    "options": e.options,
                    "confidence": e.confidence,
                    "source": e.source,
                    "source_text": e.source_text,
                })
        except Exception as e:
            acroform = [{"_error": f"AcroForm extraction failed: {e}"}]

    page_count = full_text.count("\f") + 1 if full_text else 0

    return {
        "pdf_type": pdf_type,
        "page_count": page_count,
        "acroform_fields": acroform,
        "text_sample": full_text[:500],
        "text_length": len(full_text),
    }
