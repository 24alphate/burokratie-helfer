import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.case import Case, CaseStatus
from app.models.document import UploadedDocument
from app.models.user import User
from app.models.audit_log import AuditAction
from app.schemas.document import UploadResponse
from app.services.audit_service import audit_service

router = APIRouter(prefix="/cases", tags=["documents"])

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/tiff"}
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
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    dest = upload_dir / f"{file_id}{suffix}"
    dest.write_bytes(content)

    ocr_service = request.app.state.ocr_service
    ocr_result = await ocr_service.extract_text(content)
    detected_type = await ocr_service.detect_form_type(ocr_result)

    doc = UploadedDocument(
        case_id=case_id,
        original_filename=file.filename or "upload",
        storage_path=str(dest),
        ocr_text=None,  # never stored in plaintext — PII risk
        detected_form_type=detected_type,
        ocr_confidence=ocr_result.confidence,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.flush()

    case.status = CaseStatus.UPLOADED.value
    if detected_type and ocr_result.confidence >= 0.8:
        case.form_template_id = detected_type
        case.status = CaseStatus.FORM_SELECTED.value
    case.updated_at = datetime.now(timezone.utc)

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id,
        "detected_form_type": detected_type,
        "confidence": round(ocr_result.confidence, 3),
    })
    db.commit()

    return UploadResponse(
        document_id=doc.id,
        detected_form_type=detected_type,
        confidence=ocr_result.confidence,
        requires_manual_selection=(detected_type is None or ocr_result.confidence < 0.8),
    )
