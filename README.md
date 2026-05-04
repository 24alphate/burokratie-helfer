# Bürokratie-Helfer

Form assistance for immigrants in Germany — starting with Jobcenter ALG II forms.

> **Disclaimer:** This is a form completion tool only. We provide no legal advice.

---

## What it does

1. User selects their language (Arabic, Turkish, English, German, etc.)
2. Uploads a Jobcenter PDF
3. System detects the form type (mocked in MVP — always detects ALG II)
4. Asks questions one by one in the user's language with plain-language explanations
5. Skips irrelevant questions automatically (e.g. partner questions skipped if user has no partner)
6. Validates each answer (required fields, date formats, IBAN check)
7. Shows a review screen with all answers
8. Generates a completed German PDF
9. User downloads and brings it to the Jobcenter

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### Backend

```bash
cd burokratie-helfer/backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements-dev.txt

# Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# Edit .env if needed (defaults work for local SQLite)

# Run database migrations
alembic upgrade head

# Seed the ALG II form template into the database
python -m app.form_templates.seed

# Start the backend
uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000
API docs: http://localhost:8000/docs

### Frontend

```bash
cd burokratie-helfer/frontend

npm install

# Copy env file (defaults work for local development)
copy .env.local.example .env.local      # Windows
# cp .env.local.example .env.local      # macOS/Linux

npm run dev
```

Frontend runs at: http://localhost:3000

---

## Running Tests

```bash
cd burokratie-helfer/backend
.venv\Scripts\activate
pytest tests/ -v
```

---

## What Works (MVP Skeleton)

| Feature | Status |
|---|---|
| Language selection | ✅ Working |
| Anonymous session creation | ✅ Working |
| Case creation | ✅ Working |
| PDF upload | ✅ Working (saves file to disk) |
| OCR form detection | 🟡 Mocked — always returns ALG II |
| Manual form type selection | ✅ Working |
| Question-by-question flow | ✅ Working |
| Conditional logic (skip questions) | ✅ Working |
| Validation (required, regex, date, IBAN) | ✅ Working |
| Answer translation | 🟡 Mocked — enum values mapped, free text returned as-is |
| Review screen | ✅ Working |
| PDF generation (overlay/fallback) | ✅ Working (text summary PDF if no blank template) |
| PDF generation (AcroForm fill) | 🟡 Ready — needs `static_pdfs/alg2_blank.pdf` |
| PDF download | ✅ Working |
| Audit logs | ✅ Working (no PII stored) |

---

## What Is Mocked

| Component | Mock behavior | Replace with |
|---|---|---|
| OCR | Returns fixture text, detects `alg2_antrag_v1` | Google Document AI, Tesseract |
| Translation | Enum values → German, free text unchanged | GPT-4o, DeepL |
| PDF blank form | Falls back to text-summary PDF | Real ALG II blank form with AcroForm fields |
| File storage | Local filesystem | GCS / S3 via StorageService |

### To add real OCR:

1. Create `backend/app/services/ocr/google_ocr.py` implementing `OCRService`
2. Add `"google_document_ai"` branch to `OCRServiceFactory.create()`
3. Set `OCR_BACKEND=google_document_ai` in `.env`

### To add real translation:

1. Create `backend/app/services/translation/openai_translation.py` implementing `TranslationService`
2. Add `"openai"` branch to `TranslationServiceFactory.create()`
3. Set `TRANSLATION_BACKEND=openai` in `.env`

---

## To enable AcroForm PDF filling:

1. Obtain the blank ALG II form PDF (from BA/Jobcenter website)
2. Inspect its AcroForm field names (use `pypdf` or Adobe Acrobat)
3. Update `backend/app/form_templates/alg2_antrag_v1.json` → `pdf_field_map` to match actual field names
4. Place the blank PDF at `backend/static_pdfs/alg2_blank.pdf`

---

## PostgreSQL Migration

Change one line in `.env`:

```
DATABASE_URL=postgresql+psycopg2://user:password@localhost/burokratie
```

Then run `alembic upgrade head`. No code changes needed.

---

## Adding a New Form Template

1. Create `backend/app/form_templates/<new_form_id>.json` following the same schema as `alg2_antrag_v1.json`
2. Run `python -m app.form_templates.seed` to load it into the DB
3. The new form will appear in `GET /api/v1/templates` and be available for upload detection

---

## Project Structure

```
burokratie-helfer/
├── backend/              FastAPI backend
│   ├── app/
│   │   ├── main.py       FastAPI app + service wiring
│   │   ├── models/       SQLAlchemy ORM models
│   │   ├── schemas/      Pydantic request/response models
│   │   ├── api/v1/       Route handlers
│   │   ├── services/     OCR, translation, PDF, form engine, validation
│   │   └── form_templates/  ALG II form definition JSON
│   └── tests/            pytest test suite
└── frontend/             Next.js 14 frontend
    └── src/
        ├── app/          Pages (landing, upload, questions, review, download)
        ├── components/   UI components
        ├── lib/          API client
        ├── store/        Zustand state
        └── locales/      UI strings in EN, AR, TR, DE
```

---

## Security Notes

- Audit logs store no PII — only `field_key`, `template_id`, `case_id`
- OCR text is stored but never returned to the client
- Uploaded files are stored locally under `backend/uploads/` (gitignored)
- AI translation output is validated before being written to PDF fields
- No AI ever writes directly to PDF fields without passing through ValidationService first
- This app is not a legal advice tool — all pages include disclaimers
