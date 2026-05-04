from typing import Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    detected_form_type: Optional[str]
    confidence: float
    requires_manual_selection: bool
    prefilled_fields: int = 0
