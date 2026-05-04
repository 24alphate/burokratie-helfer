from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


class TranslationService(ABC):
    @abstractmethod
    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str = "de",
        field_context: Optional[str] = None,
    ) -> TranslationResult:
        """
        Translate text from source_language to target_language.
        field_context (e.g. "city", "nationality") helps LLM produce better output.
        """
        ...
