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
no_ai=true   Bypass the AI translator completely. Uses the raw PDF label as the question text.
             Use this to isolate whether wrong questions come from extraction or AI.

The response always includes:
  raw_extracted_fields  — field map BEFORE translation (extraction ground truth)
  ai_comparison         — side-by-side original_label vs AI question for every field
  ai_used               — whether the AI translator was attempted (false when no_ai=true or key missing)
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
from app.services.question_translator import (
    translate_fields, static_fallback, get_deterministic_translation, anthropic_available,
)
from app.services.semantic_questions import infer_semantic_key, lookup_semantic, lookup_semantic_strict
from app.services.verified_questions import lookup_verified, lookup_verified_strict

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
    # Whether the AI translator was called (false when no_ai=true or ANTHROPIC_API_KEY not set)
    ai_used: bool = False


def _build_scanned_response(
    *,
    content: bytes,
    extraction,
    ocr_diag_dict: dict,
    user_language: str,
    document_language: str,
    filename: str,
    ai_was_used: bool,
    no_ai_mode: bool,
) -> ProcessPdfResponse:
    """
    Stage 4A — short-circuit response for Level-4 (scanned/photo) PDFs.

    Returns a 200 OK with:
      • support_level = 4
      • fields = []
      • extracted_field_ids = []
      • analysis_report.ocr_diagnostic populated (technical_message stripped)
      • a signed pdf_token (so the existing UI plumbing doesn't crash) but
        no fields → /fill-pdf would 422 anyway because there are no answers
        to send. The token isn't intended to be used.

    No question generation, no LLM, no PDF fill. Strictly diagnostic.
    """
    # Strip the technical_message before serialization — it's developer-
    # facing only and may contain language pack names / file paths.
    safe_ocr = dict(ocr_diag_dict)
    safe_ocr.pop("technical_message", None)

    # Build a minimal AnalysisReport. The acroform_metrics + question_quality
    # fields stay None / zero — no questions exist for the user to assess.
    analysis = AnalysisReport(
        pdf_type=extraction.pdf_type,
        total_pages=extraction.total_pages,
        field_count=0,
        questions_shown=0,
        questions_blocked=0,
        low_confidence_fields=0,
        invented_questions_removed=0,
        coverage_rate="0%",
        grounding_rate="100%",   # vacuously true — no fields to ground
        grounding_ok=True,
        template_id=None,
        extraction_source=extraction.extraction_source,
        support_level=extraction.support_level,
        translation_locale=user_language,
        translation_total=0,
        translation_translated=0,
        translation_fallback=0,
        translation_fallback_ids=[],
        question_quality=None,
        acroform_metrics=None,
        fill_strategy=None,        # Level 4 has no fill path yet
        ocr_diagnostic=safe_ocr,
    )

    # Sign a token so frontend state remains consistent (the questions page
    # checks for a token before rendering). The token holds the original
    # bytes + an empty field_ids list. /fill-pdf will reject it because the
    # grounding guard requires at least one valid answer key, which the UI
    # has no way to produce — fields are empty.
    pdf_token = sign_pdf_token(
        pdf_bytes=content,
        field_ids=[],
        filename=filename,
        secret_key=settings.secret_key,
        template_id=None,
        support_level=4,
    )

    return ProcessPdfResponse(
        fields=[],
        extracted_field_ids=[],
        pdf_token=pdf_token,
        analysis_report=analysis,
        filename=filename,
        raw_extracted_fields=[],
        ai_comparison=[],
        ai_used=ai_was_used,
    )


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

    # Stage 4A — when the router returns Level 4 (scanned/photo) we run
    # the OCR diagnostic. Two outcomes:
    #
    #   (a) Stage 4B promotion: diagnostic_status == "readable" AND OCR text
    #       yields ≥1 FieldMapEntry via text_to_fields. We REPLACE the
    #       extraction result with the OCR-derived fields, downgrade the
    #       support_level to 3 (best-effort extraction), and let the rest of
    #       the pipeline (translate + quality + grounding) run unchanged.
    #       The original ocr_diagnostic is still attached to AnalysisReport
    #       for transparency.
    #
    #   (b) Stage 4A short-circuit: any other status (low_confidence,
    #       no_text_found, ocr_unavailable, failed) OR readable but zero
    #       fields extracted. Same diagnostic-only response as before.
    ocr_diag_for_report: dict | None = None

    # Stage 4C — Claude Vision. For a scanned/photographed form (no text layer,
    # no AcroForm) we render the pages and let Claude read the blank field
    # structure directly. On success we promote Level 4 → 3 and let the normal
    # translate/quality/grounding pipeline run; the existing Tesseract block
    # below is then skipped (support_level is no longer 4). Best-effort: fields
    # are shown with needs_review and the UI warns the user to verify. Falls
    # through to Tesseract when there's no key or Claude found nothing.
    if extraction.support_level == 4 and anthropic_available():
        from app.services.ocr.claude_scan import extract_fields_from_scan
        scan_fields = extract_fields_from_scan(content)
        if scan_fields:
            log.info("process-pdf CLAUDE_SCAN level=4→3 fields=%d", len(scan_fields))
            from app.services.pdf_pipeline import ExtractionResult
            extraction = ExtractionResult(
                pdf_type="ocr",
                fields=scan_fields,
                total_pages=extraction.total_pages,
                template_id=None,
                extraction_source="ocr",
                support_level=3,
            )
            extracted_ids = [e.field_id for e in extraction.fields]
            # Minimal diagnostic so the frontend shows the "read via OCR/vision —
            # please verify" banner (Stage 4B promotion note).
            ocr_diag_for_report = {
                "provider": "claude-vision",
                "page_count": extraction.total_pages,
                "pages": [],
                "full_text": "",
                "average_confidence": 0.0,
                "detected_languages": [],
                "readable_pages": extraction.total_pages,
                "unreadable_pages": 0,
                "diagnostic_status": "readable",
                "user_message": "",
            }

    if extraction.support_level == 4:
        from app.services.ocr.tesseract_provider import get_default_provider
        from app.services.ocr.text_to_fields import extract_fields_from_ocr
        ocr_provider = get_default_provider()
        ocr_diag = ocr_provider.diagnose(content)
        log.info(
            "process-pdf OCR_DIAGNOSTIC provider=%s status=%s avg_conf=%.3f "
            "pages=%d/%d readable=%d/%d tech=%s",
            ocr_diag.provider, ocr_diag.diagnostic_status,
            ocr_diag.average_confidence, ocr_diag.page_count,
            ocr_diag.page_count, ocr_diag.readable_pages, ocr_diag.page_count,
            ocr_diag.technical_message,
        )
        from dataclasses import asdict
        ocr_diag_dict = asdict(ocr_diag)

        # Stage 4B — try OCR-text-to-fields when the scan is readable.
        ocr_fields = extract_fields_from_ocr(ocr_diag)
        if ocr_fields:
            log.info(
                "process-pdf OCR_PROMOTION level=4→3 ocr_fields=%d",
                len(ocr_fields),
            )
            # Promote: replace the empty extraction with OCR-derived fields
            # and let the normal pipeline run. The ocr_diagnostic is kept
            # in the report so the user knows OCR was used.
            from app.services.pdf_pipeline import ExtractionResult
            extraction = ExtractionResult(
                pdf_type="ocr",
                fields=ocr_fields,
                total_pages=ocr_diag.page_count,
                template_id=None,
                extraction_source="ocr",
                support_level=3,
            )
            extracted_ids = [e.field_id for e in extraction.fields]
            ocr_diag_for_report = ocr_diag_dict
            # Fall through to the normal extraction path below.
        else:
            # Stage 4A short-circuit — diagnostic only.
            return _build_scanned_response(
                content=content,
                extraction=extraction,
                ocr_diag_dict=ocr_diag_dict,
                user_language=user_language,
                document_language=document_language,
                filename=filename,
                ai_was_used=False,
                no_ai_mode=no_ai,
            )

    if not extraction.fields:
        detail = {
            "acroform": "This PDF has an AcroForm but no extractable widget fields.",
            "flat":     "This PDF has no fillable fields and no recognisable field patterns.",
            "scanned":  "This PDF appears to be a scanned image — OCR is not yet supported.",
        }.get(extraction.pdf_type, "No fields could be extracted from this PDF.")
        raise HTTPException(status_code=422, detail=detail)

    # ── 1b. Vision enrichment (Level-2 AcroForm only, opt-in) ────────────────
    # Render the pages and let Gemini label every widget + group sibling
    # checkboxes. Strictly grounded (model can only reference real widgets) and
    # fully optional — any failure leaves the heuristic labels in place.
    vision_groups_for_token: list[dict] = []
    if extraction.support_level == 2 and settings.vision_backend in ("gemini", "claude"):
        import asyncio
        if settings.vision_backend == "claude":
            from app.services.vision.claude_form_vision import enrich_acroform
        else:
            from app.services.vision.gemini_form_vision import enrich_acroform
        try:
            enr = await asyncio.to_thread(enrich_acroform, extraction.fields, content)
        except Exception as e:
            log.warning("process-pdf VISION_FAILED err=%s", e)
            enr = None
        if enr and enr.used:
            for e in extraction.fields:
                lbl = enr.labels.get(e.field_id)
                if lbl:
                    e.original_label = lbl
                    e.semantic_key = None  # re-inferred from the new label below
            if enr.groups:
                from app.services.pdf_pipeline import FieldMapEntry
                members = enr.member_widgets
                extraction.fields = [e for e in extraction.fields if e.field_id not in members]
                for g in enr.groups:
                    extraction.fields.append(FieldMapEntry(
                        field_id=g.field_id,
                        original_label=g.question,
                        field_type="radio",
                        source_page=g.source_page,
                        options=[opt for (opt, _w, _on) in g.options],
                        confidence=1.0,
                        source="acroform",
                        source_text=g.question,
                        reason="pdf_field",
                    ))
                    vision_groups_for_token.append({
                        "field_id": g.field_id,
                        "options": [{"value": opt, "widget": w, "on": on}
                                    for (opt, w, on) in g.options],
                    })
            extracted_ids = [e.field_id for e in extraction.fields]
            log.info("process-pdf VISION_DONE labels=%d groups=%d field_count=%d",
                     len(enr.labels), len(enr.groups), len(extraction.fields))

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
    # These are free (no AI cost) and highest quality. Only unresolved fields
    # are sent to the AI translator.
    #
    # Locale coverage: the verified/semantic/deterministic tables cover only a
    # subset of locales. For NON-verified extractions (Level 2/3) we use the
    # STRICT lookups so a field whose locale isn't in a table is left unresolved
    # and routed to AI for a real translation — instead of silently pre-resolving
    # to the English fallback (which shadowed the AI for ~15 advertised locales
    # like it/pl/fa/ur). Verified templates keep the permissive (English-fallback)
    # lookups so Level 1 never reaches AI.
    prefer_strict = extraction.extraction_source != "verified_template"
    pre_resolved: dict[str, dict] = {}
    for entry in extraction.fields:
        fid   = entry.field_id
        label = entry.original_label

        # Phase F1 follow-up — Manual fields (confidence <= 0.5) are filtered
        # out of the question UI by the confidence gate downstream
        # (show_question=False for conf < CONF_SHOW_MIN=0.70). There is no
        # value in translating them — and translating them via AI would
        # falsely violate the Level 1 "ai_calls_made=0" invariant for
        # any verified template that legitimately marks fields as manual.
        if entry.confidence <= 0.5:
            continue

        # Priority 1: verified human question
        verified = (lookup_verified_strict if prefer_strict else lookup_verified)(
            fid, label, user_language
        )
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
            sem = (lookup_semantic_strict if prefer_strict else lookup_semantic)(
                entry.semantic_key, user_language
            )
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
        det = get_deterministic_translation(label, user_language, strict=prefer_strict)
        if det:
            pre_resolved[fid] = {
                "question": det,
                "explanation": "",
                "translated_options": {},
                "_source": "deterministic",
            }

    # Build the AI translator input for unresolved fields only.
    # Phase F1 follow-up: also skip manual (confidence <= 0.5) fields here
    # so they don't show up in ai_call_count even when ANTHROPIC_API_KEY is unset
    # (translate_fields can still fall through to static_fallback). Same
    # rationale as the pre_resolved skip above.
    fields_for_ai = [
        {
            "field_name":     e.field_id,
            "field_type":     e.field_type,
            "options":        e.options,
            "original_label": e.original_label,
        }
        for e in extraction.fields
        if e.field_id not in pre_resolved and e.confidence > 0.5
    ]

    ai_key_set = anthropic_available()

    if no_ai or not fields_for_ai:
        if fields_for_ai:
            # Use static fallback for unresolved fields when no_ai=True
            ai_translations = static_fallback(fields_for_ai, user_language)
            for fid in ai_translations:
                ai_translations[fid]["_source"] = "deterministic"
        else:
            ai_translations = {}
        ai_was_used = False
        log.info("process-pdf no_ai=%s ai_unresolved=%d pre_resolved=%d",
                 no_ai, len(fields_for_ai), len(pre_resolved))
    else:
        ai_translations = translate_fields(fields_for_ai, user_language, document_language)
        for fid in ai_translations:
            if "_source" not in ai_translations[fid]:
                ai_translations[fid]["_source"] = "ai"
        ai_was_used = ai_key_set

    # Merge: pre_resolved wins over AI (verified/semantic/deterministic beat AI)
    raw_translations = {**ai_translations, **pre_resolved}
    ai_call_count = len(fields_for_ai) if not no_ai else 0
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
    # Weak labels: empty, all-digits/punctuation, too short, or a generic
    # widget name ('Textfield', …). Shared with the Level-2 label-association
    # pass so the metric and the fix agree on what counts as weak.
    from app.services.pdf_pipeline import _is_weak_label
    fields_with_weak_label = sum(1 for e in extraction.fields if _is_weak_label(e.original_label))
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
    #
    # Phase F6 follow-up: the new "fitz_acroform" backend is normalized to
    # "acroform" in the public advertisement — both backends write into the
    # original PDF's AcroForm widgets and produce the same user-facing
    # "fillable PDF" experience. The internal backend choice is an
    # implementation detail; the X-Fill-Strategy download header also says
    # "acroform" for both.
    if extraction.support_level == 1:
        fill_strategy = "fitz_overlay"
        if extraction.template_id:
            from app.services.form_templates import find_template_by_id
            tmpl = find_template_by_id(extraction.template_id)
            if tmpl is not None:
                _raw = getattr(tmpl, "fill_strategy", "fitz_overlay")
                # Normalize fitz_acroform → acroform for the public surface
                fill_strategy = "acroform" if _raw == "fitz_acroform" else _raw
    elif extraction.support_level == 2:
        fill_strategy = "acroform"
    elif extraction.support_level == 3:
        fill_strategy = "summary"
    else:
        fill_strategy = None

    # ── Locale quality report (language-switch invariant) ───────────────────
    from app.services.locale_quality import build_locale_quality_report
    locale_quality = build_locale_quality_report(
        shown_fields=shown_defs,
        selected_locale=user_language,
        document_language=document_language,
        extraction_source=extraction.extraction_source,
        support_level=extraction.support_level,
        template_id=extraction.template_id,
    )
    log.info(
        "process-pdf LOCALE_QUALITY locale=%s ready=%s tier_a_ready=%s "
        "localized=%d fallback=%d missing=%d",
        user_language,
        locale_quality["ready_for_locale"],
        locale_quality["tier_a_ready"],
        locale_quality["localized_questions"],
        locale_quality["fallback_questions"],
        len(locale_quality["missing_questions"]),
    )

    # Stage 4B — when this run came from an OCR-promoted scan, strip the
    # technical_message from the diagnostic before serializing it. The
    # diagnostic stays attached so the frontend can show "we used OCR".
    safe_ocr_for_promotion: dict | None = None
    if ocr_diag_for_report is not None:
        safe_ocr_for_promotion = dict(ocr_diag_for_report)
        safe_ocr_for_promotion.pop("technical_message", None)

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
        locale_quality_report=locale_quality,
        ocr_diagnostic=safe_ocr_for_promotion,
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
        vision_groups=vision_groups_for_token or None,  # Level-2 checkbox groups
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
