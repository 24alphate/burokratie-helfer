from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.models.form_template import FormTemplate
from app.models.audit_log import AuditAction
from app.schemas.case import CaseCreate, CaseRead, FormTypeSelect
from app.services.audit_service import audit_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseRead, status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.form_template_id:
        tpl = db.query(FormTemplate).filter(FormTemplate.id == payload.form_template_id).first()
        if not tpl:
            raise HTTPException(status_code=404, detail="Form template not found.")

    now = datetime.now(timezone.utc)
    case = Case(
        user_id=user.id,
        form_template_id=payload.form_template_id,
        status=CaseStatus.CREATED.value,
        current_question_index=0,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.flush()
    audit_service.log(db, case.id, AuditAction.CASE_CREATED, {"template_id": payload.form_template_id})
    db.commit()
    db.refresh(case)
    return case


@router.get("/{case_id}", response_model=CaseRead)
def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _get_case_or_404(db, case_id, user.id)
    return case


@router.patch("/{case_id}/form-type", response_model=CaseRead)
def set_form_type(
    case_id: str,
    payload: FormTypeSelect,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user.id)
    tpl = db.query(FormTemplate).filter(FormTemplate.id == payload.form_template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Form template not found.")

    case.form_template_id = payload.form_template_id
    case.status = CaseStatus.FORM_SELECTED.value
    case.updated_at = datetime.now(timezone.utc)
    audit_service.log(db, case.id, AuditAction.FORM_TYPE_SELECTED, {"template_id": payload.form_template_id})
    db.commit()
    db.refresh(case)
    return case


def _get_case_or_404(db: Session, case_id: str, user_id: str) -> Case:
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case
