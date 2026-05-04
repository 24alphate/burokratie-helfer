"""
Perfect form extraction pipeline using:
- pdfplumber  : accurate text + table extraction from native PDFs
- pypdf       : PDF metadata and page analysis
- PyMuPDF     : render scanned PDFs to high-resolution images
- LangChain   : orchestration, prompt templates, structured output
- instructor  : guaranteed Pydantic-validated JSON with auto-retry
- openai SDK  : OpenAI-compatible client pointed at Groq

Strategy:
  1. Try pdfplumber text extraction (fast, perfect for digital PDFs)
  2. If text is sparse/absent → render to image via PyMuPDF (scanned forms)
  3. Feed to LangChain chain → Groq LLM → instructor structured output
  4. instructor auto-retries (up to 3×) if output doesn't match schema
  5. Normalize: dates, IBAN, yes/no values
"""
from __future__ import annotations

import base64
import io
import os
import re
from typing import Optional

import pdfplumber
import pymupdf  # fitz — renders PDF pages to images
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator
import instructor

from app.services.ocr.base import OCRService, OCRResult

# ── Pydantic schema — defines the exact output shape ──────────────────────────

class ExtractedFormFields(BaseModel):
    first_name: Optional[str] = Field(None, description="Vorname as written")
    last_name: Optional[str] = Field(None, description="Familienname as written")
    date_of_birth: Optional[str] = Field(None, description="Geburtsdatum in DD.MM.YYYY")
    nationality: Optional[str] = Field(None, description="Staatsangehörigkeit")
    street_address: Optional[str] = Field(None, description="Straße und Hausnummer")
    postal_code: Optional[str] = Field(None, description="Postleitzahl, 5 digits")
    city: Optional[str] = Field(None, description="Ort / Stadt")
    employment_status: Optional[str] = Field(
        None,
        description="One of: unemployed, part_time, self_employed, not_working"
    )
    monthly_income: Optional[str] = Field(None, description="Monthly income as numeric string")
    has_partner: Optional[str] = Field(None, description="yes or no")
    partner_first_name: Optional[str] = Field(None, description="Partner Vorname")
    partner_last_name: Optional[str] = Field(None, description="Partner Familienname")
    children_count: Optional[str] = Field(None, description="Number of children as string")
    iban: Optional[str] = Field(None, description="German IBAN without spaces, starts DE")
    signature_date: Optional[str] = Field(None, description="Signing date in DD.MM.YYYY")

    @field_validator("date_of_birth", "signature_date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if not v:
            return None
        # Accept various date formats and normalize to DD.MM.YYYY
        v = str(v).strip()
        for pat in (r"(\d{2})\.(\d{2})\.(\d{4})", r"(\d{4})-(\d{2})-(\d{2})"):
            m = re.match(pat, v)
            if m:
                if "-" in v:
                    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
                return v
        return v

    @field_validator("iban", mode="before")
    @classmethod
    def normalize_iban(cls, v):
        if not v:
            return None
        return re.sub(r"\s+", "", str(v)).upper()

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal(cls, v):
        if not v:
            return None
        digits = re.sub(r"\D", "", str(v))
        return digits if len(digits) == 5 else None

    @field_validator("has_partner", mode="before")
    @classmethod
    def normalize_boolean(cls, v):
        if not v:
            return None
        v = str(v).lower().strip()
        if v in ("yes", "ja", "true", "1", "✓", "x"):
            return "yes"
        if v in ("no", "nein", "false", "0"):
            return "no"
        return None

    @field_validator("employment_status", mode="before")
    @classmethod
    def normalize_employment(cls, v):
        if not v:
            return None
        v = str(v).lower().strip()
        if any(w in v for w in ("arbeitslos", "unemployed", "job")):
            return "unemployed"
        if any(w in v for w in ("teilzeit", "part", "mini")):
            return "part_time"
        if any(w in v for w in ("selbst", "self", "freelance", "freiberuf")):
            return "self_employed"
        if any(w in v for w in ("nicht", "not_working", "not working", "sonstig")):
            return "not_working"
        if v in ("unemployed", "part_time", "self_employed", "not_working"):
            return v
        return None

    @field_validator("monthly_income", "children_count", mode="before")
    @classmethod
    def normalize_numeric(cls, v):
        if not v:
            return None
        digits = re.sub(r"[^\d.,]", "", str(v)).replace(",", ".")
        return digits if digits else None


class FormExtractionResult(BaseModel):
    form_type: str = Field(default="alg2_antrag_v1")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extracted_fields: ExtractedFormFields = Field(default_factory=ExtractedFormFields)


# ── Prompts ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert at extracting structured data from German government forms. "
    "Extract ALL visible field values from the provided Jobcenter ALG II form. "
    "Only include values that are clearly filled in. Return null for empty fields. "
    "For checkboxes, determine the value from which box is checked or marked."
)

TEXT_PROMPT = (
    "Extract all filled-in values from this German Jobcenter ALG II form text.\n\n"
    "FORM TEXT:\n{text}\n\n"
    "Return confidence 0.0–1.0 indicating how certain you are this is an ALG II form."
)

IMAGE_PROMPT = (
    "Extract all filled-in values from this German Jobcenter ALG II form image. "
    "Look carefully at every field, checkbox, and handwritten entry. "
    "Return confidence 0.0–1.0 indicating how certain you are this is an ALG II form."
)


