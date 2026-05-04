import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{BASE_DIR}/burokratie.db"
    ocr_backend: str = "mock"
    translation_backend: str = "mock"
    upload_dir: str = str(BASE_DIR / "uploads")
    generated_dir: str = str(BASE_DIR / "generated")
    static_pdfs_dir: str = str(BASE_DIR / "static_pdfs")
    form_templates_dir: str = str(Path(__file__).resolve().parent / "form_templates")
    # Accepts comma-separated string OR JSON array for Railway/Vercel env var compatibility
    cors_origins_raw: str = "http://localhost:3000"
    max_upload_size_mb: int = 10
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if raw.startswith("["):
            return json.loads(raw)
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
