"""
Upload + PDF extraction routes.

Flow:
  1. POST /cases/{id}/upload  → saves file, returns document_id instantly (< 2s).
     Returns fields=[] — no questions are shown until the PDF is actually analysed.

  2. POST /cases/{id}/extract-pdf-fields  → AWAITED by frontend after upload.
     Reads the PDF field tree (AcroForm or pdfplumber), runs Groq translation,
     validates against anti-hallucination guard, returns grounded FieldDefinitions.
     Includes AnalysisReport with grounding_rate (always 100%) and coverage_rate.

  3. GET  /cases/{id}/analyze-pdf  → diagnostic endpoint for debug view.

Language rule:
  FieldOption.value  = PDF-native value (written to the PDF, e.g. "verheiratet")
  FieldOption.label  = user-facing text   (shown in UI,      e.g. "Marié(e)")
  raw_answer         = option.value  for choice fields  (already in PDF language)
  translated_answer  = Groq output   for text fields    (user lang → PDF lang)

Grounding rule (enforced):
  EVERY FieldDefinition returned has:
    - show_question: True only when confidence >= 0.70
    - source_text: the exact PDF text that grounds the question
    - reason: always "pdf_field" (never invented)
  The anti-hallucination validator guarantees grounding_rate = 100%.
"""
from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pypdf
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

log = logging.getLogger("burokratie.upload")

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.answer import Answer
from app.models.audit_log import AuditAction
from app.models.case import Case, CaseStatus
from app.models.document import UploadedDocument
from app.models.form_template import FormField, FormTemplate
from app.models.user import User
from app.schemas.document import AnalysisReport, FieldDefinition, FieldOption, UploadResponse
from app.services.audit_service import audit_service
from app.services.dynamic_form_service import create_dynamic_template
from app.services.pdf_pipeline import (
    AnalysisReport as PipelineAnalysisReport,
    build_analysis_report,
    extract_field_map,
    field_map_to_defs,
    validate_no_hallucinations,
    FieldMapEntry,
)
from app.services.question_translator import translate_fields
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024

# Choice field types — raw_answer for these is already the PDF-native value
CHOICE_TYPES = {"radio", "checkbox", "select", "multiselect", "yes_no"}


# ── Upload route — saves file, returns instantly with NO questions ─────────────
#
# The upload route intentionally returns fields=[].
# Questions are ONLY returned by /extract-pdf-fields, which the frontend awaits
# before navigating to the questions page.  This guarantees that every question
# shown to the user is grounded in the actual uploaded PDF.

