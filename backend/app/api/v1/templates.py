import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.form_template import FormTemplate
from app.schemas.form_template import FormTemplateSummary, FormTemplateRead

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[FormTemplateSummary])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(FormTemplate).all()
    result = []
    for t in templates:
        result.append(FormTemplateSummary(
            id=t.id,
            name=t.name,
            institution=t.institution,
            version=t.version,
            supported_languages=json.loads(t.supported_languages),
        ))
    return result


@router.get("/{template_id}", response_model=FormTemplateRead)
def get_template(template_id: str, db: Session = Depends(get_db)):
    t = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found.")
    return FormTemplateRead(
        id=t.id,
        name=t.name,
        institution=t.institution,
        version=t.version,
        supported_languages=json.loads(t.supported_languages),
    )
