"""
OCR using Groq API with Llama 4 Scout vision model.
100% free — get key at https://console.groq.com
PDFs are rendered to images via PyMuPDF before sending.
"""
import base64
import json
import os
import re
from typing import Optional

import httpx

from app.services.ocr.base import OCRService, OCRResult

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

EXTRACTION_PROMPT = """You are analyzing a German Jobcenter form. Extract ALL text and filled-in values visible.

Return ONLY a valid JSON object, nothing else:
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
    "employment_status": "one of: unemployed, part_time, self_employed, not_working — from checked box or written text, else null",
    "monthly_income": "numeric value as string if filled, else null",
    "has_partner": "yes or no from checkbox state, else null",
    "partner_first_name": "value if filled, else null",
    "partner_last_name": "value if filled, else null",
    "children_count": "number as string if filled, else null",
    "iban": "IBAN without spaces if filled, else null",
    "signature_date": "DD.MM.YYYY if filled, else null"
  }
}

Rules:
- Only extract values CLEARLY visible and filled in on the form
- IBAN: remove all spaces, return continuous string
- Dates: always DD.MM.YYYY
- Null for empty or unclear fields
- confidence: how certain you are this is a Jobcenter ALG II form (0.0–1.0)"""


def _pdf_to_image(pdf_bytes: bytes) -> bytes:
    """Convert first page of PDF to PNG image using PyMuPDF."""
    import fitz  # PyMuPDF — renders PDFs without external dependencies
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(0)
    mat = fitz.Matrix(2.0, 2.0)  # 2× scale for legibility
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def _detect_mime(file_bytes: bytes) -> str:
    if file_bytes[:4] == b"%PDF":
        return "application/pdf"
    if file_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"


def _to_image_bytes(file_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """Return (image_bytes, image_mime). Converts PDF → PNG if needed."""
    if mime == "application/pdf":
        return _pdf_to_image(file_bytes), "image/png"
    return file_bytes, mime


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    return {}


class GroqOCRService(OCRService):
    """
    Uses Groq (Llama 4 Scout vision) to extract fields from German forms.
    Free tier: https://console.groq.com — no credit card required.
    PDFs are automatically converted to images before sending.
    """

    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", "")

    async def extract_text(self, file_bytes: bytes) -> OCRResult:
        if not self.api_key or self.api_key == "REPLACE_WITH_YOUR_KEY":
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": "GROQ_API_KEY not set"},
            )

        mime = _detect_mime(file_bytes)
        try:
            img_bytes, img_mime = _to_image_bytes(file_bytes, mime)
        except Exception as exc:
            return OCRResult(
                raw_text="",
                confidence=0.0,
                detected_form_type=None,
                page_count=1,
                metadata={"error": f"PDF render failed: {exc}"},
            )

        b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        data_url = f"data:{img_mime};base64,{b64}"

        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    GROQ_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
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
            raw_text = result["choices"][0]["message"]["content"]
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
