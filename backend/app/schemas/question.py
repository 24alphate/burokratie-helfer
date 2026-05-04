from typing import Any, Optional
from pydantic import BaseModel


class OptionRead(BaseModel):
    value: str
    label: dict[str, str]


class QuestionRead(BaseModel):
    id: str
    field_key: str
    order_index: int
    input_type: str
    question_text: dict[str, str]
    explanation_text: dict[str, str]
    options: Optional[list[OptionRead]]
    answered_count: int
    total_count: int


class CompletedSignal(BaseModel):
    completed: bool = True
    answered_count: int
    total_count: int


class AnswerSubmit(BaseModel):
    field_key: str
    raw_answer: str


class ValidationErrorItem(BaseModel):
    message: str


class AnswerRead(BaseModel):
    id: str
    field_key: str
    raw_answer: str
    translated_answer: Optional[str]
    is_validated: bool
    validation_errors: list[str]
    is_active: bool

    model_config = {"from_attributes": True}
