from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.database import Base
import app.models  # noqa: F401 — ensures all models registered before table creation

from app.api.v1 import sessions, cases, documents, questions, templates, pdf
from app.services.ocr import OCRServiceFactory
from app.services.translation import TranslationServiceFactory
from app.services.pdf_generator.pypdf_generator import PDFGeneratorFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (Alembic handles migrations; this is a safety net)
    Base.metadata.create_all(bind=engine)

    # Wire up service implementations — swap via env vars, zero route changes needed
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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
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
