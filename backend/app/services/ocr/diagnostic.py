"""
Stage 4A OCR diagnostic data model + provider ABC.

NAMESPACE NOTE
--------------
This module deliberately uses class names like `OCRDiagnostic`,
`OCRDiagnosticPage` (NOT `OCRResult`) to avoid colliding with the
legacy `app.services.ocr.base.OCRResult` used by `OCRServiceFactory`,
`MockOCRService`, `SmartOCRService`, etc. Those legacy classes are part
of the old DB-based pipeline and remain untouched.

If you're working on Stage 4A, import from THIS module:
    from app.services.ocr.diagnostic import OCRDiagnostic, OCRDiagnosticProvider

If you're working on the legacy OCR pipeline (cases API), import from:
    from app.services.ocr.base import OCRService, OCRResult

Diagnostic-only contract
------------------------
Stage 4A's job is to ANSWER QUESTIONS about a scanned PDF, never to
extract form fields. The output is read by:
  - process_pdf.py  → populates AnalysisReport.ocr_diagnostic
  - Frontend Level-4 screen → renders user-friendly status + next-step copy

Stage 4A MUST NOT:
  - generate FieldDefinitions
  - invent question text
  - call an LLM
  - mutate pdf_token, extracted_field_ids, or any fill-pdf state

Status codes (DiagnosticStatus values, surfaced in the API response and
mapped to frontend copy):

    "readable"          OCR succeeded with average_confidence >= 0.65 and
                        at least one text block was found.
    "low_confidence"    OCR ran but average_confidence < 0.65 — the user
                        should retake or upload a digital PDF.
    "no_text_found"     OCR ran successfully but extracted zero text
                        blocks (likely a blank page or pure-image scan
                        with no recognisable characters).
    "ocr_unavailable"   The Tesseract binary is not installed on the
                        server. NOT a user error — the upload is still
                        accepted, the user is told and asked to upload a
                        digital PDF.
    "failed"            OCR ran but raised an exception (corrupt image,
                        unsupported format, etc.). Generic safe fallback.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# ── Status code constants (string literals so Pydantic + JSON play nice) ─────

STATUS_READABLE         = "readable"
STATUS_LOW_CONFIDENCE   = "low_confidence"
STATUS_NO_TEXT_FOUND    = "no_text_found"
STATUS_OCR_UNAVAILABLE  = "ocr_unavailable"
STATUS_FAILED           = "failed"

# Average-confidence threshold below which we mark the diagnostic as
# "low_confidence" and ask the user to retake. Same value Section 28 of
# Part IV of the plan uses for the post-OCR gate.
LOW_CONFIDENCE_THRESHOLD = 0.65


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class OCRTextBlock:
    """One word/line/region returned by the OCR engine."""
    text: str
    page: int                          # 1-indexed
    bbox: list[float]                  # [x0, y0, x1, y1] in page-image px
    confidence: float                  # 0.0–1.0 (provider-normalized)
    language: Optional[str] = None     # ISO 639-1 if reported per-block


@dataclass
class OCRPageQuality:
    """
    Per-page quality summary. Stage 4A computes the basic ones; Stage 4D
    will add Laplacian-variance blur scoring + brightness + crop checks.
    """
    page: int                          # 1-indexed
    width: int                         # page-image pixels
    height: int                        # page-image pixels
    dpi_estimate: Optional[int]        # best-guess from PDF page size
    text_block_count: int
    average_confidence: float          # 0.0–1.0; mean across this page's blocks
    readable: bool                     # text_block_count > 0 AND avg_conf >= threshold
    issues: list[str] = field(default_factory=list)
    # Stage 4D will add: blur_score, brightness_score, crop_score


@dataclass
class OCRPageResult:
    """All blocks + quality info for a single page."""
    page: int                          # 1-indexed
    blocks: list[OCRTextBlock]
    quality: OCRPageQuality


@dataclass
class OCRDiagnostic:
    """
    The Stage 4A return shape. Fed into AnalysisReport.ocr_diagnostic.

    Frontend reads:
      - diagnostic_status → which copy to show
      - user_message      → headline copy (already translated en + de;
                            fr/ar/tr/sq picked up via UI dict)
      - readable_pages / unreadable_pages → for the "X of Y pages readable"
        line on the Level-4 screen

    Backend logs:
      - technical_message → developer-facing diagnostic, NEVER shown to user
    """
    provider: str                      # "tesseract" | "unavailable"
    page_count: int
    pages: list[OCRPageResult]
    full_text: str                     # joined text across all pages (may be empty)
    average_confidence: float          # mean across all blocks; 0.0 when no blocks
    detected_languages: list[str]      # ISO 639-1; empty when uncertain
    readable_pages: int                # number of pages with quality.readable=True
    unreadable_pages: int              # page_count - readable_pages
    diagnostic_status: str             # one of STATUS_* constants
    user_message: str                  # safe to show users (en); locale dict in frontend
    technical_message: str             # for backend logs only — never sent to UI


# ── Provider ABC ──────────────────────────────────────────────────────────────

class OCRDiagnosticProvider(ABC):
    """
    Stage 4A provider interface. Implementations:
      - TesseractProvider — local, free, GDPR-clean (default)
      - (future Stage 4E) GoogleDocumentAIProvider
    """

    @abstractmethod
    def name(self) -> str:
        """Short identifier surfaced in OCRDiagnostic.provider."""

    @abstractmethod
    def is_available(self) -> bool:
        """
        Cheap pre-flight check. False when the underlying engine isn't
        installed (returns OCRDiagnostic with status='ocr_unavailable'
        without ever loading the document).
        """

    @abstractmethod
    def diagnose(self, pdf_bytes: bytes) -> OCRDiagnostic:
        """
        Run OCR diagnostic on a PDF. Always returns a valid OCRDiagnostic
        — exceptions are caught and surfaced as status='failed'.

        MUST NOT raise. MUST NOT mutate pdf_bytes. MUST NOT call any LLM.
        """


# ── Helpers used by both the provider and the routing code ───────────────────

def make_unavailable(provider_name: str = "unavailable") -> OCRDiagnostic:
    """Pre-built OCRDiagnostic for the 'binary is missing' path."""
    return OCRDiagnostic(
        provider=provider_name,
        page_count=0,
        pages=[],
        full_text="",
        average_confidence=0.0,
        detected_languages=[],
        readable_pages=0,
        unreadable_pages=0,
        diagnostic_status=STATUS_OCR_UNAVAILABLE,
        user_message="OCR is not installed on this server yet.",
        technical_message="pytesseract.TesseractNotFoundError or equivalent",
    )


def make_failed(provider_name: str, technical_message: str) -> OCRDiagnostic:
    """Generic failure fallback. Never leaks the exception text to users."""
    return OCRDiagnostic(
        provider=provider_name,
        page_count=0,
        pages=[],
        full_text="",
        average_confidence=0.0,
        detected_languages=[],
        readable_pages=0,
        unreadable_pages=0,
        diagnostic_status=STATUS_FAILED,
        user_message="We could not read this document. Please try again or upload a digital PDF.",
        technical_message=technical_message,
    )
