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
"""
from __future__ import annotations

import logging
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
from app.services.question_translator import translate_fields

log = logging.getLogger("burokratie.process_pdf")

router = APIRouter(tags=["stateless"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


class ProcessPdfResponse(BaseModel):
    fields: list[FieldDefinition] = []
    extracted_field_ids: list[str] = []
    pdf_token: str
    analysis_report: Optional[AnalysisReport] = None
    filename: str = ""


@router.post("/process-pdf", response_model=ProcessPdfResponse)
async def process_pdf(
    file: UploadFile = File(...),
    user_language: str = Query("en"),
    document_language: str = Query("de"),
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

    log.info("process-pdf START filename=%s size_kb=%d lang=%s", filename, size_kb, user_language)

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

    # ── 2. Translate labels → user language via Groq ─────────────────────────
    fields_for_groq = [
        {
            "field_name":     e.field_id,
            "field_type":     e.field_type,
            "options":        e.options,
            "original_label": e.original_label,
        }
        for e in extraction.fields
    ]
    raw_translations = translate_fields(fields_for_groq, user_language, document_language)

    # ── 3. Anti-hallucination validation ─────────────────────────────────────
    report = validate_no_hallucinations(extraction.fields, raw_translations)
    if not report.is_clean:
        log.warning("process-pdf HALLUCINATION invented=%s", report.invented)

    # ── 4. Build FieldDefinition list with confidence gate ───────────────────
    prefilled_ids = {e.field_id for e in extraction.fields if e.current_value}
    field_defs = field_map_to_defs(
        extraction.fields,
        report.cleaned_translations,
        prefilled_ids,
        user_language,
        document_language,
    )

    # ── 5. Hard assertion: every question key must be in extracted field map ──
    extracted_set = set(extracted_ids)
    for fd in field_defs:
        if fd.key not in extracted_set:
            log.error("BUG process-pdf INVENTED_QUESTION key=%s not in %s", fd.key, extracted_set)
            raise HTTPException(
                status_code=500,
                detail=f"BUG: question '{fd.key}' not in extracted PDF field map.",
            )

    # ── 6. Accuracy report ────────────────────────────────────────────────────
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
    )

    shown = [d for d in field_defs if d.show_question]
    log.info(
        "process-pdf RESULT pdf_type=%s field_count=%d question_count=%d "
        "blocked=%d invented_removed=%d grounding=%s first_question_ids=%s",
        extraction.pdf_type, len(extraction.fields), len(shown),
        len([d for d in field_defs if not d.show_question]),
        len(report.invented), analysis.grounding_rate,
        [d.key for d in shown[:10]],
    )

    # ── 7. Sign PDF token (no DB write, no file write) ───────────────────────
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
    )