# ── Helper functions ───────────────────────────────────────────────────────────

def _detect_mime(file_bytes: bytes) -> str:
    if file_bytes[:4] == b"%PDF":
        return "application/pdf"
    if file_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if file_bytes[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    return "application/pdf"


def _extract_text_with_pdfplumber(pdf_bytes: bytes) -> str:
    """
    Use pdfplumber for best-quality text extraction from native PDFs.
    Handles text positioning, tables, and form fields.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts = []
            for page in pdf.pages[:4]:  # max 4 pages
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    parts.append(text)
                # Also extract tables (form fields often appear as tables)
                for table in (page.extract_tables() or []):
                    for row in table:
                        row_text = " | ".join(cell or "" for cell in row if cell)
                        if row_text.strip():
                            parts.append(row_text)
            return "\n".join(parts)
    except Exception:
        return ""


def _pdf_to_image_bytes(pdf_bytes: bytes, scale: float = 2.5) -> bytes:
    """
    Render first PDF page to high-resolution PNG using PyMuPDF.
    scale=2.5 gives ~180 DPI which is good for OCR.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(0)
    mat = pymupdf.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def _to_base64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("utf-8")


def _is_text_rich(text: str, min_chars: int = 80) -> bool:
    """Returns True if extracted text has enough content to be useful."""
    return len(text.strip()) >= min_chars


# ── Main SmartOCRService ───────────────────────────────────────────────────────

class SmartOCRService(OCRService):
    """
    Multi-strategy extraction pipeline:
    1. pdfplumber text extraction (native PDFs) → LangChain text chain
    2. PyMuPDF image rendering (scanned PDFs/images) → LangChain vision chain
    3. instructor ensures guaranteed Pydantic output with auto-retry
    """

    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        self._langchain_llm: Optional[ChatGroq] = None
        self._instructor_client: Optional[object] = None

    def _get_langchain_llm(self) -> ChatGroq:
        if not self._langchain_llm:
            self._langchain_llm = ChatGroq(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                api_key=self.groq_api_key,
                temperature=0,
                max_tokens=2000,
            )
        return self._langchain_llm

    def _get_instructor_client(self):
        """instructor wraps the OpenAI-compatible Groq client for structured output with retry."""
        if not self._instructor_client:
            raw_client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_api_key,
            )
            self._instructor_client = instructor.from_openai(
                raw_client,
                mode=instructor.Mode.JSON,
            )
        return self._instructor_client

    def _extract_from_text(self, text: str) -> FormExtractionResult:
        """
        LangChain text chain: prompt template → Groq LLM → structured output.
        Used for native PDFs where pdfplumber extracted good text.
        """
        llm = self._get_langchain_llm()
        structured_llm = llm.with_structured_output(FormExtractionResult)

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=SYSTEM_PROMPT),
            ("human", TEXT_PROMPT),
        ])
        chain = prompt | structured_llm
        return chain.invoke({"text": text})

    def _extract_from_image(self, img_bytes: bytes, mime: str = "image/png") -> FormExtractionResult:
        """
        Vision chain via instructor: image → Groq Llama 4 Scout → Pydantic model.
        instructor retries automatically if output doesn't match schema (max 3 attempts).
        """
        client = self._get_instructor_client()
        b64 = _to_base64(img_bytes)
        data_url = f"data:{mime};base64,{b64}"

        return client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            response_model=FormExtractionResult,
            max_retries=3,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": f"{SYSTEM_PROMPT}\n\n{IMAGE_PROMPT}"},
                ],
            }],
        )

    async def extract_text(self, file_bytes: bytes) -> OCRResult:
        if not self.groq_api_key or self.groq_api_key.startswith("REPLACE"):
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": "GROQ_API_KEY not configured"},
            )

        mime = _detect_mime(file_bytes)
        result: Optional[FormExtractionResult] = None
        strategy_used = ""

        try:
            if mime == "application/pdf":
                # Strategy 1: pdfplumber text extraction (best for native PDFs)
                pdf_text = _extract_text_with_pdfplumber(file_bytes)

                if _is_text_rich(pdf_text):
                    strategy_used = "pdfplumber+langchain-text"
                    result = self._extract_from_text(pdf_text)
                else:
                    # Strategy 2: render to image (scanned PDF)
                    strategy_used = "pymupdf+langchain-vision"
                    img_bytes = _pdf_to_image_bytes(file_bytes, scale=2.5)
                    result = self._extract_from_image(img_bytes, "image/png")
            else:
                # Strategy 3: direct image input
                strategy_used = "langchain-vision"
                result = self._extract_from_image(file_bytes, mime)

        except Exception as exc:
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": str(exc), "strategy": strategy_used},
            )

        if result is None:
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": "No result returned"},
            )

        # Build clean extracted fields dict (remove nulls)
        fields_dict = result.extracted_fields.model_dump()
        clean_fields = {k: v for k, v in fields_dict.items() if v is not None}

        form_type = result.form_type if result.confidence >= 0.7 else None

        return OCRResult(
            raw_text="",  # not stored — PII
            confidence=result.confidence,
            detected_form_type=form_type,
            page_count=1,
            metadata={
                "extracted_fields": clean_fields,
                "strategy": strategy_used,
                "fields_found": len(clean_fields),
            },
        )

    async def detect_form_type(self, ocr_result: OCRResult) -> Optional[str]:
        return ocr_result.detected_form_type
