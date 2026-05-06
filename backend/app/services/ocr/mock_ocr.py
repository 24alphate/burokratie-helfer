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

    async def detect_all_fields(self, file_bytes: bytes) -> list[dict]:
        return [
            {"label": "Vorname",          "value": "Max",         "field_type": "text"},
            {"label": "Familienname",     "value": "Mustermann",  "field_type": "text"},
            {"label": "Geburtsdatum",     "value": None,          "field_type": "date"},
            {"label": "Straße",           "value": None,          "field_type": "text"},
            {"label": "Postleitzahl",     "value": None,          "field_type": "text"},
            {"label": "Ort",              "value": None,          "field_type": "text"},
            {"label": "IBAN",             "value": None,          "field_type": "text"},
        ]
