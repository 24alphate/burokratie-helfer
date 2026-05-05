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
from app.models.user import User
from app.schemas.document import UploadResponse
from app.services.audit_service import audit_service
from app.services.dynamic_form_service import create_dynamic_template
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ── AcroForm extraction ────────────────────────────────────────────────────────

def _extract_acroform_fields(pdf_bytes: bytes) -> dict[str, str]:
    """
    Extract every AcroForm widget field from a digital PDF.
    Returns {widget_name: current_value} — value is "" for empty fields.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        raw_fields = reader.get_fields()
        if not raw_fields:
            return {}

        result: dict[str, str] = {}
        for name, field in raw_fields.items():
            clean = name.lstrip("/").strip()
            val = field.get("/V") or field.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()
            if val in ("/Off", "Off", "/No", "No"):
                val = "no"
            elif val.startswith("/"):
                val = val[1:]  # strip leading slash from /Yes, /Ja, etc.
            elif val in ("None", "none", "null"):
                val = ""
            result[clean] = val
        return result
    except Exception:
        return {}


# ── Helpers for fallback (fixed-template) path ───────────────────────────────

def _build_reverse_map(pdf_field_map: dict[str, str]) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for field_key, pdf_name in pdf_field_map.items():
        reverse[pdf_name] = field_key
        reverse[pdf_name.lower()] = field_key
        plain = re.sub(r"[^a-z0-9]", "", pdf_name.lower())
        if plain:
            reverse[plain] = field_key
    return reverse


def _match_to_template(
    acroform: dict[str, str],
    reverse_map: dict[str, str],
) -> dict[str, str]:
    matched: dict[str, str] = {}
    for pdf_name, value in acroform.items():
        if not value:
            continue
        fk = (reverse_map.get(pdf_name)
              or reverse_map.get(pdf_name.lower())
              or reverse_map.get(re.sub(r"[^a-z0-9]", "", pdf_name.lower())))
        if not fk:
            for key, candidate in reverse_map.items():
                if len(key) >= 4 and key in pdf_name.lower():
                    fk = candidate
                    break
        if fk:
            matched[fk] = value
    return matched


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

    is_pdf = content[:4] == b"%PDF"

    # ── Path A: AcroForm-based PDF (any fillable form) ────────────────────────
    # Read the PDF's own field structure — no AI, no template needed.
    acroform_raw: dict[str, str] = {}
    if is_pdf:
        acroform_raw = _extract_acroform_fields(content)

    if acroform_raw:
        # Create a case-specific dynamic template from the PDF's own fields
        template_id, prefilled_from_pdf = create_dynamic_template(
            db=db,
            case_id=case_id,
            acroform_fields=acroform_raw,
            form_name=Path(file.filename or "Uploaded Form").stem.replace("_", " ").title(),
        )

        # Also run OCR in parallel to enrich pre-filling (fills scanned parts)
        ocr_service = request.app.state.ocr_service
        ocr_result = await ocr_service.extract_text(content)
        # Merge: PDF AcroForm values override OCR guesses
        extracted = dict(ocr_result.metadata.get("extracted_fields", {}))
        extracted.update(prefilled_from_pdf)  # AcroForm wins

        case.form_template_id = template_id
        case.status = CaseStatus.FORM_SELECTED.value
        case.updated_at = datetime.now(timezone.utc)

        doc = UploadedDocument(
            case_id=case_id,
            original_filename=file.filename or "upload",
            storage_path=str(dest),
            ocr_text=None,
            detected_form_type=template_id,
            ocr_confidence=1.0,
            uploaded_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()

        # Pre-fill Answer rows for all fields that had values in the PDF
        prefilled_count = await _save_prefilled_answers(
            db, case_id, template_id, extracted, request
        )

        audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
            "document_id": doc.id,
            "mode": "acroform_dynamic",
            "total_fields": len(acroform_raw),
            "prefilled_fields": prefilled_count,
        })
        db.commit()

        return UploadResponse(
            document_id=doc.id,
            detected_form_type=template_id,
            confidence=1.0,
            requires_manual_selection=False,
            prefilled_fields=prefilled_count,
        )

    # ── Path B: Non-AcroForm PDF / image (scanned form, fixed ALG II template) ─
    ocr_service = request.app.state.ocr_service
    ocr_result = await ocr_service.extract_text(content)
    detected_type = await ocr_service.detect_form_type(ocr_result)

    # Auto-select the only available template when OCR is uncertain
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
        case_id=case_id,
        original_filename=file.filename or "upload",
        storage_path=str(dest),
        ocr_text=None,
        detected_form_type=detected_type,
        ocr_confidence=ocr_result.confidence,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()

    extracted = dict(ocr_result.metadata.get("extracted_fields", {}))

    # Enrich with reverse-mapped AcroForm values (shouldn't be many since no fields found,
    # but handle the edge case where a few were found but not enough to trigger Path A)
    if acroform_raw and detected_type:
        template = db.query(FormTemplate).filter_by(id=detected_type).first()
        if template:
            pdf_map = json.loads(template.pdf_field_map)
            rev = _build_reverse_map(pdf_map)
            acroform_matched = _match_to_template(acroform_raw, rev)
            extracted.update(acroform_matched)

    prefilled_count = 0
    if extracted and case.form_template_id:
        prefilled_count = await _save_prefilled_answers(
            db, case_id, case.form_template_id, extracted, request
        )

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id,
        "mode": "ocr_fixed_template",
        "detected_form_type": detected_type,
        "confidence": round(ocr_result.confidence, 3),
        "prefilled_fields": prefilled_count,
    })
    db.commit()

    return UploadResponse(
        document_id=doc.id,
        detected_form_type=detected_type,
        confidence=ocr_result.confidence,
        requires_manual_selection=not detected_type,
        prefilled_fields=prefilled_count,
    )


async def _save_prefilled_answers(
    db: Session,
    case_id: str,
    template_id: str,
    extracted: dict[str, str],
    request,
) -> int:
    """Save extracted field values as pre-filled Answer rows. Returns count saved."""
    if not extracted:
        return 0

    fields = db.query(FormField).filter(FormField.template_id == template_id).all()
    valid_keys = {f.field_key: f for f in fields}
    translation_service = request.app.state.translation_service
    count = 0

    for field_key, raw_value in extracted.items():
        if not raw_value or field_key not in valid_keys:
            continue

        field = valid_keys[field_key]
        vresult = validation_service.validate_answer(
            raw_value, field.validation_rules, language="de"
        )
        translation = await translation_service.translate(
            raw_value, source_language="de", target_language="de",
            field_context=field_key,
        )

        db.query(Answer).filter(
            Answer.case_id == case_id,
            Answer.field_key == field_key,
            Answer.is_active == True,
        ).update({"is_active": False})

        db.add(Answer(
            case_id=case_id,
            field_key=field_key,
            raw_answer=raw_value,
            translated_answer=translation.translated_text,
            is_validated=vresult.is_valid,
            validation_errors=json.dumps(vresult.errors),
            is_active=True,
            answered_at=datetime.now(timezone.utc),
        ))
        count += 1

    return count
