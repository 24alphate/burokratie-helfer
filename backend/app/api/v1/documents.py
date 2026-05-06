"""
Upload + PDF extraction routes.

Flow:
  1. POST /cases/{id}/upload  → saves file, returns fixed-template fields instantly (< 2s)
  2. POST /cases/{id}/extract-pdf-fields  → background call; reads AcroForm field tree,
     creates dynamic template, returns real FieldDefinitions with options
  3. POST /cases/{id}/translate-fields   → background call; Groq translation of questions

Language rule:
  FieldOption.value  = PDF-native value (written to the PDF, e.g. "verheiratet")
  FieldOption.label  = user-facing text   (shown in UI,      e.g. "Marié(e)")
  raw_answer         = option.value  for choice fields  (already in PDF language)
  translated_answer  = Groq output   for text fields    (user lang → PDF lang)
"""
from __future__ import annotations

import io
import json
import logging
import re
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
from app.models.question import Question
from app.models.user import User
from app.schemas.document import FieldDefinition, FieldOption, UploadResponse
from app.services.audit_service import audit_service
from app.services.dynamic_form_service import create_dynamic_template
from app.services.pdf_pipeline import (
    extract_field_map, detect_pdf_type,
    validate_no_hallucinations, field_map_to_defs, FieldMapEntry,
)
from app.services.question_translator import static_fallback, translate_fields
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024
MAX_ACROFORM_FIELDS = 150   # safety cap to bound memory / time

_FF_RADIO       = 1 << 15
_FF_PUSHBUTTON  = 1 << 16
_FF_MULTISELECT = 1 << 21

# Choice field types — raw_answer for these is already the PDF-native value
CHOICE_TYPES = {"radio", "checkbox", "select", "multiselect", "yes_no"}


# ── AcroForm field-type classifier ────────────────────────────────────────────

def _acroform_field_type(ft: str, flags: int) -> Optional[str]:
    if ft == "/Tx":   return "text"
    if ft == "/Sig":  return "signature"
    if ft == "/Ch":   return "multiselect" if (flags & _FF_MULTISELECT) else "select"
    if ft == "/Btn":
        if flags & _FF_PUSHBUTTON: return None
        return "radio" if (flags & _FF_RADIO) else "checkbox"
    return "text"


# ── Radio-option extraction from /Kids (field-tree only, no page walk) ────────

def _radio_options_from_kids(field_obj) -> list[str]:
    """
    Extract radio button export values from a /Btn group's /Kids widgets.

    Path: field → /Kids[] → each widget → /AP/N → key names (= export values).
    This is purely within the AcroForm field tree — never touches page objects,
    so it cannot cause OOM on large multi-page forms.
    """
    options: list[str] = []
    kids = field_obj.get("/Kids", [])
    if hasattr(kids, "get_object"):
        kids = kids.get_object()
    for kid_ref in list(kids)[:50]:
        try:
            kid = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            ap = kid.get("/AP")
            if ap is None:
                continue
            if hasattr(ap, "get_object"):
                ap = ap.get_object()
            normal = ap.get("/N")
            if normal is None:
                continue
            if hasattr(normal, "get_object"):
                normal = normal.get_object()
            for key in (normal.keys() if hasattr(normal, "keys") else []):
                val = str(key).lstrip("/")
                if val and val.lower() not in ("off", ""):
                    if val not in options:
                        options.append(val)
        except Exception:
            continue
    return options


# ── Recursive AcroForm field-tree walker ──────────────────────────────────────

