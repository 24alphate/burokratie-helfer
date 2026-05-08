from typing import Optional
from pydantic import BaseModel


class FieldOption(BaseModel):
    value: str    # value written to PDF (document language, e.g. "verheiratet")
    label: str    # shown to user (user language, e.g. "Marié(e)")


class GuidanceText(BaseModel):
    """
    Optional human-language guidance for a single field.
    All values are dicts keyed by locale (e.g. {"en": "...", "de": "..."}).
    Fallback order: user locale → "en" → "de".
    """
    plain_language: dict = {}        # {locale: simple explanation}
    why_needed: dict = {}            # {locale: why the form asks this}
    where_to_find: dict = {}         # {locale: where the user finds the information}
    format_hint: dict = {}           # {locale: how to format the answer}
    example: dict = {}               # {locale: example answer string}
    required_documents: dict = {}    # {locale: [doc1, doc2, ...]}
    common_mistakes: dict = {}       # {locale: [mistake1, ...]}
    warning: dict = {}               # {locale: warning string}


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
    # ── Guidance layer — optional, never affects PDF filling ──────────────────
    guidance: Optional[GuidanceText] = None
    semantic_key: Optional[str] = None    # e.g. "applicant.full_name" — for future answer reuse
    # ── Question quality metadata ──────────────────────────────────────────────
    question_source: str = ""  # "verified" | "semantic" | "ai" | "deterministic" | "label" | "key"
    question_weak_reasons: list[str] = []  # quality checker flags


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
    support_level: int = 4           # 1=verified | 2=acroform | 3=flat | 4=scanned/unknown
    # Translation coverage — how many fields got a proper translation vs fallback
    translation_locale: Optional[str] = None
    translation_total: int = 0
    translation_translated: int = 0   # AI or deterministic translation
    translation_fallback: int = 0     # fell back to original_label
    translation_fallback_ids: list[str] = []
    # Question quality report
    question_quality: Optional[dict] = None  # {strong, weak, weak_field_ids, source_counts, ...}
    # ── Level 2 (AcroForm) field-type breakdown — Phase D/D2 ─────────────────
    # Populated for every extraction (zeroed for Level 1 verified, since the
    # template path skips per-type counting). Used by the QA dashboard and
    # the upload-page diagnostic table to make AcroForm quality visible.
    acroform_metrics: Optional[dict] = None
    # ── Level 2 fill strategy advertisement ──────────────────────────────────
    # "fitz_overlay"  — Level 1 verified template path
    # "acroform"      — Level 2 PyPDFGenerator AcroForm fill
    # "summary"       — Level 3/4 reportlab summary fallback
    # None            — extraction-only call (no fill yet)
    fill_strategy: Optional[str] = None


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
