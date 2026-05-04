from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CaseCreate(BaseModel):
    form_template_id: Optional[str] = None


class FormTypeSelect(BaseModel):
    form_template_id: str


class CaseRead(BaseModel):
    id: str
    user_id: str
    form_template_id: Optional[str]
    status: str
    current_question_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