def _walk_acroform_fields(fields_array, seen: set[str], depth: int = 0) -> list[dict]:
    """
    Walk the AcroForm /Fields tree recursively.

    Handles intermediate group nodes (fields with /Kids but no /FT) — common in
    complex German government forms where fields are nested inside named groups.
    Radio options are collected from /Kids → /AP/N (field tree, not page tree).
    """
    results: list[dict] = []
    for field_ref in list(fields_array):
        if len(seen) >= MAX_ACROFORM_FIELDS:
            break
        try:
            field = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref
            ft_raw = field.get("/FT")
            has_kids = "/Kids" in field

            # Intermediate group node — no /FT, has /Kids → recurse
            if ft_raw is None and has_kids and depth < 5:
                kids = field.get("/Kids", [])
                if hasattr(kids, "get_object"):
                    kids = kids.get_object()
                results.extend(_walk_acroform_fields(kids, seen, depth + 1))
                continue

            # Leaf widget — extract name
            name = field.get("/T", "")
            if hasattr(name, "get_object"):
                name = name.get_object()
            clean = str(name).lstrip("/").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)

            # Field type
            ft_str = str(ft_raw) if ft_raw else "/Tx"
            try:
                flags = int(str(field.get("/Ff", "0")).split(".")[0] or "0")
            except (ValueError, TypeError):
                flags = 0
            ftype = _acroform_field_type(ft_str, flags) or "text"

            # Current / default value
            val = field.get("/V") or field.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()
            if val in ("/Off", "Off", "None", "none"):
                val = ""
            elif val.startswith("/"):
                val = val[1:]

            # Options (for choice fields)
            options: list[str] = []
            if ftype in ("select", "multiselect"):
                try:
                    raw_opts = field.get("/Opt", [])
                    for o in (raw_opts if isinstance(raw_opts, list) else []):
                        options.append(str(o[0]) if isinstance(o, (list, tuple)) else str(o))
                except Exception:
                    options = []
            elif ftype == "radio" and has_kids:
                options = _radio_options_from_kids(field)

            results.append({
                "field_name":    clean,
                "field_type":    ftype,
                "current_value": val,
                "options":       options,
                "original_label": clean,
            })
        except Exception:
            continue
    return results


