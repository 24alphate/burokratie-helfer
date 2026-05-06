"""
Upload route — three paths:
  A. Fillable PDF with AcroForm widgets   → deterministic field extraction (no hallucination)
  B. Scanned / flat PDF                  → Groq vision field detection
  C. Fallback                            → fixed ALG II template

Every FieldDefinition produced by Path A is grounded in an actual PDF widget.
Path B fields carry confidence < 1.0 and may be marked needs_review.
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
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
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
from app.services.question_translator import translate_fields
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024

# pypdf AcroForm field-type flags
_FF_RADIO       = 1 << 15
_FF_PUSHBUTTON  = 1 << 16
_FF_MULTISELECT = 1 << 21


# ── AcroForm full extraction ───────────────────────────────────────────────────

def _acroform_field_type(ft: str, flags: int) -> Optional[str]:
    """Map PDF field type code + flags → our type string. Returns None to skip."""
    if ft == "/Tx":
        return "text"
    if ft == "/Sig":
        return "signature"
    if ft == "/Ch":
        return "multiselect" if (flags & _FF_MULTISELECT) else "select"
    if ft == "/Btn":
        if flags & _FF_PUSHBUTTON:
            return None        # skip submit/reset buttons
        return "radio" if (flags & _FF_RADIO) else "checkbox"
    return "text"


def _collect_radio_options(reader: pypdf.PdfReader) -> dict[str, list[str]]:
    """
    Walk every page annotation to collect radio-button option values.
    For a radio group "Familienstand" with choices ["ledig","verheiratet",...],
    each child widget has /AP/N/{option_key}. We harvest those keys.
    """
    opts: dict[str, list[str]] = {}
    for page in reader.pages:
        for ref in page.get("/Annots", []):
            try:
                ann = ref.get_object() if hasattr(ref, "get_object") else ref
                parent_ref = ann.get("/Parent")
                parent = (parent_ref.get_object() if hasattr(parent_ref, "get_object")
                          else parent_ref) if parent_ref else None
                fname = str((parent or ann).get("/T", "")).strip().lstrip("/")
                if not fname:
                    continue
                ap = ann.get("/AP", {})
                if hasattr(ap, "get_object"):
                    ap = ap.get_object()
                normal = ap.get("/N", {}) if ap else {}
                if hasattr(normal, "get_object"):
                    normal = normal.get_object()
                for key in (normal.keys() if hasattr(normal, "keys") else []):
                    val = str(key).lstrip("/")
                    if val and val.lower() != "off":
                        opts.setdefault(fname, [])
                        if val not in opts[fname]:
                            opts[fname].append(val)
            except Exception:
                continue
    return opts


def _extract_acroform_full(pdf_bytes: bytes) -> list[dict]:
    """
    Extract every AcroForm field with type, current value, and options.
    Returns list of dicts — order matches the field tree (≈ visual order).
    This is the ground-truth source: every returned field IS in the PDF.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        raw = reader.get_fields()
        if not raw:
            return []

        radio_opts = _collect_radio_options(reader)
        results: list[dict] = []

        for name, field in raw.items():
            clean = name.lstrip("/").strip()
            ft    = str(field.get("/FT", "/Tx"))
            flags = int(str(field.get("/Ff", "0")).strip() or "0")

            ftype = _acroform_field_type(ft, flags)
            if ftype is None:
                continue   # skip push-buttons

            # Current value
            val = field.get("/V") or field.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()
            if val in ("/Off", "Off", "None", "none"):
                val = ""
            elif val.startswith("/"):
                val = val[1:]

            # Options (select / radio / checkbox)
            options: list[str] = []
            if ftype in ("select", "multiselect"):
                raw_opts = field.get("/Opt", [])
                for o in (raw_opts if isinstance(raw_opts, list) else []):
                    options.append(str(o[0]) if isinstance(o, (list, tuple)) else str(o))
            elif ftype == "radio":
                options = radio_opts.get(clean, [])
            elif ftype == "checkbox":
                options = radio_opts.get(clean, ["yes"])

            results.append({
                "field_name":     clean,
                "field_type":     ftype,
                "current_value":  val,
                "options":        options,
                "original_label": clean,   # for AcroForm, widget name IS the label
            })

        return results
    except Exception:
        return []


