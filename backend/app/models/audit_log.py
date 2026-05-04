import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AuditAction(str, Enum):
    CASE_CREATED = "case_created"
    DOCUMENT_UPLOADED = "document_uploaded"
    FORM_TYPE_SELECTED = "form_type_selected"
    ANSWER_SUBMITTED = "answer_submitted"
    ANSWER_INVALIDATED = "answer_invalidated"
    PDF_GENERATED = "pdf_generated"
    PDF_DOWNLOADED = "pdf_downloaded"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    # JSON â€” no PII: only field_key, template_id, etc.
    action_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

