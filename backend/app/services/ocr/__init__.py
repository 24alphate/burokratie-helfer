from app.services.ocr.base import OCRService, OCRResult
from app.services.ocr.mock_ocr import MockOCRService


class OCRServiceFactory:
    @staticmethod
    def create(backend: str) -> OCRService:
        if backend == "mock":
            return MockOCRService()
        if backend == "claude":
            from app.services.ocr.claude_ocr import ClaudeOCRService
            return ClaudeOCRService()
        raise ValueError(f"Unknown OCR backend: {backend!r}. Supported: mock, claude")
