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


# ── Verified-template diagnostic endpoint (Level 1) ──────────────────────────
# Read-only; safe to expose. Used for QA dashboards and ops visibility.

@router.get("/verified")
def list_verified_templates() -> dict:
    """
    Return the registered Level 1 verified-template catalog.

    Each entry: template_id, name, field_count, non_signature_count,
    write_spec_count, locale_coverage (per-locale answered/total).
    """
    from app.services.form_templates import _all_templates
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID

    LOCALES = ["en", "de", "fr", "ar", "tr", "sq", "es", "ru", "uk"]
    templates = _all_templates()
    out = []
    for t in templates:
        field_map = t.get_field_map()
        non_sig = [f for f in field_map if f.confidence > 0.5]
        write_specs = t.get_write_specs()
        coverage = {}
        for loc in LOCALES:
            covered = sum(
                1 for f in non_sig
                if VERIFIED_BY_FIELD_ID.get(f.field_id, {}).get(loc, {}).get("question")
            )
            coverage[loc] = {"covered": covered, "total": len(non_sig)}
        out.append({
            "template_id": t.template_id,
            "name": t.name,
            "field_count": len(field_map),
            "non_signature_count": len(non_sig),
            "write_spec_count": len(write_specs),
            "locale_coverage": coverage,
        })
    return {"count": len(out), "templates": out}


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
