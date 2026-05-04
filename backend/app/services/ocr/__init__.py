from app.services.ocr.base import OCRService, OCRResult
from app.services.ocr.mock_ocr import MockOCRService


class OCRServiceFactory:
    @staticmethod
    def create(backend: str) -> OCRService:
        if backend == "mock":
            return MockOCRService()
        if backend in ("smart", "groq"):
            # "smart" = full pipeline: pdfplumber + PyMuPDF + LangChain + instructor + Groq
            from app.services.ocr.smart_ocr import SmartOCRService
            return SmartOCRService()
        if backend == "gemini":
            from app.services.ocr.gemini_ocr import GeminiOCRService
            return GeminiOCRService()
        if backend == "claude":
            from app.services.ocr.claude_ocr import ClaudeOCRService
            return ClaudeOCRService()
        raise ValueError(
            f"Unknown OCR backend: {backend!r}. "
            "Supported: mock, smart (or groq), gemini, claude"
        )
