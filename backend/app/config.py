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
    # Signing key for stateless PDF tokens. ALWAYS set SECRET_KEY (env or .env):
    # the os.urandom default is a last-resort fallback that changes on every
    # process start, which invalidates any in-flight pdf_token across a dev
    # server restart or a second worker/instance (BadSignature on /fill-pdf).
    # A stable value keeps tokens valid for their full 4h lifetime.
    secret_key: str = os.environ.get("SECRET_KEY") or os.urandom(32).hex()
    # Anthropic API key for the question translator + Claude Vision OCR.
    # When unset (or left as the REPLACE placeholder) translation falls back to
    # the deterministic table — never an AI call, never a crash.
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if raw.startswith("["):
            return json.loads(raw)
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
