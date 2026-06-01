import json
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel sets VERCEL=1 in all serverless environments
IS_VERCEL = os.environ.get("VERCEL") == "1"

# On Vercel, /tmp is the only writable directory (ephemeral between cold starts)
_TMP = "/tmp"
_DEFAULT_DB = f"sqlite:///{_TMP}/burokratie.db" if IS_VERCEL else f"sqlite:///{BASE_DIR}/burokratie.db"
_DEFAULT_UPLOAD = f"{_TMP}/uploads" if IS_VERCEL else str(BASE_DIR / "uploads")
_DEFAULT_GENERATED = f"{_TMP}/generated" if IS_VERCEL else str(BASE_DIR / "generated")


class Settings(BaseSettings):
    database_url: str = _DEFAULT_DB
    ocr_backend: str = "mock"
    translation_backend: str = "mock"
    # Vision-LLM AcroForm enrichment (Level 2). "off" = use the positional
    # heuristic only; "gemini" = render pages and ask Gemini 2.0 Flash to label
    # widgets + group checkboxes (needs GEMINI_API_KEY). Falls back to the
    # heuristic on any error, so this is always a safe quality upgrade.
    vision_backend: str = "off"
    upload_dir: str = _DEFAULT_UPLOAD
    generated_dir: str = _DEFAULT_GENERATED
    static_pdfs_dir: str = str(BASE_DIR / "static_pdfs")
    form_templates_dir: str = str(Path(__file__).resolve().parent / "form_templates")
    cors_origins_raw: str = "http://localhost:3000"
    max_upload_size_mb: int = 10
    port: int = 8000
    # Signing key for stateless PDF tokens — set SECRET_KEY env var in production.
    # A random default is generated per-process so tokens expire on cold start,
    # which is the right behavior: user must re-upload after a cold start anyway.
    secret_key: str = os.urandom(32).hex()

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if raw.startswith("["):
            return json.loads(raw)
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
