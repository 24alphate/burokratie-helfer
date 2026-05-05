import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models.answer import Answer
from app.models.audit_log import AuditAction
from app.models.case import Case, CaseStatus
from app.models.document import UploadedDocument
from app.models.form_template import FormField, FormTemplate
from app.models.generated_pdf import GeneratedPDF
from app.models.question import Question
from app.models.user import User
from app.schemas.pdf import PDFGenerateResponse
from app.services.audit_service import audit_service
from app.services.form_engine import form_engine
from app.services.pdf_generator.base import PDFGenerationRequest

router = APIRouter(prefix="/cases", tags=["pdf"])


@router.post("/{case_id}/generate-pdf", response_model=PDFGenerateResponse)
async def generate_pdf(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user.id)
    if not case.form_template_id:
        raise HTTPException(status_code=400, detail="Form type not selected.")

    template = db.query(FormTemplate).filter(FormTemplate.id == case.form_template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Form template not found.")

    questions = db.query(Question).filter(Question.template_id == case.form_template_id).all()
    active_answers = db.query(Answer).filter(Answer.case_id == case_id, Answer.is_active == True).all()
    answers_dict = {a.field_key: a.raw_answer for a in active_answers}

    # Ensure all required questions are answered
    next_q = form_engine.get_next_question(questions, answers_dict)
    if next_q is not None:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot generate PDF: question '{next_q.field_key}' is not yet answered.",
        )

    # Build pdf_field_values: pdf_field_name → translated German answer
    pdf_field_map = json.loads(template.pdf_field_map)
    fields = db.query(FormField).filter(FormField.template_id == case.form_template_id).all()
    field_map = {f.field_key: f for f in fields}

    translated_values: dict[str, str] = {}
    for answer in active_answers:
        field_obj = field_map.get(answer.field_key)
        if not field_obj:
            continue
        pdf_name = pdf_field_map.get(answer.field_key)
        if not pdf_name:
            continue
        translated_values[pdf_name] = answer.translated_answer or answer.raw_answer

    # Dynamic templates use the original uploaded PDF as the base;
    # fixed templates use the pre-built blank form.
    is_dynamic = case.form_template_id.startswith("dyn_")
    if is_dynamic:
        uploaded_doc = db.query(UploadedDocument).filter_by(case_id=case_id).order_by(
            UploadedDocument.uploaded_at.desc()
        ).first()
        if not uploaded_doc or not Path(uploaded_doc.storage_path).exists():
            raise HTTPException(status_code=404, detail="Original uploaded PDF not found.")
        blank_pdf_path = Path(uploaded_doc.storage_path)
    else:
        blank_pdf_path = Path(settings.static_pdfs_dir) / (template.blank_pdf_filename or "alg2_blank.pdf")

    pdf_request = PDFGenerationRequest(
        template_id=case.form_template_id,
        field_values=translated_values,
        blank_pdf_path=str(blank_pdf_path),
    )

    generator = request.app.state.pdf_generator
    result = await generator.generate(pdf_request)

    generated_dir = Path(settings.generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)
    pdf_id = str(uuid.uuid4())
    output_path = generated_dir / f"{pdf_id}.pdf"
    output_path.write_bytes(result.pdf_bytes)

    gen_pdf = GeneratedPDF(
        case_id=case_id,
        storage_path=str(output_path),
        generated_at=datetime.now(timezone.utc),
        is_valid=True,
    )
    db.add(gen_pdf)
    db.flush()

    case.status = CaseStatus.COMPLETED.value
    case.updated_at = datetime.now(timezone.utc)

    audit_service.log(db, case_id, AuditAction.PDF_GENERATED, {
        "pdf_id": gen_pdf.id,
        "field_count": result.field_count_filled,
        "warnings": result.warnings,
    })
    db.commit()

    return PDFGenerateResponse(pdf_id=gen_pdf.id, status="ready")


@router.get("/{case_id}/pdf/{pdf_id}/download")
def download_pdf(
    case_id: str,
    pdf_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user.id)

    gen_pdf = db.query(GeneratedPDF).filter(
        GeneratedPDF.id == pdf_id,
        GeneratedPDF.case_id == case_id,
    ).first()
    if not gen_pdf:
        raise HTTPException(status_code=404, detail="PDF not found.")

    pdf_path = Path(gen_pdf.storage_path)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    audit_service.log(db, case_id, AuditAction.PDF_DOWNLOADED, {"pdf_id": pdf_id})
    db.commit()

    pdf_bytes = pdf_path.read_bytes()

    def iter_bytes():
        yield pdf_bytes

    return StreamingResponse(
        iter_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="antrag_{case_id[:8]}.pdf"'},
    )


def _get_case_or_404(db: Session, case_id: str, user_id: str) -> Case:
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case
