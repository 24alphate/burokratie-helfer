import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class GeneratedPDF(Base):
    __tablename__ = "generated_pdfs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    case: Mapped["Case"] = relationship("Case", back_populates="generated_pdfs")

