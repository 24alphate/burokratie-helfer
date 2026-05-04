"""
Real OCR using Claude Vision API.
Handles both native PDFs and scanned images (JPEG, PNG, TIFF).
Extracts all visible form field values and returns structured data.
"""
import base64
import json
import re
from typing import Optional

import anthropic

from app.services.ocr.base import OCRService, OCRResult

# Maps Claude's output field names → our internal field_keys
FIELD_KEY_MAP = {
    "first_name": "first_name",
    "last_name": "last_name",
    "date_of_birth": "date_of_birth",
    "nationality": "nationality",
    "street_address": "street_address",
    "postal_code": "postal_code",
    "city": "city",
    "employment_status": "employment_status",
    "monthly_income": "monthly_income",
    "has_partner": "has_partner",
    "partner_first_name": "partner_first_name",
    "partner_last_name": "partner_last_name",
    "children_count": "children_count",
    "iban": "iban",
    "signature_date": "signature_date",
}

EXTRACTION_PROMPT = """You are analyzing a German Jobcenter form. Extract ALL visible text and filled-in values.

Return ONLY a valid JSON object with this exact structure (no extra text before or after):
{
  "form_type": "alg2_antrag_v1",
  "confidence": 0.95,
  "extracted_fields": {
    "first_name": "value if visible and filled in, otherwise null",
    "last_name": "value if visible and filled in, otherwise null",
    "date_of_birth": "DD.MM.YYYY format if filled, otherwise null",
    "nationality": "value if filled, otherwise null",
    "street_address": "street and house number if filled, otherwise null",
    "postal_code": "5-digit code if filled, otherwise null",
    "city": "city name if filled, otherwise null",
    "employment_status": "one of: unemployed, part_time, self_employed, not_working — based on what is checked/filled, otherwise null",
    "monthly_income": "numeric value as string if filled, otherwise null",
    "has_partner": "yes or no based on checkbox state, otherwise null",
    "partner_first_name": "value if filled, otherwise null",
    "partner_last_name": "value if filled, otherwise null",
    "children_count": "number as string if filled, otherwise null",
    "iban": "IBAN value if filled (remove spaces), otherwise null",
    "signature_date": "DD.MM.YYYY format if filled, otherwise null"
  }
}

Rules:
- Only extract values that are CLEARLY visible and filled in on the form
- For checkboxes: determine yes/no from which box is checked
- For IBAN: remove any spaces, return continuous string
- For dates: always use DD.MM.YYYY format
- Set null for any field that is empty, unclear, or not present
- form_type should always be "alg2_antrag_v1" for Jobcenter ALG II forms
- confidence: your confidence that this is an ALG II form (0.0 to 1.0)"""


def _detect_media_type(file_bytes: bytes) -> str:
    """Detect file type from magic bytes."""
    if file_bytes[:4] == b"%PDF":
        return "application/pdf"
    if file_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if file_bytes[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    return "application/pdf"  # default


def _build_content(file_bytes: bytes, media_type: str) -> list:
    """Build the content list for the Claude API call."""
    b64_data = base64.standard_b64encode(file_bytes).decode("utf-8")

    if media_type == "application/pdf":
        doc_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64_data,
            },
        }
    else:
        doc_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_data,
            },
        }

    return [doc_block, {"type": "text", "text": EXTRACTION_PROMPT}]


def _parse_response(text: str) -> dict:
    """Extract JSON from Claude's response, handling any surrounding text."""
    text = text.strip()
    # Try to find a JSON block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    return {}


class ClaudeOCRService(OCRService):
    """
    Uses Claude Vision to extract text and field values from uploaded forms.
    Supports native PDFs and scanned images (JPEG, PNG, TIFF).
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self._client = anthropic.Anthropic()

    async def extract_text(self, file_bytes: bytes) -> OCRResult:
        media_type = _detect_media_type(file_bytes)
        content = _build_content(file_bytes, media_type)

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": content}],
            )
            raw_text = response.content[0].text
        except Exception as exc:
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": str(exc)},
            )

        try:
            data = _parse_response(raw_text)
        except (json.JSONDecodeError, Exception):
            data = {}

        extracted = data.get("extracted_fields", {})
        # Filter out null/empty values and normalize
        clean_fields: dict[str, str] = {}
        for key, value in extracted.items():
            if value and str(value).strip() not in ("null", "None", ""):
                clean_fields[FIELD_KEY_MAP.get(key, key)] = str(value).strip()

        confidence = float(data.get("confidence", 0.0))
        form_type = data.get("form_type") if confidence >= 0.7 else None

        return OCRResult(
            raw_text=raw_text,
            confidence=confidence,
            detected_form_type=form_type,
            page_count=1,
            metadata={"extracted_fields": clean_fields},
        )

    async def detect_form_type(self, ocr_result: OCRResult) -> Optional[str]:
        return ocr_result.detected_form_type
