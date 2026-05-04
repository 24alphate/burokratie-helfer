import uuid
from typing import List, Optional
from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    institution: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    supported_languages: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    pdf_field_map: Mapped[str] = mapped_column(Text, nullable=False)  # JSON object: field_key → pdf_field_name
    blank_pdf_filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    fields: Mapped[List["FormField"]] = relationship("FormField", back_populates="template", cascade="all, delete-orphan")
    questions: Mapped[List["Question"]] = relationship("Question", back_populates="template", cascade="all, delete-orphan")


class FormField(Base):
    __tablename__ = "form_fields"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String, ForeignKey("form_templates.id"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    pdf_field_name: Mapped[str] = mapped_column(String, nullable=False)
    data_type: Mapped[str] = mapped_column(String, nullable=False)  # text | date | boolean | select
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    template: Mapped["FormTemplate"] = relationship("FormTemplate", back_populates="fields")
    validation_rules: Mapped[List["ValidationRule"]] = relationship("ValidationRule", back_populates="field", cascade="all, delete-orphan")
