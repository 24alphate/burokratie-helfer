from typing import Optional
from pydantic import BaseModel


class FieldOption(BaseModel):
    value: str    # value written to PDF (document language, e.g. "verheiratet")
    label: str    # shown to user (user language, e.g. "Marié(e)")


class FieldDefinition(BaseModel):
    key: str                        # exact PDF widget name — the ground truth anchor
    question: dict[str, str]        # {locale: question text in user language}
    explanation: dict[str, str]
    input_type: str                 # text | date | number | checkbox | radio | select | signature
    options: list[FieldOption] = [] # for radio/select/checkbox — empty for text fields
    original_label: str = ""        # field label as it appears in the document
    document_language: str = "de"   # language of the PDF
    source_page: int = 1
    order: int
    is_prefilled: bool
    confidence: float = 1.0         # 1.0 = from AcroForm widget (ground truth); <1.0 = vision guess
    needs_review: bool = False      # flag low-confidence fields for user confirmation


class UploadResponse(BaseModel):
    document_id: str
    detected_form_type: Optional[str]
    confidence: float
    requires_manual_selection: bool
    prefilled_fields: int = 0
    fields: list[FieldDefinition] = []
    document_language: str = "de"
    user_language: str = "en"
