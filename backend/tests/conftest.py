import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.services.ocr import OCRServiceFactory
from app.services.translation import TranslationServiceFactory
from app.services.pdf_generator.pypdf_generator import PDFGeneratorFactory
from app.form_templates.seed import seed_template

TEST_DATABASE_URL = "sqlite:///./test.db"
TEMPLATE_JSON = Path(__file__).parent.parent / "app" / "form_templates" / "alg2_antrag_v1.json"


@pytest.fixture(scope="session")
def test_engine():
    eng = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="session")
def TestSession(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session")
def client(test_engine, TestSession):
    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.ocr_service = OCRServiceFactory.create("mock")
    app.state.translation_service = TranslationServiceFactory.create("mock")
    app.state.pdf_generator = PDFGeneratorFactory.create("pypdf")

    # Seed form template into the test DB
    db = TestSession()
    try:
        with open(TEMPLATE_JSON, encoding="utf-8") as f:
            data = json.load(f)
        seed_template(db, data)
    finally:
        db.close()

    with TestClient(app) as c:
        yield c
