"""
Upload route — guaranteed < 3s on Vercel, zero LLM calls.

Three paths, all fast:
  A. Fillable PDF with AcroForm widgets → pypdf (no network, no LLM)
  B. Any other PDF / image             → fixed template from DB (no LLM)
  C. No template found                 → requires_manual_selection=True

Groq / LLM calls happen ONLY in the /translate-fields endpoint which is
called fire-and-forget by the frontend after the upload succeeds.
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

_FF_RADIO       = 1 << 15
_FF_PUSHBUTTON  = 1 << 16
_FF_MULTISELECT = 1 << 21


# ── AcroForm extraction (no network, < 500ms for any PDF) ─────────────────────

def _acroform_field_type(ft: str, flags: int) -> Optional[str]:
    if ft == "/Tx":   return "text"
    if ft == "/Sig":  return "signature"
    if ft == "/Ch":   return "multiselect" if (flags & _FF_MULTISELECT) else "select"
    if ft == "/Btn":
        if flags & _FF_PUSHBUTTON: return None
        return "radio" if (flags & _FF_RADIO) else "checkbox"
    return "text"



def _extract_acroform_full(pdf_bytes: bytes) -> list[dict]:
    """Ground-truth extraction. Every returned field IS in the PDF. No network calls."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        raw = reader.get_fields()
        if not raw:
            return []
        results: list[dict] = []
        for name, field in raw.items():
            clean = name.lstrip("/").strip()
            ft    = str(field.get("/FT", "/Tx"))
            try:
                flags = int(str(field.get("/Ff", "0")).strip().split(".")[0] or "0")
            except (ValueError, TypeError):
                flags = 0
            ftype = _acroform_field_type(ft, flags)
            if ftype is None:
                continue
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
                "field_name": clean, "field_type": ftype,
                "current_value": val, "options": options,
                "original_label": clean,
            })
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


# ── Upload route (zero LLM calls — always returns in < 3s) ────────────────────

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

    form_name = Path(file.filename or "Uploaded Form").stem.replace("_", " ").title()
    trans_svc = request.app.state.translation_service

    # ── Path A: AcroForm fields found — fastest, most accurate ───────────────
    extracted_fields: list[dict] = []
    if content[:4] == b"%PDF":
        extracted_fields = _extract_acroform_full(content)

    if extracted_fields:
        try:
            translations   = static_fallback(extracted_fields, user_language)
            prefilled_raw  = {f["field_name"]: f["current_value"]
                              for f in extracted_fields if f["current_value"]}

            template_id, _ = create_dynamic_template(
                db=db, case_id=case_id,
                acroform_fields={f["field_name"]: f["current_value"] for f in extracted_fields},
                form_name=form_name,
            )
            case.form_template_id = template_id
            case.status           = CaseStatus.FORM_SELECTED.value
            case.updated_at       = datetime.now(timezone.utc)

            doc = UploadedDocument(
                case_id=case_id, original_filename=file.filename or "upload",
                storage_path=str(dest), ocr_text=None,
                detected_form_type=template_id, ocr_confidence=1.0,
                uploaded_at=datetime.now(timezone.utc),
            )
            db.add(doc)
            db.flush()

            prefilled_count = await _save_answers(
                db, case_id, template_id, prefilled_raw, trans_svc
            )
            field_defs = _build_field_defs(
                extracted_fields, translations,
                set(prefilled_raw.keys()), user_language, document_language, 1.0,
            )
            audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
                "document_id": doc.id, "mode": "acroform",
                "total_fields": len(extracted_fields), "prefilled_fields": prefilled_count,
            })
            db.commit()
            return UploadResponse(
                document_id=doc.id, detected_form_type=template_id,
                confidence=1.0, requires_manual_selection=False,
                prefilled_fields=prefilled_count, fields=field_defs,
                document_language=document_language, user_language=user_language,
            )
        except Exception:
            db.rollback()
            extracted_fields = []  # fall through to Path B

    # ── Path B: no AcroForm — use fixed template from DB (no LLM) ────────────
    # Scanned / image PDFs land here. OCR/vision runs via /translate-fields later.
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

    field_defs = []
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
        "document_id": doc.id, "mode": "fixed_template_fallback",
        "detected_form_type": detected_type,
    })
    db.commit()

    return UploadResponse(
        document_id=doc.id, detected_form_type=detected_type,
        confidence=0.5, requires_manual_selection=not detected_type,
        prefilled_fields=0, fields=field_defs,
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


async def _save_answers(db, case_id, template_id, extracted, translation_service) -> int:
    if not extracted:
        return 0
    fields    = db.query(FormField).filter(FormField.template_id == template_id).all()
    valid_keys = {f.field_key: f for f in fields}
    count = 0
    for field_key, raw_value in extracted.items():
        if not raw_value or field_key not in valid_keys:
            continue
        field   = valid_keys[field_key]
        vresult = validation_service.validate_answer(raw_value, field.validation_rules, language="de")
        translation = await translation_service.translate(
            raw_value, source_language="de", target_language="de",
            field_context=field_key,
        )
        db.query(Answer).filter(
            Answer.case_id == case_id, Answer.field_key == field_key, Answer.is_active == True,
        ).update({"is_active": False})
        db.add(Answer(
            case_id=case_id, field_key=field_key, raw_answer=raw_value,
            translated_answer=translation.translated_text,
            is_validated=vresult.is_valid,
            validation_errors=json.dumps(vresult.errors),
            is_active=True, answered_at=datetime.now(timezone.utc),
        ))
        count += 1
    return count
