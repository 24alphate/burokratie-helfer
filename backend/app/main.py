import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal
from app.database import Base
import app.models  # noqa: F401 — ensures all models registered before table creation

from app.api.v1 import sessions, cases, documents, questions, templates, pdf
from app.services.ocr import OCRServiceFactory
from app.services.translation import TranslationServiceFactory
from app.services.pdf_generator.pypdf_generator import PDFGeneratorFactory


def _seed_templates_if_needed():
    """Seed form templates on startup. Safe to run multiple times (idempotent)."""
    from app.form_templates.seed import seed_template
    from app.models.form_template import FormTemplate

    templates_dir = Path(settings.form_templates_dir)
    db = SessionLocal()
    try:
        for json_file in templates_dir.glob("*.json"):
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            existing = db.query(FormTemplate).filter(FormTemplate.id == data["id"]).first()
            if not existing:
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

    yield


app = FastAPI(
    title="Bürokratie-Helfer API",
    description="Assists immigrants in Germany with filling out Jobcenter forms.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