def _extract_acroform_fields(pdf_bytes: bytes) -> list[dict]:
    """
    Public entry point for AcroForm extraction.
    Uses field-tree traversal — safe on any size PDF.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        root = reader.trailer.get("/Root")
        if root is None:
            return []
        if hasattr(root, "get_object"):
            root = root.get_object()
        acroform_ref = root.get("/AcroForm")
        if acroform_ref is None:
            return []
        if hasattr(acroform_ref, "get_object"):
            acroform_ref = acroform_ref.get_object()
        fields_array = acroform_ref.get("/Fields", [])
        if hasattr(fields_array, "get_object"):
            fields_array = fields_array.get_object()
        return _walk_acroform_fields(fields_array, seen=set())
    except Exception:
        return []


# ── FieldDefinition builder ───────────────────────────────────────────────────

def _build_field_defs(
    extracted: list[dict],
    translations: dict[str, dict],
    prefilled_keys: set[str],
    user_language: str,
    document_language: str,
    confidence: float = 1.0,
) -> list[FieldDefinition]:
    defs: list[FieldDefinition] = []
    for i, f in enumerate(extracted, 1):
        fname  = f["field_name"]
        tr     = translations.get(fname, {})
        tr_opts = tr.get("translated_options", {})
        # Options: value = PDF-native export value, label = translated user text
        options = [
            FieldOption(value=v, label=tr_opts.get(v, v))
            for v in f.get("options", [])
        ]
        defs.append(FieldDefinition(
            key=fname,
            question={user_language: tr.get("question") or fname},
            explanation={user_language: tr.get("explanation", "")},
            input_type=f["field_type"],
            options=options,
            original_label=f.get("original_label", fname),
            document_language=document_language,
            source_page=1,
            order=i,
            is_prefilled=(fname in prefilled_keys),
            confidence=confidence,
            needs_review=(confidence < 0.6),
        ))
    return defs


# ── Upload route — always returns < 2s, no pypdf ──────────────────────────────

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
    log.info("upload start case=%s filename=%s content_type=%s",
             case_id, file.filename, file.content_type)

    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    content = await file.read()
    size_kb = len(content) // 1024
    log.info("upload file read case=%s size_kb=%d", case_id, size_kb)

    if len(content) > MAX_SIZE_BYTES:
        log.warning("upload rejected — file too large case=%s size_kb=%d limit_mb=%d",
                    case_id, size_kb, settings.max_upload_size_mb)
        raise HTTPException(status_code=413,
                            detail=f"File too large ({size_kb} KB). Max {settings.max_upload_size_mb} MB.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    suffix  = Path(file.filename or "upload.pdf").suffix or ".pdf"
    dest    = upload_dir / f"{file_id}{suffix}"
    dest.write_bytes(content)
    log.info("upload saved case=%s path=%s", case_id, dest)

    # Auto-select the fixed template when there is exactly one (no OCR needed)
    detected_type: Optional[str] = None
    all_fixed = db.query(FormTemplate).filter(
        ~FormTemplate.id.startswith("dyn_")
    ).all()
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
        detected_form_type=detected_type, ocr_confidence=0.5,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()

    # Return generic fixed-template questions immediately
    field_defs: list[FieldDefinition] = []
    if detected_type:
        questions = db.query(Question).filter(
            Question.template_id == detected_type
        ).order_by(Question.order_index).all()
        raw_for_tr = [{"field_name": q.field_key, "field_type": q.input_type}
                      for q in questions]
        translations = static_fallback(raw_for_tr, user_language)
        for q in questions:
            qt = json.loads(q.question_text)
            tr = translations.get(q.field_key, {})
            question_text = tr.get("question") or qt.get(user_language) or qt.get("en", q.field_key)
            field_defs.append(FieldDefinition(
                key=q.field_key,
                question={user_language: question_text},
                explanation={user_language: tr.get("explanation", "")},
                input_type=q.input_type,
                options=[],
                original_label=q.field_key,
                document_language=document_language,
                source_page=1,
                order=q.order_index,
                is_prefilled=False,
                confidence=0.5,
                needs_review=True,
            ))

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id, "mode": "fast_upload",
        "detected_form_type": detected_type,
        "is_pdf": content[:4] == b"%PDF",
        "file_size_kb": len(content) // 1024,
    })
    db.commit()

    log.info("upload complete case=%s doc_id=%s template=%s fields=%d",
             case_id, doc.id, detected_type, len(field_defs))
    return UploadResponse(
        document_id=doc.id, detected_form_type=detected_type,
        confidence=0.5, requires_manual_selection=not detected_type,
        prefilled_fields=0, fields=field_defs,
        document_language=document_language, user_language=user_language,
    )


# ── PDF field extraction — fire-and-forget after upload ───────────────────────

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
    Reads the uploaded PDF's AcroForm field tree and returns precise field
    definitions grounded in the actual document.

    Called fire-and-forget by the frontend after upload completes.
    No Vercel timeout pressure: the upload response was already sent.

    Guarantees:
    - Every returned question has a source field_name matching an AcroForm widget.
    - Radio/checkbox fields include their export values as options[].value.
    - Choice field options have translated labels via Groq (when available).
    - confidence=1.0 for AcroForm widgets (ground truth).
    """
    log.info("extract-pdf-fields start case=%s lang=%s", case_id, user_language)
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
        log.warning("extract-pdf-fields no document found case=%s", case_id)
        raise HTTPException(status_code=404, detail="No uploaded document found.")

    storage_path = Path(doc.storage_path)
    if not storage_path.exists():
        log.warning("extract-pdf-fields file missing case=%s path=%s", case_id, storage_path)
        raise HTTPException(status_code=404, detail="Uploaded file not found on disk.")

    pdf_bytes = storage_path.read_bytes()
    if pdf_bytes[:4] != b"%PDF":
        log.warning("extract-pdf-fields not a PDF case=%s", case_id)
        raise HTTPException(status_code=400, detail="Uploaded file is not a PDF.")

    # ── 1. Detect PDF type + extract deterministic field map ─────────────────
    extraction = extract_field_map(pdf_bytes)
    log.info(
        "extract-pdf-fields type=%s pages=%d fields=%d case=%s",
        extraction.pdf_type, extraction.total_pages, len(extraction.fields), case_id,
    )

    if not extraction.fields:
        log.info("extract-pdf-fields no fields found case=%s pdf_type=%s", case_id, extraction.pdf_type)
        detail = {
            "acroform": "This PDF has an AcroForm but no extractable widget fields.",
            "flat":     "This PDF has no fillable fields and no recognisable field patterns.",
            "scanned":  "This PDF appears to be a scanned image — OCR is not yet supported.",
        }.get(extraction.pdf_type, "No fields could be extracted from this PDF.")
        raise HTTPException(status_code=422, detail=detail)

    # ── 2. Translate field labels + options via Groq ───────────────────────────
    #    Input: only the exact field_ids from the field map — AI cannot invent new ones
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

    # ── 3. Anti-hallucination validation ──────────────────────────────────────
    report = validate_no_hallucinations(extraction.fields, raw_translations)
    if not report.is_clean:
        log.warning(
            "extract-pdf-fields hallucination case=%s invented=%s missing=%s",
            case_id, report.invented, report.missing,
        )
    log.info(
        "extract-pdf-fields validation clean=%s invented=%d missing=%d case=%s",
        report.is_clean, len(report.invented), len(report.missing), case_id,
    )

    # ── 4. Build field definitions (one per extracted field, no extras) ────────
    prefilled_raw = {e.field_id: e.current_value for e in extraction.fields if e.current_value}
    form_name = storage_path.stem.replace("_", " ").title()

    template_id, _ = create_dynamic_template(
        db=db, case_id=case_id,
        acroform_fields={e.field_id: e.current_value for e in extraction.fields},
        form_name=form_name,
    )
    case.form_template_id  = template_id
    case.status            = CaseStatus.FORM_SELECTED.value
    case.updated_at        = datetime.now(timezone.utc)
    doc.detected_form_type = template_id
    doc.ocr_confidence     = extraction.fields[0].confidence if extraction.fields else 0.5

    db.flush()

    count     = _save_prefilled_answers(db, case_id, template_id, prefilled_raw)
    field_defs = field_map_to_defs(
        extraction.fields,
        report.cleaned_translations,
        set(prefilled_raw.keys()),
        user_language,
        document_language,
    )
    db.commit()

    return UploadResponse(
        document_id=doc.id, detected_form_type=template_id,
        confidence=extraction.fields[0].confidence if extraction.fields else 0.5,
        requires_manual_selection=False,
        prefilled_fields=count, fields=field_defs,
        document_language=document_language, user_language=user_language,
    )


