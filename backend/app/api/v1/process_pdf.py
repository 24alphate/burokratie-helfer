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
from app.services.question_translator import translate_fields, static_fallback, get_deterministic_translation
from app.services.semantic_questions import infer_semantic_key, lookup_semantic
from app.services.verified_questions import lookup_verified

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

    # ── 3. Annotate semantic_keys for unannotated fields ────────────────────
    # Only sets entry.semantic_key — never changes entry.field_id.
    for entry in extraction.fields:
        if entry.semantic_key is None:
            entry.semantic_key = infer_semantic_key(entry.original_label)

    # ── 4. Pre-resolve questions: verified → semantic → deterministic ────────
    # These are free (no AI cost) and highest quality.
    # Only unresolved fields are sent to Groq.
    pre_resolved: dict[str, dict] = {}
    for entry in extraction.fields:
        fid   = entry.field_id
        label = entry.original_label

        # Priority 1: verified human question
        verified = lookup_verified(fid, label, user_language)
        if verified:
            pre_resolved[fid] = {
                "question": verified["question"],
                "explanation": verified.get("help", ""),
                "help": verified.get("help", ""),
                "example": verified.get("example", ""),
                "format": verified.get("format", ""),
                "translated_options": {},
                "_source": "verified",
            }
            continue

        # Priority 2: semantic key question
        if entry.semantic_key:
            sem = lookup_semantic(entry.semantic_key, user_language)
            if sem:
                pre_resolved[fid] = {
                    "question": sem["question"],
                    "explanation": sem.get("help", ""),
                    "help": sem.get("help", ""),
                    "example": sem.get("example", ""),
                    "format": sem.get("format", ""),
                    "translated_options": {},
                    "_source": "semantic",
                }
                continue

        # Priority 3: deterministic translation table
        det = get_deterministic_translation(label, user_language)
        if det:
            pre_resolved[fid] = {
                "question": det,
                "explanation": "",
                "translated_options": {},
                "_source": "deterministic",
            }

    # Build Groq input for unresolved fields only
    fields_for_groq = [
        {
            "field_name":     e.field_id,
            "field_type":     e.field_type,
            "options":        e.options,
            "original_label": e.original_label,
        }
        for e in extraction.fields
        if e.field_id not in pre_resolved
    ]

    groq_key_set = bool(os.environ.get("GROQ_API_KEY", "").strip())

    if no_ai or not fields_for_groq:
        if fields_for_groq:
            # Use static fallback for unresolved fields when no_ai=True
            ai_translations = static_fallback(fields_for_groq, user_language)
            for fid in ai_translations:
                ai_translations[fid]["_source"] = "deterministic"
        else:
            ai_translations = {}
        ai_was_used = False
        log.info("process-pdf no_ai=%s groq_unresolved=%d pre_resolved=%d",
                 no_ai, len(fields_for_groq), len(pre_resolved))
    else:
        ai_translations = translate_fields(fields_for_groq, user_language, document_language)
        for fid in ai_translations:
            if "_source" not in ai_translations[fid]:
                ai_translations[fid]["_source"] = "ai"
        ai_was_used = groq_key_set

    # Merge: pre_resolved wins over AI (verified/semantic/deterministic beat AI)
    raw_translations = {**ai_translations, **pre_resolved}
    ai_call_count = len(fields_for_groq) if not no_ai else 0
    ai_skip_count = len(pre_resolved)

    # Level 1 invariant: verified templates must never reach Groq
    if extraction.extraction_source == "verified_template" and ai_call_count > 0:
        log.critical(
            "process-pdf BUG: verified template %s sent %d field(s) to AI — "
            "check VERIFIED_BY_FIELD_ID coverage",
            extraction.template_id, ai_call_count,
        )

    # ── 5. Anti-hallucination validation ─────────────────────────────────────
    report = validate_no_hallucinations(extraction.fields, raw_translations, user_language=user_language)
    if not report.is_clean:
        log.warning("process-pdf HALLUCINATION invented=%s", report.invented)

    # ── 6. Build FieldDefinition list with confidence gate ───────────────────
    prefilled_ids = {e.field_id for e in extraction.fields if e.current_value}
    field_defs = field_map_to_defs(
        extraction.fields,
        report.cleaned_translations,
        prefilled_ids,
        user_language,
        document_language,
    )

    # ── 7. Hard assertion: every question key must be in extracted field map ──
    extracted_set = set(extracted_ids)
    for fd in field_defs:
        if fd.key not in extracted_set:
            log.error("BUG process-pdf INVENTED_QUESTION key=%s not in %s", fd.key, extracted_set)
            raise HTTPException(
                status_code=500,
                detail=f"BUG: question '{fd.key}' not in extracted PDF field map.",
            )

    # ── 8. Question quality report ───────────────────────────────────────────
    # Quality checker lives in app.services.question_quality so the flag set
    # can be unit-tested directly (Phase C).
    from app.services.question_quality import quality_flags as _quality_flags_fn
    shown_defs      = [d for d in field_defs if d.show_question]
    field_by_id_map = {e.field_id: e for e in extraction.fields}

    source_counts: dict[str, int] = {
        "verified": 0, "semantic": 0, "ai": 0,
        "deterministic": 0, "label": 0, "key": 0,
    }
    weak_field_ids: list[str] = []
    weak_reasons_by_field: dict[str, list[str]] = {}
    for fd in shown_defs:
        entry = field_by_id_map.get(fd.key)
        src   = fd.question_source or "ai"
        source_counts[src] = source_counts.get(src, 0) + 1
        flags = _quality_flags_fn(
            fd,
            entry,
            user_language=user_language,
            extraction_source=extraction.extraction_source,
        )
        # Phase D/D7 — surface flags onto each FieldDefinition so the frontend
        # can render an honest "needs your review" hint per field. Empty list
        # means the question passed every check.
        fd.question_weak_reasons = flags
        if flags:
            weak_field_ids.append(fd.key)
            weak_reasons_by_field[fd.key] = flags

    quality_report = {
        "locale": user_language,
        "total_fields": len(shown_defs),
        "strong_questions": len(shown_defs) - len(weak_field_ids),
        "weak_questions": len(weak_field_ids),
        "weak_field_ids": weak_field_ids,
        "weak_reasons_by_field": weak_reasons_by_field,
        "question_source_counts": source_counts,
        "ai_calls_made": ai_call_count,
        "ai_calls_skipped": ai_skip_count,
    }
    log.info(
        "process-pdf QUALITY locale=%s strong=%d weak=%d ai_calls=%d skipped=%d weak_ids=%s",
        user_language, quality_report["strong_questions"], quality_report["weak_questions"],
        ai_call_count, ai_skip_count, weak_field_ids[:5],
    )

    # ── 9. Build AI comparison table (MODE 3) ────────────────────────────────
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

    # ── 10. Accuracy report + translation coverage ────────────────────────────
    pipeline_report = build_analysis_report(extraction, field_defs, report)

    # Translation coverage: a field is "translated" when its question[user_language]
    # differs from original_label.
    tr_total       = len(shown_defs)
    tr_fallback_ids: list[str] = []
    for fd in shown_defs:
        q_text = (fd.question or {}).get(user_language, "")
        orig   = field_by_id_map.get(fd.key)
        orig_label = orig.original_label if orig else ""
        if not q_text or q_text == orig_label:
            tr_fallback_ids.append(fd.key)
    tr_translated = tr_total - len(tr_fallback_ids)

    # ── 10b. AcroForm metrics (Phase D/D2) ─────────────────────────────────
    # Computed for every extraction so the QA dashboard always has numbers,
    # but only meaningful for Level 2 / 3 (Level 1 fields are template-typed).
    from collections import Counter as _Counter
    type_counts = _Counter(e.field_type for e in extraction.fields)
    fields_missing_bbox = sum(1 for e in extraction.fields if not e.bbox)
    fields_with_semantic = sum(1 for e in extraction.fields if e.semantic_key)
    fields_without_semantic = len(extraction.fields) - fields_with_semantic
    # /TU labels: heuristic — when extractor preferred a tooltip, the
    # original_label differs from the cleaned widget name.
    fields_with_tu = sum(
        1 for e in extraction.fields
        if e.original_label and e.original_label.lower() != e.field_id.lower()
        and " " in e.original_label
    )
    # Weak labels: empty, all-digits, or shorter than 3 chars.
    import re as _re_d
    fields_with_weak_label = sum(
        1 for e in extraction.fields
        if not e.original_label
        or len(e.original_label) < 3
        or _re_d.fullmatch(r"[\d\s\.\-]+", e.original_label or "")
    )
    # Duplicate labels: groups of 2+ fields sharing the same cleaned label.
    label_groups = _Counter(
        (e.original_label or "").strip().lower() for e in extraction.fields
    )
    duplicate_label_groups = sum(1 for _, n in label_groups.items() if n > 1)
    acroform_metrics = {
        "text_count":                 type_counts.get("text", 0),
        "date_count":                 type_counts.get("date", 0),
        "number_count":               type_counts.get("number", 0),
        "checkbox_count":             type_counts.get("checkbox", 0),
        "radio_count":                type_counts.get("radio", 0),
        "select_count":               type_counts.get("select", 0),
        "multiselect_count":          type_counts.get("multiselect", 0),
        "signature_count":            type_counts.get("signature", 0),
        "fields_missing_bbox":        fields_missing_bbox,
        "fields_with_semantic_key":   fields_with_semantic,
        "fields_without_semantic_key": fields_without_semantic,
        "fields_with_tu_label":       fields_with_tu,
        "fields_with_weak_label":     fields_with_weak_label,
        "duplicate_label_groups":     duplicate_label_groups,
    }
    # fill_strategy advertisement: tells the frontend which path /fill-pdf
    # WILL take when invoked with this token. None for routes that have no
    # fill path yet (Level 4).
    #
    # Phase F/0 follow-up: for Level 1 we read the actual template's
    # `fill_strategy` attribute instead of hard-coding "fitz_overlay". This
    # keeps the upload-page advertisement honest for verified templates that
    # use the AcroForm fill path (e.g. KG1). The template lookup is cheap
    # (in-memory cache) and always succeeds when extraction.template_id was
    # set, but we defensively fall back to "fitz_overlay" if it doesn't.
    if extraction.support_level == 1:
        fill_strategy = "fitz_overlay"
        if extraction.template_id:
            from app.services.form_templates import find_template_by_id
            tmpl = find_template_by_id(extraction.template_id)
            if tmpl is not None:
                fill_strategy = getattr(tmpl, "fill_strategy", "fitz_overlay")
    elif extraction.support_level == 2:
        fill_strategy = "acroform"
    elif extraction.support_level == 3:
        fill_strategy = "summary"
    else:
        fill_strategy = None

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
        support_level=extraction.support_level,
        translation_locale=user_language,
        translation_total=tr_total,
        translation_translated=tr_translated,
        translation_fallback=len(tr_fallback_ids),
        translation_fallback_ids=tr_fallback_ids,
        question_quality=quality_report,
        acroform_metrics=acroform_metrics,
        fill_strategy=fill_strategy,
    )

    shown = shown_defs
    first_questions = [
        f"{d.key} → {(d.question or {}).get(user_language, '?')!r}"
        for d in shown[:5]
    ]
    log.info(
        "process-pdf RESULT filename=%s user_language=%s document_language=%s "
        "pdf_type=%s field_count=%d question_count=%d "
        "blocked=%d invented_removed=%d grounding=%s ai_used=%s",
        filename, user_language, document_language,
        extraction.pdf_type, len(extraction.fields), len(shown),
        len([d for d in field_defs if not d.show_question]),
        len(report.invented), analysis.grounding_rate, ai_was_used,
    )
    log.info("process-pdf FIRST_5_FIELDS first_ids=%s", [e.field_id for e in extraction.fields[:5]])
    log.info("process-pdf FIRST_5_QUESTIONS %s", first_questions)

    # ── 9. Sign PDF token (no DB write, no file write) ───────────────────────
    pdf_token = sign_pdf_token(
        pdf_bytes=content,
        field_ids=extracted_ids,
        filename=filename,
        secret_key=settings.secret_key,
        template_id=extraction.template_id,   # None for AcroForm/unknown
        support_level=extraction.support_level,  # 1..4 — used by /fill-pdf safety policy
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
