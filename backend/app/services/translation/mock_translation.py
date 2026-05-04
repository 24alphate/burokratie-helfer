from typing import Optional
from app.services.translation.base import TranslationService, TranslationResult

# Static mappings for boolean/enum values → German
_STATIC_MAP = {
    "yes": "Ja",
    "no": "Nein",
    "unemployed": "Arbeitslos",
    "part_time": "Teilzeitbeschäftigt",
    "self_employed": "Selbstständig",
    "not_working": "Nicht erwerbstätig",
}


class MockTranslationService(TranslationService):
    """
    Returns input unchanged for free-text fields (names, addresses don't need translation).
    Applies static German mappings for known enum/boolean values.
    Replace with LLM or DeepL when ready.
    """

    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str = "de",
        field_context: Optional[str] = None,
    ) -> TranslationResult:
        translated = _STATIC_MAP.get(text.lower(), text)
        return TranslationResult(
            original_text=text,
            translated_text=translated,
            source_language=source_language,
            target_language=target_language,
        )
