import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    raw_answer: Mapped[str] = mapped_column(Text, nullable=False)
    translated_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    case: Mapped["Case"] = relationship("Case", back_populates="answers")

