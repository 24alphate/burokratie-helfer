# Manual QA — Support-Level UI

Phase C/C5 deliverable. Run this checklist before every release.

The frontend has Jest installed but no React component test runner / Next.js
navigation mock configured. Spinning that up is out of scope for Phase C
(would require @testing-library/react, jest-dom, jest config, jsdom env,
router mocks). Until that infrastructure lands, this checklist is the
reliability gate for the support-level UI surface.

The behaviors under test are owned by:

- [SupportLevelBanner](../burokratie-helfer/frontend/src/components/questions/SupportLevelBanner.tsx)
- [questions/page.tsx](../burokratie-helfer/frontend/src/app/[locale]/questions/page.tsx)
- [caseStore.ts](../burokratie-helfer/frontend/src/store/caseStore.ts) — `supportLevel`/`templateId`
- [upload/page.tsx](../burokratie-helfer/frontend/src/app/[locale]/upload/page.tsx) — passes `routing` to `setFields`

## Setup

```bash
cd burokratie-helfer/frontend
npm run dev          # http://localhost:3000
```

Backend must be running locally or `NEXT_PUBLIC_API_URL` must point to a
deployed backend.

## Test PDFs

Keep these in your local `~/Downloads/qa-pdfs/` (none should be committed
to the repo):

| Name | What it is |
|---|---|
| `but-real.pdf` | Real Jobcenter "Bildung und Teilhabe" form (Level 1 trigger) |
| `wohngeld-acroform.pdf` | Any AcroForm PDF that is not a registered template |
| `flat-form.pdf` | A flat (non-fillable) PDF with extractable text |
| `scanned-photo.pdf` | A photo of a paper form, exported as PDF |

## Checklist

### Level 1 — Verified template (BuT)

Steps:
1. Open `http://localhost:3000` in a fresh browser window
2. Pick any locale (start with English, repeat in Arabic to verify RTL rendering)
3. Click "Start"
4. Upload `but-real.pdf`
5. Wait for processing to finish

Expected:
- [ ] **Green** banner at the top of the questions page reads `✓ Verified form` (or the locale equivalent)
- [ ] Banner secondary line reads `Every question has been written and reviewed by a human.`
- [ ] Banner subtitle includes the template name (e.g. `— jobcenter_but_v1`)
- [ ] No question shows the raw German label (no "Vorname", "Datum", "Tag")
- [ ] No question contains "Translation unavailable"
- [ ] Date fields show an example like `15.03.1985`
- [ ] Number fields show a format hint or example
- [ ] Checkbox questions either end with `?` or start with `Check this if…` / `Ankreuzen wenn…`
- [ ] Open browser devtools → Network → POST /api/v1/process-pdf → response body has `analysis_report.support_level == 1`, `extraction_source == "verified_template"`
- [ ] Same response: `question_quality.weak_questions == 0`
- [ ] Same response: `question_quality.ai_calls_made == 0`

Repeat the checklist in **Arabic** to verify:
- [ ] All questions render in Arabic
- [ ] RTL layout renders without overlapping the banner
- [ ] Banner shows Arabic title `نموذج موثق`
- [ ] Same backend assertions hold (weak_questions=0, ai_calls_made=0)

### Level 2 — AcroForm (no verified template)

Steps:
1. Start fresh, pick locale, click Start
2. Upload `wohngeld-acroform.pdf` (or any AcroForm PDF that doesn't match a registered template)

Expected:
- [ ] **Blue** banner reads `Recognized form fields` (or locale equivalent)
- [ ] Secondary line reads `Form fields detected automatically. Please double-check your answers.`
- [ ] Banner does NOT show a template name
- [ ] Some questions may show `needs_review` styling — that is OK
- [ ] Network: `analysis_report.support_level == 2`, `extraction_source == "acroform"`
- [ ] Network: `template_id == null`
- [ ] AI calls may be > 0 (this is allowed for Level 2)

### Level 3 — Flat readable PDF

Steps:
1. Upload `flat-form.pdf` (a plain text-based PDF with no AcroForm widgets)

Expected:
- [ ] **Amber** banner reads `Best-effort extraction`
- [ ] Secondary line reads `We did our best to find the questions. Some may be missing or unclear.`
- [ ] Network: `analysis_report.support_level == 3`, `extraction_source == "pdfplumber"`

### Level 4 — Scanned photo / unsupported

Steps:
1. Upload `scanned-photo.pdf`

Expected:
- [ ] **NOT** stuck on "Loading…"
- [ ] Page shows the level-4 unsupported screen with the 📄 icon
- [ ] Title reads `We can't read this document yet` (or locale equivalent)
- [ ] Body explains: scanned image, please upload digital PDF
- [ ] "Upload a different PDF" button returns to `/upload`
- [ ] **Red** support-level banner is visible above the unsupported screen
- [ ] Network: `analysis_report.support_level == 4`, fields list is empty

### Cross-cutting

- [ ] On every level, no Vercel/NEXT_PUBLIC_API_URL/CORS/404/500 string is visible to the user
- [ ] On every level, the page header does not flicker between locales
- [ ] Refreshing the questions page restores the support level (Zustand persist works)
- [ ] Clicking "← New document" clears the support level (Zustand `clearCurrentDocument`)

## Promoting this to automated tests

When the team is ready to invest in frontend testing infra, the steps are:

1. Add to `frontend/package.json`:
   ```json
   "test": "jest --config jest.config.ts",
   "test:watch": "jest --config jest.config.ts --watch"
   ```

2. Install:
   ```
   npm i -D @testing-library/react @testing-library/jest-dom jest-environment-jsdom
   ```

3. Create `frontend/jest.config.ts` with `next/jest` preset and a setup
   file that mocks `next/navigation` (`useRouter`, `useParams`).

4. Convert each numbered checklist item above into a `render(<Component />)`
   + assertion test. The localized strings live in
   [SupportLevelBanner.tsx](../burokratie-helfer/frontend/src/components/questions/SupportLevelBanner.tsx)
   so assertions can target `data-testid="support-level-banner"`.

5. Wire the test job into `.github/workflows/template-validation.yml`
   (or a new frontend workflow).

Until then: run this checklist before merging anything that touches the
support-level pipeline (router, store, banner component, upload page).
