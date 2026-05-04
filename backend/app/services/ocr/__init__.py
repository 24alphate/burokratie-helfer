from app.services.ocr.base import OCRService, OCRResult
from app.services.ocr.mock_ocr import MockOCRService


class OCRServiceFactory:
    @staticmethod
    def create(backend: str) -> OCRService:
        if backend == "mock":
            return MockOCRService()
        raise ValueError(f"Unknown OCR backend: {backend}. Supported: mock")
