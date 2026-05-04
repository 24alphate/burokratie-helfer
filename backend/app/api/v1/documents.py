import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.answer import Answer
from app.models.audit_log import AuditAction
from app.models.case import Case, CaseStatus
from app.models.document import UploadedDocument
from app.models.form_template import FormField
from app.models.user import User
from app.schemas.document import UploadResponse
from app.services.audit_service import audit_service
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


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

    # Run OCR — real (Claude) or mock depending on OCR_BACKEND env var
    ocr_service = request.app.state.ocr_service
    ocr_result = await ocr_service.extract_text(content)
    detected_type = await ocr_service.detect_form_type(ocr_result)

    doc = UploadedDocument(
        case_id=case_id,
        original_filename=file.filename or "upload",
        storage_path=str(dest),
        ocr_text=None,  # raw text never stored — PII risk
        detected_form_type=detected_type,
        ocr_confidence=ocr_result.confidence,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()

    # Set form type on case if OCR detected it with high confidence
    if detected_type and ocr_result.confidence >= 0.7:
        case.form_template_id = detected_type
        case.status = CaseStatus.FORM_SELECTED.value
    else:
        case.status = CaseStatus.UPLOADED.value
    case.updated_at = datetime.now(timezone.utc)

    # Pre-fill answers from extracted fields (skips those questions in questionnaire)
    extracted = ocr_result.metadata.get("extracted_fields", {})
    prefilled_count = 0
    if extracted and case.form_template_id:
        fields = db.query(FormField).filter(
            FormField.template_id == case.form_template_id
        ).all()
        valid_keys = {f.field_key: f for f in fields}

        translation_service = request.app.state.translation_service

        for field_key, raw_value in extracted.items():
            if not raw_value or field_key not in valid_keys:
                continue

            # Validate the extracted value
            field = valid_keys[field_key]
            vresult = validation_service.validate_answer(
                raw_value, field.validation_rules, language="de"
            )

            # Translate to German (extracted values may already be German)
            translation = await translation_service.translate(
                raw_value, source_language="de", target_language="de",
                field_context=field_key,
            )

            # Remove any existing answer for this field first
            db.query(Answer).filter(
                Answer.case_id == case_id,
                Answer.field_key == field_key,
                Answer.is_active == True,
            ).update({"is_active": False})

            answer = Answer(
                case_id=case_id,
                field_key=field_key,
                raw_answer=raw_value,
                translated_answer=translation.translated_text,
                is_validated=vresult.is_valid,
                validation_errors=json.dumps(vresult.errors),
                is_active=True,
                answered_at=datetime.now(timezone.utc),
            )
            db.add(answer)
            prefilled_count += 1

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id,
        "detected_form_type": detected_type,
        "confidence": round(ocr_result.confidence, 3),
        "prefilled_fields": prefilled_count,
    })
    db.commit()

    return UploadResponse(
        document_id=doc.id,
        detected_form_type=detected_type,
        confidence=ocr_result.confidence,
        requires_manual_selection=(not detected_type or ocr_result.confidence < 0.7),
    )
