import json
from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.answer import Answer
from app.models.audit_log import AuditAction
from app.models.case import Case, CaseStatus
from app.models.form_template import FormField
from app.models.question import Question
from app.models.user import User
from app.schemas.question import (
    AnswerRead, AnswerSubmit, CompletedSignal, OptionRead, QuestionRead,
)
from app.services.audit_service import audit_service
from app.services.form_engine import form_engine
from app.services.validation_service import validation_service

router = APIRouter(prefix="/cases", tags=["questions"])


def _active_answers_dict(db: Session, case_id: str) -> dict[str, str]:
    rows = db.query(Answer).filter(Answer.case_id == case_id, Answer.is_active == True).all()
    return {r.field_key: r.raw_answer for r in rows}


def _build_question_read(question: Question, answered: int, total: int) -> QuestionRead:
    options = None
    if question.options:
        raw_opts = json.loads(question.options)
        options = [OptionRead(value=o["value"], label=o["label"]) for o in raw_opts]
    return QuestionRead(
        id=question.id,
        field_key=question.field_key,
        order_index=question.order_index,
        input_type=question.input_type,
        question_text=json.loads(question.question_text),
        explanation_text=json.loads(question.explanation_text),
        options=options,
        answered_count=answered,
        total_count=total,
    )


@router.get("/{case_id}/next-question", response_model=Union[QuestionRead, CompletedSignal])
def get_next_question(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user.id)
    if not case.form_template_id:
        raise HTTPException(status_code=400, detail="Form type not yet selected for this case.")

    questions = db.query(Question).filter(Question.template_id == case.form_template_id).all()
    answers = _active_answers_dict(db, case_id)

    next_q = form_engine.get_next_question(questions, answers)
    answered_count, total_count = form_engine.completion_fraction(questions, answers)

    if next_q is None:
        case.status = CaseStatus.REVIEW.value
        case.updated_at = datetime.now(timezone.utc)
        db.commit()
        return CompletedSignal(completed=True, answered_count=answered_count, total_count=total_count)

    if case.status == CaseStatus.FORM_SELECTED.value:
        case.status = CaseStatus.IN_PROGRESS.value
        case.updated_at = datetime.now(timezone.utc)
        db.commit()

    return _build_question_read(next_q, answered_count, total_count)


@router.post("/{case_id}/answers", response_model=AnswerRead, status_code=201)
async def submit_answer(
    case_id: str,
    payload: AnswerSubmit,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = _get_case_or_404(db, case_id, user.id)
    if not case.form_template_id:
        raise HTTPException(status_code=400, detail="Form type not yet selected.")

    # Validate: field_key must belong to this template
    field = db.query(FormField).filter(
        FormField.template_id == case.form_template_id,
        FormField.field_key == payload.field_key,
    ).first()
    if not field:
        raise HTTPException(status_code=400, detail=f"Unknown field_key: {payload.field_key}")

    # Run validation rules
    vresult = validation_service.validate_answer(
        payload.raw_answer,
        field.validation_rules,
        language=user.preferred_language,
    )

    # Translate answer to German (via service layer — never raw AI output to PDF)
    translation_service = request.app.state.translation_service
    translation = await translation_service.translate(
        payload.raw_answer,
        source_language=user.preferred_language,
        target_language="de",
        field_context=payload.field_key,
    )

    # Soft-delete any existing active answer for this field (user is re-answering)
    existing = db.query(Answer).filter(
        Answer.case_id == case_id,
        Answer.field_key == payload.field_key,
        Answer.is_active == True,
    ).first()

    if existing:
        # Check if changing this answer invalidates downstream conditional answers
        old_answers = _active_answers_dict(db, case_id)
        new_answers = {**old_answers, payload.field_key: payload.raw_answer}
        questions = db.query(Question).filter(Question.template_id == case.form_template_id).all()
        invalidated_keys = form_engine.get_invalidated_field_keys(questions, old_answers, new_answers)

        for key in invalidated_keys:
            stale = db.query(Answer).filter(
                Answer.case_id == case_id,
                Answer.field_key == key,
                Answer.is_active == True,
            ).first()
            if stale:
                stale.is_active = False
                audit_service.log(db, case_id, AuditAction.ANSWER_INVALIDATED, {"field_key": key})

        existing.is_active = False

    answer = Answer(
        case_id=case_id,
        field_key=payload.field_key,
        raw_answer=payload.raw_answer,
        translated_answer=translation.translated_text,
        is_validated=vresult.is_valid,
        validation_errors=json.dumps(vresult.errors),
        is_active=True,
        answered_at=datetime.now(timezone.utc),
    )
    db.add(answer)
    db.flush()

    audit_service.log(db, case_id, AuditAction.ANSWER_SUBMITTED, {
        "field_key": payload.field_key,
        "is_validated": vresult.is_valid,
    })
    case.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(answer)

    return AnswerRead(
        id=answer.id,
        field_key=answer.field_key,
        raw_answer=answer.raw_answer,
        translated_answer=answer.translated_answer,
        is_validated=answer.is_validated,
        validation_errors=json.loads(answer.validation_errors) if answer.validation_errors else [],
        is_active=answer.is_active,
    )


@router.get("/{case_id}/answers", response_model=list[AnswerRead])
def get_answers(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_case_or_404(db, case_id, user.id)
    answers = db.query(Answer).filter(
        Answer.case_id == case_id,
        Answer.is_active == True,
    ).all()
    return [
        AnswerRead(
            id=a.id,
            field_key=a.field_key,
            raw_answer=a.raw_answer,
            translated_answer=a.translated_answer,
            is_validated=a.is_validated,
            validation_errors=json.loads(a.validation_errors) if a.validation_errors else [],
            is_active=a.is_active,
        )
        for a in answers
    ]


def _get_case_or_404(db: Session, case_id: str, user_id: str) -> Case:
    case = db.query(Case).filter(Case.id == case_id, Case.user_id == user_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case
