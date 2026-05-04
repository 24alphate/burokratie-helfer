"""
Seed script: reads all JSON form templates from this directory and upserts them into the DB.
Run: python -m app.form_templates.seed
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.database import SessionLocal, engine
from app.database import Base
import app.models  # noqa: F401 — registers all models

from app.models.form_template import FormTemplate, FormField
from app.models.question import Question
from app.models.validation_rule import ValidationRule


def seed_template(db, data: dict) -> None:
    template_id = data["id"]

    existing = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    template = FormTemplate(
        id=template_id,
        name=data["name"],
        institution=data["institution"],
        version=data["version"],
        supported_languages=json.dumps(data["supported_languages"]),
        pdf_field_map=json.dumps(data["pdf_field_map"]),
        blank_pdf_filename=data.get("blank_pdf_filename"),
    )
    db.add(template)
    db.flush()

    field_id_map: dict[str, str] = {}
    for f in data.get("fields", []):
        field = FormField(
            template_id=template_id,
            field_key=f["field_key"],
            pdf_field_name=f["pdf_field_name"],
            data_type=f["data_type"],
            required=f.get("required", True),
        )
        db.add(field)
        db.flush()
        field_id_map[f["field_key"]] = field.id

    for q in data.get("questions", []):
        question = Question(
            id=q["id"],
            template_id=template_id,
            field_key=q["field_key"],
            order_index=q["order_index"],
            input_type=q["input_type"],
            question_text=json.dumps(q["question_text"]),
            explanation_text=json.dumps(q["explanation_text"]),
            options=json.dumps(q["options"]) if q.get("options") else None,
            condition=json.dumps(q["condition"]) if q.get("condition") else None,
        )
        db.add(question)
        db.flush()

        field_id = field_id_map.get(q["field_key"])
        if field_id:
            for rule in q.get("validation_rules", []):
                vr = ValidationRule(
                    field_id=field_id,
                    rule_type=rule["rule_type"],
                    rule_value=rule.get("rule_value"),
                    error_message=json.dumps(rule["error_message"]),
                )
                db.add(vr)

    db.commit()
    print(f"Seeded template: {template_id}")


def main():
    Base.metadata.create_all(bind=engine)
    templates_dir = Path(__file__).parent
    db = SessionLocal()
    try:
        for json_file in templates_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            seed_template(db, data)
    finally:
        db.close()
    print("Seeding complete.")


if __name__ == "__main__":
    main()