# ── FieldDefinition builder ────────────────────────────────────────────────────

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
        fname   = f["field_name"]
        ftype   = f["field_type"]
        raw_lbl = f.get("original_label", fname)
        f_opts  = f.get("options", [])

        tr = translations.get(fname, {})
        question_text = tr.get("question") or _fallback_question(fname, user_language)
        explanation   = tr.get("explanation", "")
        tr_opts       = tr.get("translated_options", {})  # {orig_val: translated_label}

        options: list[FieldOption] = []
        for orig_val in f_opts:
            translated_label = tr_opts.get(orig_val, orig_val)
            options.append(FieldOption(value=orig_val, label=translated_label))

        defs.append(FieldDefinition(
            key=fname,
            question={user_language: question_text},
            explanation={user_language: explanation},
            input_type=ftype,
            options=options,
            original_label=raw_lbl,
            document_language=document_language,
            source_page=1,
            order=i,
            is_prefilled=(fname in prefilled_keys),
            confidence=confidence,
            needs_review=(confidence < 0.6),
        ))
    return defs


def _fallback_question(field_name: str, lang: str) -> str:
    q = make_question_for_field(field_name)
    return q["question_text"].get(lang, q["question_text"].get("en", field_name))


# ── Upload route ───────────────────────────────────────────────────────────────

