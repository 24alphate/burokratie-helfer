from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OCRResult:
    raw_text: str
    confidence: float
    detected_form_type: Optional[str]
    page_count: int
    metadata: dict = field(default_factory=dict)


class OCRService(ABC):
    @abstractmethod
    async def extract_text(self, pdf_bytes: bytes) -> OCRResult:
        """Extract text from PDF bytes. Never log result.raw_text (contains PII)."""
        ...

    @abstractmethod
    async def detect_form_type(self, ocr_result: OCRResult) -> Optional[str]:
        """Return a FormTemplate ID if the document matches a known form, else None."""
        ...
