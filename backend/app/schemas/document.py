from typing import Literal, Optional
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
    original_label: str = ""        # field label as it appears in the document (PDF language)
    document_language: str = "de"   # language of the PDF
    source_page: int = 1
    order: int
    is_prefilled: bool
    confidence: float = 1.0         # 1.0 = AcroForm ground truth; 0.75 = pdfplumber; 0.5 = ocr
    needs_review: bool = False      # True if confidence in [0.70, 0.90) — show with review warning
    # Grounding metadata — required for every question shown to the user
    show_question: bool = True      # False when confidence < 0.70 (blocked, not shown)
    source_text: str = ""           # exact text from the PDF that grounds this question
    reason: str = "pdf_field"       # "pdf_field" | "derived_helper"
    question_type: str = "pdf_field"


class AnalysisReport(BaseModel):
    """
    Accuracy report returned with every field extraction.
    grounding_rate is always 100% by design.
    """
    pdf_type: str
    total_pages: int
    field_count: int                # fields extracted from PDF
    questions_shown: int            # fields with show_question=True
    questions_blocked: int          # fields blocked (confidence < 0.70)
    low_confidence_fields: int      # confidence in [0.70, 0.90) — shown but needs_review
    invented_questions_removed: int # AI-invented keys discarded
    coverage_rate: str              # questions_shown / field_count
    grounding_rate: str             # always "100%"
    grounding_ok: bool              # always True when grounding_rate == "100%"
    # Template metadata — set when a verified template was used
    template_id: Optional[str] = None
    extraction_source: str = "auto"  # "verified_template" | "acroform" | "pdfplumber" | "auto"


class UploadResponse(BaseModel):
    document_id: str
    detected_form_type: Optional[str]
    confidence: float
    requires_manual_selection: bool
    prefilled_fields: int = 0
    fields: list[FieldDefinition] = []
    document_language: str = "de"
    user_language: str = "en"
    analysis_report: Optional[AnalysisReport] = None
    # Authoritative list of field_ids extracted directly from the PDF.
    # This is the ground truth. Every key in `fields` must appear here.
    # The frontend stores this separately and uses it as the hard grounding gate.
    extracted_field_ids: list[str] = []