@router.post("/{case_id}/upload", response_model=UploadResponse)
async def upload_document(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    user_language: str = Query("en", description="User's preferred guide language (ISO 639-1)"),
    document_language: str = Query("de", description="Detected document language"),
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

    is_pdf    = content[:4] == b"%PDF"
    form_name = Path(file.filename or "Uploaded Form").stem.replace("_", " ").title()
    ocr_svc   = request.app.state.ocr_service
    trans_svc = request.app.state.translation_service

    # ── Path A: AcroForm — ground-truth extraction, zero hallucination ─────────
    extracted_fields: list[dict] = []
    if is_pdf:
        extracted_fields = _extract_acroform_full(content)

    if extracted_fields:
        # Translate all field labels + options into user's language (one Groq call)
        translations = translate_fields(extracted_fields, user_language, document_language)

        prefilled_raw = {f["field_name"]: f["current_value"]
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
            extracted=extracted_fields,
            translations=translations,
            prefilled_keys=set(prefilled_raw.keys()),
            user_language=user_language,
            document_language=document_language,
            confidence=1.0,
        )

        audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
            "document_id": doc.id, "mode": "acroform",
            "total_fields": len(extracted_fields),
            "prefilled_fields": prefilled_count,
            "user_language": user_language,
        })
        db.commit()

        return UploadResponse(
            document_id=doc.id, detected_form_type=template_id,
            confidence=1.0, requires_manual_selection=False,
            prefilled_fields=prefilled_count,
            fields=field_defs,
            document_language=document_language,
            user_language=user_language,
        )

    # ── Path B: scanned/flat — vision field detection ─────────────────────────
    vision_fields: list[dict] = await ocr_svc.detect_all_fields(content)

    if vision_fields:
        translations = translate_fields(vision_fields, user_language, document_language)
        prefilled_raw = {f["label"]: f["value"]
                         for f in vision_fields if f.get("value")}
        acroform_style = {f["label"]: (f.get("value") or "") for f in vision_fields}

        template_id, _ = create_dynamic_template(
            db=db, case_id=case_id,
            acroform_fields=acroform_style,
            form_name=form_name,
        )
        case.form_template_id = template_id
        case.status           = CaseStatus.FORM_SELECTED.value
        case.updated_at       = datetime.now(timezone.utc)

        doc = UploadedDocument(
            case_id=case_id, original_filename=file.filename or "upload",
            storage_path=str(dest), ocr_text=None,
            detected_form_type=template_id, ocr_confidence=0.8,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()

        prefilled_count = await _save_answers(
            db, case_id, template_id, prefilled_raw, trans_svc
        )

        # Convert vision dicts to the same format as AcroForm extraction
        extracted_for_defs = [{
            "field_name":     f["label"],
            "field_type":     _map_vision_type(f.get("field_type", "text")),
            "options":        f.get("options", []),
            "original_label": f["label"],
            "current_value":  f.get("value", ""),
        } for f in vision_fields]

        field_defs = _build_field_defs(
            extracted=extracted_for_defs,
            translations=translations,
            prefilled_keys=set(prefilled_raw.keys()),
            user_language=user_language,
            document_language=document_language,
            confidence=0.75,
        )

        audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
            "document_id": doc.id, "mode": "vision_dynamic",
            "total_fields": len(vision_fields),
            "prefilled_fields": prefilled_count,
            "user_language": user_language,
        })
        db.commit()

        return UploadResponse(
            document_id=doc.id, detected_form_type=template_id,
            confidence=0.8, requires_manual_selection=False,
            prefilled_fields=prefilled_count,
            fields=field_defs,
            document_language=document_language,
            user_language=user_language,
        )

    # ── Path C: fixed ALG II template fallback ────────────────────────────────
    ocr_result   = await ocr_svc.extract_text(content)
    detected_type = await ocr_svc.detect_form_type(ocr_result)

    if not detected_type or ocr_result.confidence < 0.7:
        all_templates = db.query(FormTemplate).filter(
            ~FormTemplate.id.startswith("dyn_")
        ).all()
        if len(all_templates) == 1:
            detected_type = all_templates[0].id

    if detected_type:
        case.form_template_id = detected_type
        case.status = CaseStatus.FORM_SELECTED.value
    else:
        case.status = CaseStatus.UPLOADED.value
    case.updated_at = datetime.now(timezone.utc)

    doc = UploadedDocument(
        case_id=case_id, original_filename=file.filename or "upload",
        storage_path=str(dest), ocr_text=None,
        detected_form_type=detected_type, ocr_confidence=ocr_result.confidence,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()

    extracted_kv = dict(ocr_result.metadata.get("extracted_fields", {}))
    prefilled_count = 0
    field_defs: list[FieldDefinition] = []

    if detected_type:
        prefilled_count = await _save_answers(
            db, case_id, detected_type, extracted_kv, trans_svc
        )
        questions = db.query(Question).filter(
            Question.template_id == detected_type
        ).order_by(Question.order_index).all()

        # Build raw field list for one-shot translation
        raw_for_tr = [{"field_name": q.field_key, "field_type": q.input_type,
                        "options": [], "original_label": q.field_key}
                       for q in questions]
        translations = translate_fields(raw_for_tr, user_language, document_language)

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
                is_prefilled=(q.field_key in extracted_kv and bool(extracted_kv[q.field_key])),
                confidence=0.5,
            ))

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id, "mode": "fixed_template",
        "detected_form_type": detected_type,
        "confidence": round(ocr_result.confidence, 3),
        "prefilled_fields": prefilled_count,
        "user_language": user_language,
    })
    db.commit()

    return UploadResponse(
        document_id=doc.id, detected_form_type=detected_type,
        confidence=ocr_result.confidence,
        requires_manual_selection=not detected_type,
        prefilled_fields=prefilled_count,
        fields=field_defs,
        document_language=document_language,
        user_language=user_language,
    )


def _map_vision_type(vtype: str) -> str:
    """Map vision-detected type string to our canonical types."""
    m = {"checkbox": "checkbox", "radio": "radio", "select": "select",
         "date": "date", "text": "text", "signature": "signature", "number": "number"}
    return m.get(vtype.lower(), "text")


async def _save_answers(
    db: Session, case_id: str, template_id: str,
    extracted: dict[str, str], translation_service,
) -> int:
    if not extracted:
        return 0
    fields    = db.query(FormField).filter(FormField.template_id == template_id).all()
    valid_keys = {f.field_key: f for f in fields}
    count     = 0
    for field_key, raw_value in extracted.items():
        if not raw_value or field_key not in valid_keys:
            continue
        field  = valid_keys[field_key]
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
