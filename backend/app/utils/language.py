SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "العربية",
    "tr": "Türkçe",
    "de": "Deutsch",
    "fa": "فارسی",
    "ru": "Русский",
    "uk": "Українська",
    "so": "Soomaali",
    "ti": "ትግርኛ",
    "ps": "پښتو",
}

DEFAULT_LANGUAGE = "en"


def is_supported(lang_code: str) -> bool:
    return lang_code in SUPPORTED_LANGUAGES
