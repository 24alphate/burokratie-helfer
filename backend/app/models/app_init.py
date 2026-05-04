"""
Import all models here so SQLAlchemy registers them before Alembic autogenerate runs.
"""
from app.models import (  # noqa: F401
    User, Case, UploadedDocument, FormTemplate, FormField,
    Question, Answer, ValidationRule, GeneratedPDF, AuditLog,
)
