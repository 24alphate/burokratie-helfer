from typing import Optional
from pydantic import BaseModel


class FieldDefinition(BaseModel):
    key: str
    question: dict[str, str]    # {locale: question text}
    explanation: dict[str, str]  # {locale: explanation}
    input_type: str              # text | date | yes_no | select
    order: int
    is_prefilled: bool


class UploadResponse(BaseModel):
    document_id: str
    detected_form_type: Optional[str]
    confidence: float
    requires_manual_selection: bool
    prefilled_fields: int = 0
    fields: list[FieldDefinition] = []  # complete field list for client-side question flow
