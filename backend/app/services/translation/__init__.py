from app.services.translation.base import TranslationService, TranslationResult
from app.services.translation.mock_translation import MockTranslationService


class TranslationServiceFactory:
    @staticmethod
    def create(backend: str) -> TranslationService:
        if backend == "mock":
            return MockTranslationService()
        raise ValueError(f"Unknown translation backend: {backend}. Supported: mock")
