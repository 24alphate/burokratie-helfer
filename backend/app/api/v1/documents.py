import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["documents"])

MAX_SIZE_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ── AcroForm extraction ────────────────────────────────────────────────────────

def _extract_acroform_fields(pdf_bytes: bytes) -> dict[str, str]:
    """
    Extract every AcroForm widget field from a digital PDF with its current value.
    Returns {clean_field_name: value} — value is "" if the field is blank.
    This is the fastest, most reliable extraction path for digital (non-scanned) forms.
    """
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        raw_fields = reader.get_fields()
        if not raw_fields:
            return {}

        result: dict[str, str] = {}
        for name, field in raw_fields.items():
            clean = name.lstrip("/").strip()

            # /V holds the current value; fall back to /DV (default value)
            val = field.get("/V") or field.get("/DV") or ""
            if hasattr(val, "raw_value"):
                val = val.raw_value
            val = str(val).strip()

            # Normalise PDF checkbox/radio values
            if val in ("/Off", "Off", "/No", "No"):
                val = "no"
            elif val.startswith("/"):
                # /Yes, /Ja, /Male, /1, etc. — strip slash and lowercase
                val = val[1:]
            elif val in ("None", "none", "null", ""):
                val = ""

            result[clean] = val
        return result
    except Exception:
        return {}


def _build_reverse_map(pdf_field_map: dict[str, str]) -> dict[str, str]:
    """
    Reverse the template's pdf_field_map so we can look up a template field_key
    from a PDF widget name.  We index both the exact name and a stripped lowercase
    version so we can match "Vorname", "vorname", "  Vorname  " etc.
    """
    reverse: dict[str, str] = {}
    for field_key, pdf_name in pdf_field_map.items():
        reverse[pdf_name] = field_key
        reverse[pdf_name.lower()] = field_key
        # Also index without special characters for fuzzy matching
        plain = re.sub(r"[^a-z0-9]", "", pdf_name.lower())
        if plain:
            reverse[plain] = field_key
    return reverse


def _match_acroform_to_template(
    acroform: dict[str, str],
    reverse_map: dict[str, str],
) -> dict[str, str]:
    """
    Map AcroForm widget names → template field_keys.
    Returns {field_key: value} for all widgets that have a value.
    Tries three strategies in order: exact match, lowercase match, plain-ascii match.
    """
    matched: dict[str, str] = {}
    for pdf_name, value in acroform.items():
        if not value:
            continue  # skip empty widgets

        # Strategy 1: exact
        fk = reverse_map.get(pdf_name)
        # Strategy 2: lowercase
        if not fk:
            fk = reverse_map.get(pdf_name.lower())
        # Strategy 3: strip non-alphanumeric
        if not fk:
            plain = re.sub(r"[^a-z0-9]", "", pdf_name.lower())
            fk = reverse_map.get(plain) if plain else None
        # Strategy 4: substring — any reverse-map key that is a substring of pdf_name
        if not fk:
            for key, candidate_fk in reverse_map.items():
                if len(key) >= 4 and key in pdf_name.lower():
                    fk = candidate_fk
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

    # ── Step 1: AcroForm extraction (fast, deterministic, works on digital PDFs) ──
    is_pdf = content[:4] == b"%PDF"
    acroform_raw: dict[str, str] = {}
    if is_pdf:
        acroform_raw = _extract_acroform_fields(content)

    # ── Step 2: LLM/OCR extraction (works on scanned PDFs and images) ────────────
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

    # ── Step 3: Auto-select form template ─────────────────────────────────────────
    if not detected_type or ocr_result.confidence < 0.7:
        all_templates = db.query(FormTemplate).all()
        if len(all_templates) == 1:
            detected_type = all_templates[0].id

    if detected_type:
        case.form_template_id = detected_type
        case.status = CaseStatus.FORM_SELECTED.value
    else:
        case.status = CaseStatus.UPLOADED.value
    case.updated_at = datetime.now(timezone.utc)

    # ── Step 4: Merge AcroForm + OCR extracted fields ─────────────────────────────
    # Start with OCR results (LLM extraction)
    extracted: dict[str, str] = dict(ocr_result.metadata.get("extracted_fields", {}))

    # Overlay with AcroForm values (more precise — directly from the PDF)
    if acroform_raw and case.form_template_id:
        template = db.query(FormTemplate).filter_by(id=case.form_template_id).first()
        if template:
            pdf_map = json.loads(template.pdf_field_map)
            reverse_map = _build_reverse_map(pdf_map)
            acroform_matched = _match_acroform_to_template(acroform_raw, reverse_map)
            # AcroForm values override OCR (they come directly from the PDF widget)
            extracted.update(acroform_matched)

    # ── Step 5: Pre-fill Answer rows for all extracted fields ─────────────────────
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
            prefilled_count += 1

    audit_service.log(db, case_id, AuditAction.DOCUMENT_UPLOADED, {
        "document_id": doc.id,
        "detected_form_type": detected_type,
        "confidence": round(ocr_result.confidence, 3),
        "acroform_fields_found": len(acroform_raw),
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
