from datetime import datetime
from pydantic import BaseModel


class PDFGenerateResponse(BaseModel):
    pdf_id: str
    status: str  # "ready" | "failed"


class PDFRead(BaseModel):
    id: str
    case_id: str
    generated_at: datetime
    is_valid: bool

    model_config = {"from_attributes": True}