# ── Diagnostic: raw field map ─────────────────────────────────────────────────

@router.get("/{case_id}/analyze-pdf")
async def analyze_pdf(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Returns the raw deterministic field map for the uploaded PDF.

    Shows PDF type, page count, and each extracted field with:
    - field_id (ground truth anchor)
    - original_label (PDF language)
    - field_type
    - source_page + bbox
    - options (for choice fields)
    - confidence + source (acroform | pdfplumber | ocr)

    Use this endpoint to verify extraction BEFORE questions are generated.
    Also reports which questions would be valid (= all extracted fields)
    and which would be hallucinated (= none, by design).
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
        }

    extraction = extract_field_map(pdf_bytes)

    return {
        "pdf_type": extraction.pdf_type,
        "total_pages": extraction.total_pages,
        "field_count": len(extraction.fields),
        "filename": doc.original_filename,
        "fields": [
            {
                "field_id":       e.field_id,
                "original_label": e.original_label,
                "field_type":     e.field_type,
                "source_page":    e.source_page,
                "bbox":           e.bbox,
                "options":        e.options,
                "current_value":  e.current_value,
                "confidence":     e.confidence,
                "source":         e.source,
            }
            for e in extraction.fields
        ],
        "anti_hallucination": {
            "rule": "Every question must reference a field_id from this list.",
            "valid_field_ids": [e.field_id for e in extraction.fields],
        },
    }


# ── Lazy translation endpoint — called fire-and-forget by frontend ─────────────

@router.post("/{case_id}/translate-fields")
async def translate_fields_endpoint(
    case_id: str,
    payload: dict = Body(...),
    user_language: str = Query("en"),
    document_language: str = Query("de"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Runs Groq translation for all fields.
    Called fire-and-forget — not on the critical upload path.
    """
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    fields_input: list[dict] = payload.get("fields", [])
    if not fields_input:
        return {}
    return translate_fields(fields_input, user_language, document_language)


# ── Pre-fill answers from PDF (no translation — values already in PDF lang) ───

def _save_prefilled_answers(db, case_id: str, template_id: str, extracted: dict[str, str]) -> int:
    """
    Store pre-filled values from the uploaded PDF as Answer rows.
    raw_answer = translated_answer = the PDF-native value (no LLM needed).
    """
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
            translated_answer=raw_value,  # pre-fills are already in PDF language
            is_validated=vresult.is_valid,
            validation_errors=json.dumps(vresult.errors),
            is_active=True, answered_at=datetime.now(timezone.utc),
        ))
        count += 1
    return count
