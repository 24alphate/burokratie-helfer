import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CaseStatus(str, Enum):
    CREATED = "created"
    UPLOADED = "uploaded"
    FORM_SELECTED = "form_selected"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    form_template_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("form_templates.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=CaseStatus.CREATED)
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="cases")
    form_template: Mapped[Optional["FormTemplate"]] = relationship("FormTemplate")
    uploaded_documents: Mapped[List["UploadedDocument"]] = relationship("UploadedDocument", back_populates="case")
    answers: Mapped[List["Answer"]] = relationship("Answer", back_populates="case")
    generated_pdfs: Mapped[List["GeneratedPDF"]] = relationship("GeneratedPDF", back_populates="case")

