import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal
from app.database import Base
import app.models  # noqa: F401 — ensures all models registered before table creation

from app.api.v1 import sessions, cases, documents, questions, templates, pdf, process_pdf, fill_pdf
from app.services.ocr import OCRServiceFactory
from app.services.translation import TranslationServiceFactory
from app.services.pdf_generator.pypdf_generator import PDFGeneratorFactory

log = logging.getLogger("burokratie.main")


def _check_ai_runtime() -> None:
    """
    Fail LOUD (not silently) when an Anthropic key is configured but the SDK is
    not importable in THIS interpreter.

    The footgun: launching uvicorn on a Python that lacks `anthropic` (e.g. a
    global interpreter on PATH instead of backend/.venv). The app still boots,
    but translation silently degrades to the German table and scanning can't use
    Claude Vision. This check surfaces the mismatch at startup instead.
    """
    from app.services.question_translator import anthropic_key_configured
    key_set = anthropic_key_configured()
    try:
        import anthropic  # noqa: F401
        sdk_ok = True
    except Exception:
        sdk_ok = False

    if key_set and not sdk_ok:
        log.critical(
            "AI MISCONFIGURED: an Anthropic key is set but the 'anthropic' SDK is "
            "NOT importable in this interpreter (%s). Translation will fall back to "
            "the German table and scanning will fail. You are almost certainly "
            "running the server on a different Python than backend/.venv. Fix: run "
            "with the venv, e.g.  backend\\.venv\\Scripts\\python -m uvicorn "
            "app.main:app  — or  pip install -r requirements.txt  into the active "
            "interpreter.",
            sys.executable,
        )
    elif key_set:
        log.info("AI runtime OK: anthropic importable + key configured (%s).", sys.executable)
    else:
        log.info("AI runtime: no Anthropic key — using the deterministic table (%s).", sys.executable)


def _seed_templates_if_needed():
    """Seed form templates on startup. Re-seeds when the JSON version changes."""
    from app.form_templates.seed import seed_template
    from app.models.form_template import FormTemplate

    templates_dir = Path(settings.form_templates_dir)
    db = SessionLocal()
    try:
        for json_file in templates_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            existing = db.query(FormTemplate).filter(FormTemplate.id == data["id"]).first()
            if existing and existing.version == data.get("version", "1.0"):
                continue  # already up to date
            if existing:
                db.delete(existing)
                db.flush()
            seed_template(db, data)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_templates_if_needed()

    app.state.ocr_service = OCRServiceFactory.create(settings.ocr_backend)
    app.state.translation_service = TranslationServiceFactory.create(settings.translation_backend)
    app.state.pdf_generator = PDFGeneratorFactory.create("pypdf")

    _check_ai_runtime()

    yield


app = FastAPI(
    title="Bürokratie-Helfer API",
    description="Assists immigrants in Germany with filling out Jobcenter forms.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: locked to the configured frontend origin(s). When CORS_ORIGINS_RAW is
# not set (or explicitly "*") we fall back to allow-all so a fresh deploy
# without env config still works — but we log loudly because an open backend
# lets any website burn the Anthropic quota.
_cors_origins = settings.cors_origins
_cors_allow_all = (not _cors_origins) or ("*" in _cors_origins)
if _cors_allow_all:
    log.warning(
        "CORS is open to ALL origins. Set CORS_ORIGINS_RAW to your frontend "
        "URL(s) in production, e.g. CORS_ORIGINS_RAW=https://your-app.vercel.app"
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_allow_all else _cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

PREFIX = "/api/v1"
app.include_router(sessions.router, prefix=PREFIX)
app.include_router(cases.router, prefix=PREFIX)
app.include_router(documents.router, prefix=PREFIX)
app.include_router(questions.router, prefix=PREFIX)
app.include_router(templates.router, prefix=PREFIX)
app.include_router(pdf.router, prefix=PREFIX)
# Stateless pipeline — cold-start-proof, no DB or file system between calls
app.include_router(process_pdf.router, prefix=PREFIX)
app.include_router(fill_pdf.router, prefix=PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
