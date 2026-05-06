"""
Upload route — always returns in < 2s on Vercel, zero LLM calls, zero pypdf on upload.

Flow:
  1. Upload → saves file, returns Path B (fixed template) immediately
  2. Frontend fires POST /cases/{id}/extract-pdf-fields (fire-and-forget, no timeout pressure)
  3. extract-pdf-fields reads AcroForm, creates dynamic template, returns FieldDefinitions
  4. Frontend merges returned fields into Zustand, replacing the generic ones

Groq / LLM calls happen ONLY in the /translate-fields endpoint.
"""
from __future__ import annotations

import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pypdf
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

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
from app.services.dynamic_form_service import create_dynamic_template, make_question_for_field
from app.services.question_translator import static_fallback, translate_fields
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024
MAX_ACROFORM_FIELDS = 120   # safety cap — very large forms can cause OOM

_FF_RADIO       = 1 << 15
_FF_PUSHBUTTON  = 1 << 16
_FF_MULTISELECT = 1 << 21


# ── AcroForm extraction (called ONLY from background endpoint, not from upload) ──

def _acroform_field_type(ft: str, flags: int) -> Optional[str]:
    if ft == "/Tx":   return "text"
    if ft == "/Sig":  return "signature"
    if ft == "/Ch":   return "multiselect" if (flags & _FF_MULTISELECT) else "select"
    if ft == "/Btn":
        if flags & _FF_PUSHBUTTON: return None
        return "radio" if (flags & _FF_RADIO) else "checkbox"
    return "text"


def _extract_acroform_shallow(pdf_bytes: bytes) -> list[dict]:
    """
    Lightweight AcroForm extraction — reads only the top-level /Fields array,
    no recursive descent into child widgets, no annotation walk.
    Called from the background /extract-pdf-fields endpoint only.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

        # Navigate to AcroForm without calling the expensive get_fields()
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

        results: list[dict] = []
        seen_names: set[str] = set()

        for field_ref in list(fields_array)[:MAX_ACROFORM_FIELDS]:
            try:
                field = field_ref.get_object() if hasattr(field_ref, "get_object") else field_ref

                name = field.get("/T", "")
                if hasattr(name, "get_object"):
                    name = name.get_object()
                clean = str(name).lstrip("/").strip()
                if not clean or clean in seen_names:
                    continue
                seen_names.add(clean)

                ft = str(field.get("/FT", "/Tx"))
                try:
                    flags = int(str(field.get("/Ff", "0")).split(".")[0] or "0")
                except (ValueError, TypeError):
                    flags = 0

                ftype = _acroform_field_type(ft, flags) or "text"

                val = field.get("/V") or field.get("/DV") or ""
                if hasattr(val, "raw_value"):
                    val = val.raw_value
                val = str(val).strip()
                if val in ("/Off", "Off", "None", "none"):
                    val = ""
                elif val.startswith("/"):
                    val = val[1:]

                options: list[str] = []
                if ftype in ("select", "multiselect"):
                    try:
                        raw_opts = field.get("/Opt", [])
                        for o in (raw_opts if isinstance(raw_opts, list) else []):
                            options.append(str(o[0]) if isinstance(o, (list, tuple)) else str(o))
                    except Exception:
                        options = []

                results.append({
                    "field_name": clean,
                    "field_type": ftype,
                    "current_value": val,
                    "options": options,
                    "original_label": clean,
                })
            except Exception:
                continue

        return results
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
        options = [FieldOption(value=v, label=tr_opts.get(v, v)) for v in f.get("options", [])]
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


# ── Upload route — always returns < 2s, zero PDF parsing ─────────────────────

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
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"File too large. Max {settings.max_upload_size_mb}MB.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    suffix  = Path(file.filename or "upload.pdf").suffix or ".pdf"
    dest    = upload_dir / f"{file_id}{suffix}"
    dest.write_bytes(content)

    # ── Use fixed template immediately (no PDF parsing on upload path) ────────
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

    return UploadResponse(
        document_id=doc.id, detected_form_type=detected_type,
        confidence=0.5, requires_manual_selection=not detected_type,
        prefilled_fields=0, fields=field_defs,
        document_language=document_language, user_language=user_language,
    )


# ── PDF field extraction — called fire-and-forget AFTER upload returns ────────

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
    Reads AcroForm fields from the most-recently uploaded PDF for this case.
    Called fire-and-forget by the frontend immediately after upload completes.
    Has no Vercel timeout pressure because the upload response was already sent.
    Returns a full UploadResponse so the frontend can replace its field list.
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

    extracted_fields = _extract_acroform_shallow(pdf_bytes)
    if not extracted_fields:
        raise HTTPException(status_code=422, detail="No AcroForm fields found in PDF.")

    trans_svc = None  # not needed here — we use static_fallback
    translations   = static_fallback(extracted_fields, user_language)
    prefilled_raw  = {f["field_name"]: f["current_value"]
                      for f in extracted_fields if f["current_value"]}
    form_name = storage_path.stem.replace("_", " ").title()

    # Delete any previous dynamic template for this case, create a fresh one
    template_id, _ = create_dynamic_template(
        db=db, case_id=case_id,
        acroform_fields={f["field_name"]: f["current_value"] for f in extracted_fields},
        form_name=form_name,
    )
    case.form_template_id = template_id
    case.status           = CaseStatus.FORM_SELECTED.value
    case.updated_at       = datetime.now(timezone.utc)
    doc.detected_form_type = template_id
    doc.ocr_confidence     = 1.0

    db.flush()

    # Save pre-filled answers if any
    count = await _save_answers(db, case_id, template_id, prefilled_raw)

    field_defs = _build_field_defs(
        extracted_fields, translations,
        set(prefilled_raw.keys()), user_language, document_language, 1.0,
    )
    db.commit()

    return UploadResponse(
        document_id=doc.id, detected_form_type=template_id,
        confidence=1.0, requires_manual_selection=False,
        prefilled_fields=count, fields=field_defs,
        document_language=document_language, user_language=user_language,
    )


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
    Runs Groq translation for all fields in user's language.
    Safe to call async — runs in its own request, not on the critical upload path.
    """
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    fields_input: list[dict] = payload.get("fields", [])
    if not fields_input:
        return {}
    return translate_fields(fields_input, user_language, document_language)


async def _save_answers(db, case_id, template_id, extracted) -> int:
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
            Answer.case_id == case_id, Answer.field_key == field_key, Answer.is_active == True,
        ).update({"is_active": False})
        db.add(Answer(
            case_id=case_id, field_key=field_key, raw_answer=raw_value,
            translated_answer=raw_value,
            is_validated=vresult.is_valid,
            validation_errors=json.dumps(vresult.errors),
            is_active=True, answered_at=datetime.now(timezone.utc),
        ))
        count += 1
    return count
