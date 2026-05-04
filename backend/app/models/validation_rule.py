import uuid
from typing import Optional
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ValidationRule(Base):
    __tablename__ = "validation_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    field_id: Mapped[str] = mapped_column(String, ForeignKey("form_fields.id"), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String, nullable=False)  # required | regex | max_length | date_range | iban
    rule_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: {"en": "...", "ar": "...", ...}

    field: Mapped["FormField"] = relationship("FormField", back_populates="validation_rules")
