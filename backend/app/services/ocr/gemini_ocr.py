"""
Real OCR using Google Gemini 2.0 Flash Vision (free tier).
Get your free API key at: https://aistudio.google.com
No credit card required.
"""
import base64
import json
import os
import re
from typing import Optional

import httpx

from app.services.ocr.base import OCRService, OCRResult

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

EXTRACTION_PROMPT = """You are analyzing a German Jobcenter form. Extract ALL text and filled-in values visible in this document.

Return ONLY a valid JSON object, no extra text:
{
  "form_type": "alg2_antrag_v1",
  "confidence": 0.95,
  "extracted_fields": {
    "first_name": "value if filled, else null",
    "last_name": "value if filled, else null",
    "date_of_birth": "DD.MM.YYYY if filled, else null",
    "nationality": "value if filled, else null",
    "street_address": "street and house number if filled, else null",
    "postal_code": "5-digit code if filled, else null",
    "city": "city name if filled, else null",
    "employment_status": "one of: unemployed, part_time, self_employed, not_working — based on what is checked or written, else null",
    "monthly_income": "numeric value as string if filled, else null",
    "has_partner": "yes or no based on checkbox, else null",
    "partner_first_name": "value if filled, else null",
    "partner_last_name": "value if filled, else null",
    "children_count": "number as string if filled, else null",
    "iban": "IBAN without spaces if filled, else null",
    "signature_date": "DD.MM.YYYY if filled, else null"
  }
}

Rules:
- Only extract values CLEARLY visible and filled in
- Checkboxes: determine yes/no from the checked box
- IBAN: remove all spaces
- Dates: always DD.MM.YYYY format
- Null for empty, unclear, or absent fields
- confidence: 0.0–1.0, how sure you are this is a Jobcenter ALG II form"""


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


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if Gemini wrapped the JSON
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    return {}


class GeminiOCRService(OCRService):
    """
    Uses Gemini 2.0 Flash to extract field values from uploaded German forms.
    Free tier at aistudio.google.com — no credit card required.
    """

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")

    async def extract_text(self, file_bytes: bytes) -> OCRResult:
        if not self.api_key or self.api_key == "REPLACE_WITH_YOUR_KEY":
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": "GEMINI_API_KEY not set"},
            )

        mime_type = _detect_mime(file_bytes)
        b64_data = base64.standard_b64encode(file_bytes).decode("utf-8")

        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": b64_data}},
                    {"text": EXTRACTION_PROMPT},
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1500,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    f"{GEMINI_API_URL}?key={self.api_key}",
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()
        except Exception as exc:
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": str(exc)},
            )

        try:
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raw_text = str(result)

        try:
            data = _parse_json(raw_text)
        except (json.JSONDecodeError, Exception):
            data = {}

        extracted = data.get("extracted_fields", {})
        clean_fields: dict[str, str] = {
            k: str(v).strip()
            for k, v in extracted.items()
            if v and str(v).strip() not in ("null", "None", "")
        }

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
