import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pypdf
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
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
from app.schemas.document import FieldDefinition, UploadResponse
from app.services.audit_service import audit_service
from app.services.dynamic_form_service import create_dynamic_template, make_question_for_field
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ── AcroForm extraction ────────────────────────────────────────────────────────

def _extract_acroform_fields(pdf_bytes: bytes) -> dict[str, str]:
    """Extract every AcroForm widget from a digital PDF. Returns {name: value_or_empty}."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        raw = reader.get_fields()
        if not raw:
            return {}
        result: dict[str, str] = {}
        for name, field in raw.items():
            clean = name.lstrip("/").strip()
            val = field.get("/V") or field.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()
            if val in ("/Off", "Off", "/No", "No"):
                val = "no"
            elif val.startswith("/"):
                val = val[1:]
            elif val in ("None", "none", "null"):
                val = ""
            result[clean] = val
        return result
    except Exception:
        return {}


# ── Field definition builder ──────────────────────────────────────────────────

def _build_field_definitions(
    field_names: list[str],
    prefilled_keys: set[str],
) -> list[FieldDefinition]:
    defs = []
    for i, name in enumerate(field_names, 1):
        q = make_question_for_field(name)
        defs.append(FieldDefinition(
            key=name,
            question=q["question_text"],
            explanation=q["explanation_text"],
            input_type=q["input_type"],
            order=i,
            is_prefilled=(name in prefilled_keys),
        ))
    return defs


# ── Upload route ───────────────────────────────────────────────────────────────

@router.post("/{case_id}/upload", response_model=UploadResponse)
async def upload_document(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user.id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {settings.max_upload_size_mb}MB.",
        )

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    dest = upload_dir / f"{file_id}{suffix}"
    dest.write_bytes(content)

    form_name = Path(file.filename or "Uploaded Form").stem.replace("_", " ").title()
    ocr_service = request.app.state.ocr_service
    translation_service = request.app.state.translation_service

    # ── Path A: fillable PDF with AcroForm fields ─────────────────────────────
    is_pdf = content[:4] == b"%PDF"
    acroform_raw: dict[str, str] = {}
    if is_pdf:
        acroform_raw = _extract_acroform_fields(content)

    if acroform_raw:
        template_id, prefilled_from_acroform = create_dynamic_template(
            db=db, case_id=case_id,
            acroform_fields=acroform_raw, form_name=form_name,
        )
        case.form_template_id = template_id
        case.status = CaseStatus.FORM_SELECTED.value
        case.updated_at = datetime.now(timezone.utc)

        doc = UploadedDocument(
            case_id=case_id, original_filename=file.filename or "upload",
            storage_path=str(dest), ocr_text=None,
            detected_form_type=template_id, ocr_confidence=1.0,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()

        prefilled_count = await _save_answers(
            db, case_id, template_id, prefilled_from_acroform, translation_service
        )

        field_defs = _build_field_definitions(
            list(acroform_raw.keys()), set(prefilled_from_acroform.keys())
        )

        audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
            "document_id": doc.id, "mode": "acroform",
            "total_fields": len(acroform_raw), "prefilled_fields": prefilled_count,
        })
        db.commit()

        return UploadResponse(
            document_id=doc.id, detected_form_type=template_id,
            confidence=1.0, requires_manual_selection=False,
            prefilled_fields=prefilled_count, fields=field_defs,
        )

    # ── Path B: scanned / flat PDF — use vision to detect all fields ──────────
    detected_fields: list[dict] = await ocr_service.detect_all_fields(content)

    if detected_fields:
        # Vision found fields → create dynamic template from visual form structure
        acroform_style = {f["label"]: (f["value"] or "") for f in detected_fields}
        template_id, prefilled_from_vision = create_dynamic_template(
            db=db, case_id=case_id,
            acroform_fields=acroform_style, form_name=form_name,
        )
        case.form_template_id = template_id
        case.status = CaseStatus.FORM_SELECTED.value
        case.updated_at = datetime.now(timezone.utc)

        doc = UploadedDocument(
            case_id=case_id, original_filename=file.filename or "upload",
            storage_path=str(dest), ocr_text=None,
            detected_form_type=template_id, ocr_confidence=0.85,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()

        prefilled_count = await _save_answers(
            db, case_id, template_id, prefilled_from_vision, translation_service
        )

        field_defs = _build_field_definitions(
            [f["label"] for f in detected_fields],
            set(prefilled_from_vision.keys()),
        )

        audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
            "document_id": doc.id, "mode": "vision_dynamic",
            "total_fields": len(detected_fields), "prefilled_fields": prefilled_count,
        })
        db.commit()

        return UploadResponse(
            document_id=doc.id, detected_form_type=template_id,
            confidence=0.85, requires_manual_selection=False,
            prefilled_fields=prefilled_count, fields=field_defs,
        )

    # ── Path C: fallback — fixed ALG II template (Groq offline / image not a form) ──
    ocr_result = await ocr_service.extract_text(content)
    detected_type = await ocr_service.detect_form_type(ocr_result)

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

    extracted = dict(ocr_result.metadata.get("extracted_fields", {}))
    prefilled_count = 0
    field_defs: list[FieldDefinition] = []

    if detected_type:
        prefilled_count = await _save_answers(
            db, case_id, detected_type, extracted, translation_service
        )
        # Build field defs from the fixed template's questions
        questions = db.query(Question).filter(
            Question.template_id == detected_type
        ).order_by(Question.order_index).all()
        for q in questions:
            qt = json.loads(q.question_text)
            et = json.loads(q.explanation_text)
            field_defs.append(FieldDefinition(
                key=q.field_key,
                question=qt,
                explanation=et,
                input_type=q.input_type,
                order=q.order_index,
                is_prefilled=(q.field_key in extracted and bool(extracted[q.field_key])),
            ))

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id, "mode": "fixed_template",
        "detected_form_type": detected_type,
        "confidence": round(ocr_result.confidence, 3),
        "prefilled_fields": prefilled_count,
    })
    db.commit()

    return UploadResponse(
        document_id=doc.id, detected_form_type=detected_type,
        confidence=ocr_result.confidence,
        requires_manual_selection=not detected_type,
        prefilled_fields=prefilled_count, fields=field_defs,
    )


async def _save_answers(
    db: Session, case_id: str, template_id: str,
    extracted: dict[str, str], translation_service,
) -> int:
    if not extracted:
        return 0
    fields = db.query(FormField).filter(FormField.template_id == template_id).all()
    valid_keys = {f.field_key: f for f in fields}
    count = 0
    for field_key, raw_value in extracted.items():
        if not raw_value or field_key not in valid_keys:
            continue
        field = valid_keys[field_key]
        vresult = validation_service.validate_answer(raw_value, field.validation_rules, language="de")
        translation = await translation_service.translate(
            raw_value, source_language="de", target_language="de", field_context=field_key,
        )
        db.query(Answer).filter(
            Answer.case_id == case_id, Answer.field_key == field_key, Answer.is_active == True,
        ).update({"is_active": False})
        db.add(Answer(
            case_id=case_id, field_key=field_key, raw_answer=raw_value,
            translated_answer=translation.translated_text,
            is_validated=vresult.is_valid, validation_errors=json.dumps(vresult.errors),
            is_active=True, answered_at=datetime.now(timezone.utc),
        ))
        count += 1
    return count
