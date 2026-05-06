from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PDFGenerationRequest:
    template_id: str
    field_values: dict[str, str]       # field_id → user answer
    blank_pdf_path: str
    field_labels: dict[str, str] = field(default_factory=dict)  # field_id → human label


@dataclass
class PDFGenerationResult:
    pdf_bytes: bytes
    field_count_filled: int
    warnings: list[str] = field(default_factory=list)


class PDFGeneratorService(ABC):
    @abstractmethod
    async def generate(self, request: PDFGenerationRequest) -> PDFGenerationResult:
        ...
