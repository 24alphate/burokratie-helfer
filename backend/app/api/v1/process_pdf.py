"""
POST /api/v1/process-pdf — stateless PDF extraction endpoint.

Replaces the two-step upload → extract-pdf-fields flow with a single call:

  Client sends: multipart PDF file + user_language
  Server:
    1. Extracts fields from the PDF (AcroForm or pdfplumber)
    2. Translates field labels to the user's language via Groq
    3. Validates against anti-hallucination guard
    4. Signs a PDF token (contains pdf_bytes + field_ids — no DB write)
    5. Returns fields + extracted_field_ids + pdf_token + analysis_report

The pdf_token is stored by the frontend (Zustand localStorage) and sent with
POST /fill-pdf when the user is ready to generate the filled document.

No database writes.  No file system writes.  Cold-start-proof.

Diagnostic query parameters
-----------------------------
no_ai=true   Bypass Groq completely. Uses the raw PDF label as the question text.
             Use this to isolate whether wrong questions come from extraction or AI.

The response always includes:
  raw_extracted_fields  — field map BEFORE translation (extraction ground truth)
  ai_comparison         — side-by-side original_label vs AI question for every field
  ai_used               — whether Groq was attempted (false when no_ai=true or key missing)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.schemas.document import AnalysisReport, FieldDefinition
from app.services.pdf_pipeline import (
    build_analysis_report,
    extract_field_map,
    field_map_to_defs,
    validate_no_hallucinations,
)
from app.services.pdf_token import sign_pdf_token
from app.services.question_translator import translate_fields, static_fallback

log = logging.getLogger("burokratie.process_pdf")

router = APIRouter(tags=["stateless"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ── Diagnostic response models ────────────────────────────────────────────────

class RawFieldEntry(BaseModel):
    """One extracted field BEFORE AI translation. This is the extraction ground truth."""
    field_id: str
    original_label: str
    field_type: str
    source_page: int
    source_text: str
    confidence: float
    source: str            # "acroform" | "pdfplumber" | "ocr"
    bbox: Optional[list[float]] = None
    options: list[str] = []
    reason: str            # "pdf_field" | "derived_helper"


class AIComparisonEntry(BaseModel):
    """Side-by-side original label vs AI-generated question for one field."""
    field_id: str
    original_label: str    # raw PDF label (ground truth)
    ai_question: str       # what AI returned (or original_label if no_ai=true / fallback)
    ai_explanation: str
    confidence: float
    ai_used: bool          # False when no_ai=true or Groq fell back to static


class ProcessPdfResponse(BaseModel):
    fields: list[FieldDefinition] = []
    extracted_field_ids: list[str] = []
    pdf_token: str
    analysis_report: Optional[AnalysisReport] = None
    filename: str = ""
    # ── Diagnostic data — always populated ───────────────────────────────────
    # raw_extracted_fields: the field map BEFORE translation.
    #   Compare this with `fields` to see what AI changed.
    raw_extracted_fields: list[RawFieldEntry] = []
    # ai_comparison: original_label vs AI question, side by side.
    #   If ai_used=false for an entry, ai_question == original_label (no AI involved).
    ai_comparison: list[AIComparisonEntry] = []
    # Whether Groq was called (false when no_ai=true or GROQ_API_KEY not set)
    ai_used: bool = False


@router.post("/process-pdf", response_model=ProcessPdfResponse)
async def process_pdf(
    file: UploadFile = File(...),
    user_language: str = Query("en"),
    document_language: str = Query("de"),
    no_ai: bool = Query(
        False,
        description=(
            "Diagnostic: bypass Groq and use raw PDF labels as questions. "
            "Use this to isolate whether wrong questions come from extraction or AI."
        ),
    ),
):
    """
    Upload a PDF and receive grounded questions + a signed PDF token.

    The pdf_token encodes the original PDF bytes (compressed).  Send it back
    with POST /fill-pdf to generate the completed document.

    Guarantees:
    - Every returned FieldDefinition.key exists in extracted_field_ids.
    - grounding_rate is always 100% (anti-hallucination validator enforced).
    - No data written to disk or database.
    """
    content = await file.read()
    filename = file.filename or "form.pdf"
    size_kb = len(content) // 1024

    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_kb} KB). Max {settings.max_upload_size_mb} MB.",
        )

    if content[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="Uploaded file is not a PDF.")

    log.info(
        "process-pdf START filename=%s size_kb=%d lang=%s no_ai=%s",
        filename, size_kb, user_language, no_ai,
    )

    # ── 1. Extract deterministic field map ───────────────────────────────────
    extraction = extract_field_map(content)
    extracted_ids = [e.field_id for e in extraction.fields]

    log.info(
        "process-pdf EXTRACTED pdf_type=%s pages=%d field_count=%d first_ids=%s",
        extraction.pdf_type, extraction.total_pages, len(extraction.fields), extracted_ids[:10],
    )

    if not extraction.fields:
        detail = {
            "acroform": "This PDF has an AcroForm but no extractable widget fields.",
            "flat":     "This PDF has no fillable fields and no recognisable field patterns.",
            "scanned":  "This PDF appears to be a scanned image — OCR is not yet supported.",
        }.get(extraction.pdf_type, "No fields could be extracted from this PDF.")
        raise HTTPException(status_code=422, detail=detail)

    # ── 2. Build raw_extracted_fields (BEFORE translation) ───────────────────
    raw_extracted_fields = [
        RawFieldEntry(
            field_id=e.field_id,
            original_label=e.original_label,
            field_type=e.field_type,
            source_page=e.source_page,
            source_text=e.source_text,
            confidence=e.confidence,
            source=e.source,
            bbox=e.bbox,
            options=e.options,
            reason=e.reason,
        )
        for e in extraction.fields
    ]

    # ── 3. Translate labels → user language ──────────────────────────────────
    fields_for_groq = [
        {
            "field_name":     e.field_id,
            "field_type":     e.field_type,
            "options":        e.options,
            "original_label": e.original_label,
        }
        for e in extraction.fields
    ]

    groq_key_set = bool(os.environ.get("GROQ_API_KEY", "").strip())

    if no_ai:
        # MODE 1: bypass AI — use raw PDF labels as questions
        raw_translations = static_fallback(fields_for_groq, user_language)
        ai_was_used = False
        log.info("process-pdf no_ai=true — skipping Groq, using raw PDF labels")
    else:
        raw_translations = translate_fields(fields_for_groq, user_language, document_language)
        ai_was_used = groq_key_set  # true if we attempted Groq (may still have fallen back)

    # ── 4. Anti-hallucination validation ─────────────────────────────────────
    report = validate_no_hallucinations(extraction.fields, raw_translations)
    if not report.is_clean:
        log.warning("process-pdf HALLUCINATION invented=%s", report.invented)

    # ── 5. Build FieldDefinition list with confidence gate ───────────────────
    prefilled_ids = {e.field_id for e in extraction.fields if e.current_value}
    field_defs = field_map_to_defs(
        extraction.fields,
        report.cleaned_translations,
        prefilled_ids,
        user_language,
        document_language,
    )

    # ── 6. Hard assertion: every question key must be in extracted field map ──
    extracted_set = set(extracted_ids)
    for fd in field_defs:
        if fd.key not in extracted_set:
            log.error("BUG process-pdf INVENTED_QUESTION key=%s not in %s", fd.key, extracted_set)
            raise HTTPException(
                status_code=500,
                detail=f"BUG: question '{fd.key}' not in extracted PDF field map.",
            )

    # ── 7. Build AI comparison table (MODE 3) ────────────────────────────────
    ai_comparison = []
    for e in extraction.fields:
        tr = report.cleaned_translations.get(e.field_id, {})
        ai_q = tr.get("question") or e.original_label
        ai_e = tr.get("explanation", "")
        ai_comparison.append(AIComparisonEntry(
            field_id=e.field_id,
            original_label=e.original_label,
            ai_question=ai_q,
            ai_explanation=ai_e,
            confidence=e.confidence,
            ai_used=ai_was_used,
        ))

    # ── 8. Accuracy report ────────────────────────────────────────────────────
    pipeline_report = build_analysis_report(extraction, field_defs, report)
    analysis = AnalysisReport(
        pdf_type=pipeline_report.pdf_type,
        total_pages=pipeline_report.total_pages,
        field_count=pipeline_report.field_count,
        questions_shown=pipeline_report.questions_shown,
        questions_blocked=pipeline_report.questions_blocked,
        low_confidence_fields=pipeline_report.low_confidence_fields,
        invented_questions_removed=pipeline_report.invented_questions_removed,
        coverage_rate=pipeline_report.coverage_rate,
        grounding_rate=pipeline_report.grounding_rate,
        grounding_ok=pipeline_report.grounding_ok,
        template_id=extraction.template_id,
        extraction_source=extraction.extraction_source,
    )

    shown = [d for d in field_defs if d.show_question]
    log.info(
        "process-pdf RESULT pdf_type=%s field_count=%d question_count=%d "
        "blocked=%d invented_removed=%d grounding=%s ai_used=%s first_question_ids=%s",
        extraction.pdf_type, len(extraction.fields), len(shown),
        len([d for d in field_defs if not d.show_question]),
        len(report.invented), analysis.grounding_rate, ai_was_used,
        [d.key for d in shown[:10]],
    )

    # ── 9. Sign PDF token (no DB write, no file write) ───────────────────────
    pdf_token = sign_pdf_token(
        pdf_bytes=content,
        field_ids=extracted_ids,
        filename=filename,
        secret_key=settings.secret_key,
    )

    return ProcessPdfResponse(
        fields=field_defs,
        extracted_field_ids=extracted_ids,
        pdf_token=pdf_token,
        analysis_report=analysis,
        filename=filename,
        raw_extracted_fields=raw_extracted_fields,
        ai_comparison=ai_comparison,
        ai_used=ai_was_used,
    )
