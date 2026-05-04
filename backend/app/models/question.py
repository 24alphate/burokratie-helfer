import uuid
from typing import Optional
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id: Mapped[str] = mapped_column(String, ForeignKey("form_templates.id"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input_type: Mapped[str] = mapped_column(String, nullable=False)  # text | date | yes_no | select
    # JSON: {"en": "...", "ar": "...", "tr": "...", "de": "..."}
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array for select type
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON condition DSL or null

    template: Mapped["FormTemplate"] = relationship("FormTemplate", back_populates="questions")
