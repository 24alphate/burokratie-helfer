from typing import Optional
from app.services.ocr.base import OCRService, OCRResult


class MockOCRService(OCRService):
    """Returns fixture data. Swap for Google Document AI or Tesseract later."""

    async def extract_text(self, pdf_bytes: bytes) -> OCRResult:
        return OCRResult(
            raw_text="Antrag auf Arbeitslosengeld II\nJobcenter Berlin",
            confidence=0.94,
            detected_form_type="alg2_antrag_v1",
            page_count=4,
            metadata={
                "extracted_fields": {
                    "first_name": "Max",
                    "last_name": "Mustermann",
                    "date_of_birth": "01.01.1985",
                    "nationality": "Deutsch",
                    "street_address": "Musterstraße 1",
                    "postal_code": "10115",
                    "city": "Berlin",
                },
                "strategy": "mock",
                "fields_found": 7,
            },
        )

    async def detect_form_type(self, ocr_result: OCRResult) -> Optional[str]:
        return ocr_result.detected_form_type