@router.post("/{case_id}/upload", response_model=UploadResponse)
async def upload_document(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    user_language: str = Query("en"),
    document_language: str = Query("de"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    log.info("upload start case=%s filename=%s", case_id, file.filename)

    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    content = await file.read()
    size_kb = len(content) // 1024

    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"File too large ({size_kb} KB). Max {settings.max_upload_size_mb} MB.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    suffix  = Path(file.filename or "upload.pdf").suffix or ".pdf"
    dest    = upload_dir / f"{file_id}{suffix}"
    dest.write_bytes(content)

    # Auto-select fixed template if exactly one exists (for PDF generation fallback)
    detected_type: Optional[str] = None
    all_fixed = db.query(FormTemplate).filter(~FormTemplate.id.startswith("dyn_")).all()
    if len(all_fixed) == 1:
        detected_type = all_fixed[0].id

    if detected_type:
        case.form_template_id = detected_type
        case.status = CaseStatus.FORM_SELECTED.value
    else:
        case.status = CaseStatus.UPLOADED.value
    case.updated_at = datetime.now(timezone.utc)

    doc = UploadedDocument(
        case_id=case_id, original_filename=file.filename or "upload",
        storage_path=str(dest), ocr_text=None,
        detected_form_type=detected_type, ocr_confidence=0.0,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id, "mode": "fast_upload",
        "is_pdf": content[:4] == b"%PDF",
        "file_size_kb": size_kb,
    })
    db.commit()

    log.info("upload complete case=%s doc_id=%s size_kb=%d", case_id, doc.id, size_kb)

    # Return NO questions — frontend will call /extract-pdf-fields next
    return UploadResponse(
        document_id=doc.id,
        detected_form_type=detected_type,
        confidence=0.0,
        requires_manual_selection=False,
        prefilled_fields=0,
        fields=[],
        document_language=document_language,
        user_language=user_language,
        analysis_report=None,
    )


# ── PDF field extraction — awaited by frontend after upload ───────────────────

@router.post("/{case_id}/extract-pdf-fields", response_model=UploadResponse)
async def extract_pdf_fields(
    case_id: str,
    payload: dict = Body(default={}),
    user_language: str = Query("en"),
    document_language: str = Query("de"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Reads the uploaded PDF and returns precisely-grounded field definitions.

    Guarantees:
    - Every returned FieldDefinition has source_text pointing to a real PDF element.
    - show_question=False for any field with confidence < 0.70.
    - grounding_rate=100% enforced by validate_no_hallucinations().
    - analysis_report.grounding_ok is always True.

    Returns HTTP 422 with a clear message when no fields can be extracted.
    """
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    doc = (
        db.query(UploadedDocument)
        .filter(UploadedDocument.case_id == case_id)
        .order_by(UploadedDocument.uploaded_at.desc())
        .first()
    )
    if not doc or not doc.storage_path:
        raise HTTPException(status_code=404, detail="No uploaded document found.")

    storage_path = Path(doc.storage_path)
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")

    pdf_bytes = storage_path.read_bytes()
    if pdf_bytes[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="Uploaded file is not a PDF.")

    log.info(
        "extract-pdf-fields START case=%s doc=%s filename=%s lang=%s",
        case_id, doc.id, doc.original_filename, user_language,
    )

    # ── 1. Detect PDF type + extract deterministic field map ─────────────────
    extraction = extract_field_map(pdf_bytes)
    extracted_ids = [e.field_id for e in extraction.fields]

    log.info(
        "extract-pdf-fields EXTRACTED case=%s doc=%s pdf_type=%s pages=%d field_count=%d "
        "first_field_ids=%s",
        case_id, doc.id, extraction.pdf_type, extraction.total_pages,
        len(extraction.fields), extracted_ids[:10],
    )

    if not extraction.fields:
        detail = {
            "acroform": "This PDF has an AcroForm but no extractable widget fields.",
            "flat":     "This PDF has no fillable fields and no recognisable field patterns.",
            "scanned":  "This PDF appears to be a scanned image — OCR is not yet supported.",
        }.get(extraction.pdf_type, "No fields could be extracted from this PDF.")
        log.warning("extract-pdf-fields NO_FIELDS case=%s doc=%s pdf_type=%s",
                    case_id, doc.id, extraction.pdf_type)
        raise HTTPException(status_code=422, detail=detail)

    # ── 2. Translate field labels + options via Groq ──────────────────────────
    fields_for_groq = [
        {
            "field_name": e.field_id,
            "field_type": e.field_type,
            "options": e.options,
            "original_label": e.original_label,
        }
        for e in extraction.fields
    ]
    raw_translations = translate_fields(fields_for_groq, user_language, document_language)

    # ── 3. Anti-hallucination validation ─────────────────────────────────────
    report = validate_no_hallucinations(extraction.fields, raw_translations)
    if not report.is_clean:
        log.warning(
            "extract-pdf-fields HALLUCINATION case=%s doc=%s invented=%s missing=%s",
            case_id, doc.id, report.invented, report.missing,
        )

    # ── 4. Build field definitions with confidence gate ───────────────────────
    prefilled_raw = {e.field_id: e.current_value for e in extraction.fields if e.current_value}
    form_name     = storage_path.stem.replace("_", " ").title()

    field_defs = field_map_to_defs(
        extraction.fields,
        report.cleaned_translations,
        set(prefilled_raw.keys()),
        user_language,
        document_language,
    )

    # ── 5. Hard backend assertion: every question must be in the extracted field map ──
    extracted_ids_set = {e.field_id for e in extraction.fields}
    for fd in field_defs:
        if fd.key not in extracted_ids_set:
            # This should be impossible — validate_no_hallucinations() guarantees it.
            # If we reach here, there is a bug in the pipeline.
            log.error(
                "BUG extract-pdf-fields INVENTED_QUESTION case=%s doc=%s "
                "question_key=%s not_in_extracted=%s",
                case_id, doc.id, fd.key, extracted_ids_set,
            )
            raise HTTPException(
                status_code=500,
                detail=f"BUG: question '{fd.key}' not in extracted PDF field map. "
                       "This question was not generated from the uploaded document.",
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

    shown_defs   = [d for d in field_defs if d.show_question]
    blocked_defs = [d for d in field_defs if not d.show_question]
    log.info(
        "extract-pdf-fields RESULT case=%s doc=%s pdf_type=%s "
        "field_count=%d question_count=%d blocked=%d invented_removed=%d "
        "grounding_rate=%s first_question_ids=%s",
        case_id, doc.id, extraction.pdf_type,
        len(extraction.fields), len(shown_defs), len(blocked_defs),
        len(report.invented), analysis.grounding_rate,
        [d.key for d in shown_defs[:10]],
    )

    # ── 7. Persist dynamic template + pre-filled answers ─────────────────────
    template_id, _ = create_dynamic_template(
        db=db, case_id=case_id,
        acroform_fields={e.field_id: e.current_value for e in extraction.fields},
        form_name=form_name,
    )
    case.form_template_id = template_id
    case.status           = CaseStatus.FORM_SELECTED.value
    case.updated_at       = datetime.now(timezone.utc)
    doc.detected_form_type = template_id
    doc.ocr_confidence     = extraction.fields[0].confidence if extraction.fields else 0.0

    db.flush()

    count = _save_prefilled_answers(db, case_id, template_id, prefilled_raw)
    db.commit()

    return UploadResponse(
        document_id=doc.id,
        detected_form_type=template_id,
        confidence=extraction.fields[0].confidence if extraction.fields else 0.0,
        requires_manual_selection=False,
        prefilled_fields=count,
        fields=field_defs,
        document_language=document_language,
        user_language=user_language,
        analysis_report=analysis,
        extracted_field_ids=extracted_ids,   # authoritative ground-truth list
    )


# ── Diagnostic: raw field map + accuracy report ───────────────────────────────

@router.get("/{case_id}/analyze-pdf")
async def analyze_pdf(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Debug endpoint: returns the raw deterministic field map for the uploaded PDF.

    Shows PDF type, page count, and each extracted field with:
    - field_id (ground truth anchor)
    - original_label (PDF language)
    - field_type, source_page, bbox
    - source_text (exact PDF text that grounds the question)
    - options, confidence, source
    - show_question (False when confidence < 0.70)

    Also includes the full AnalysisReport.
    """
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    doc = (
        db.query(UploadedDocument)
        .filter(UploadedDocument.case_id == case_id)
        .order_by(UploadedDocument.uploaded_at.desc())
        .first()
    )
    if not doc or not doc.storage_path:
        raise HTTPException(status_code=404, detail="No uploaded document.")

    storage_path = Path(doc.storage_path)
    if not storage_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not on disk.")

    pdf_bytes = storage_path.read_bytes()
    is_pdf    = pdf_bytes[:4] == b"%PDF"

    if not is_pdf:
        return {
            "pdf_type": "not_pdf",
            "total_pages": 0,
            "field_count": 0,
            "fields": [],
            "filename": doc.original_filename,
            "analysis_report": None,
        }

    from app.services.pdf_pipeline import CONF_SHOW_MIN, CONF_REVIEW_MIN

    extraction = extract_field_map(pdf_bytes)

    # Build per-field debug data (includes show_question + blocking reason)
    debug_fields = []
    for e in extraction.fields:
        show = e.confidence >= CONF_SHOW_MIN
        needs_review = show and (e.confidence < CONF_REVIEW_MIN or e.source != "acroform")
        debug_fields.append({
            "show_question":    show,
            "field_id":         e.field_id,
            "original_label":   e.original_label,
            "field_type":       e.field_type,
            "source_page":      e.source_page,
            "bbox":             e.bbox,
            "source_text":      e.source_text,
            "options":          e.options,
            "current_value":    e.current_value,
            "confidence":       e.confidence,
            "source":           e.source,
            "needs_review":     needs_review,
            "reason":           e.reason,
            "status":           "valid" if show else "blocked",
        })

    # Compute quick analysis report for diagnostic
    shown   = sum(1 for f in debug_fields if f["show_question"])
    blocked = len(debug_fields) - shown
    low_conf = sum(1 for f in extraction.fields if CONF_SHOW_MIN <= f.confidence < CONF_REVIEW_MIN)
    cov     = round(shown / len(extraction.fields) * 100) if extraction.fields else 0

    analysis = {
        "pdf_type": extraction.pdf_type,
        "total_pages": extraction.total_pages,
        "field_count": len(extraction.fields),
        "questions_shown": shown,
        "questions_blocked": blocked,
        "low_confidence_fields": low_conf,
        "coverage_rate": f"{cov}%",
        "grounding_rate": "100%",
        "grounding_ok": True,
        "invented_questions_removed": 0,   # not run here (no AI call)
    }

    return {
        "filename": doc.original_filename,
        "analysis_report": analysis,
        "fields": debug_fields,
        "anti_hallucination": {
            "rule": "Every question.field_id must appear in this list.",
            "valid_field_ids": [e.field_id for e in extraction.fields],
        },
    }


# ── Lazy translation endpoint ──────────────────────────────────────────────────

@router.post("/{case_id}/translate-fields")
async def translate_fields_endpoint(
    case_id: str,
    payload: dict = Body(...),
    user_language: str = Query("en"),
    document_language: str = Query("de"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    fields_input: list[dict] = payload.get("fields", [])
    if not fields_input:
        return {}
    return translate_fields(fields_input, user_language, document_language)


# ── Pre-fill answers from PDF ─────────────────────────────────────────────────

def _save_prefilled_answers(db, case_id: str, template_id: str, extracted: dict[str, str]) -> int:
    if not extracted:
        return 0
    fields     = db.query(FormField).filter(FormField.template_id == template_id).all()
    valid_keys = {f.field_key: f for f in fields}
    count = 0
    for field_key, raw_value in extracted.items():
        if not raw_value or field_key not in valid_keys:
            continue
        field   = valid_keys[field_key]
        vresult = validation_service.validate_answer(raw_value, field.validation_rules, language="de")
        db.query(Answer).filter(
            Answer.case_id == case_id,
            Answer.field_key == field_key,
            Answer.is_active == True,
        ).update({"is_active": False})
        db.add(Answer(
            case_id=case_id, field_key=field_key,
            raw_answer=raw_value,
            translated_answer=raw_value,
            is_validated=vresult.is_valid,
            validation_errors=json.dumps(vresult.errors),
            is_active=True, answered_at=datetime.now(timezone.utc),
        ))
        count += 1
    return count
