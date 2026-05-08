# Locale QA checklist (Tier-A)

Manual verification for the language-switch P0 fix. Run for each Tier-A
locale: `en, de, fr, ar, tr, sq`.

## Setup
- Backend running locally on http://localhost:8000
- Frontend running on http://localhost:3000
- Test PDFs available: a Jobcenter BuT and the Familienkasse KG1
- Browser localStorage cleared between locales (or use Incognito)

## Per-locale checks

For each locale `LOCALE` in {en, de, fr, ar, tr, sq}:

1. Open `http://localhost:3000` and click the language button for `LOCALE`.
2. Click "Start" / "Starten" / "Commencer" / etc. → confirm landing copy is
   in the chosen language (no English ternary fallback).
3. Land on `/{LOCALE}/upload`. Confirm:
   - Page title in `LOCALE`
   - Drop-zone instruction in `LOCALE`
   - "Upload PDF" / "Scan document" cards in `LOCALE`
   - Beta scan warning in `LOCALE`
4. Upload Jobcenter BuT (a flat PDF that fingerprints as `jobcenter_but_v1`).
5. After processing, confirm:
   - Support-level banner in `LOCALE`
   - First 5 questions in `LOCALE` (not English, not raw German labels)
   - Guidance panel toggle text in `LOCALE`
   - Privacy-note paragraph in `LOCALE`
   - Delete-data button in `LOCALE`
6. Answer a few questions, then click `← New document` and `Save for later` —
   confirm both buttons + the modal copy in `LOCALE`.
7. Reach the review page. Confirm:
   - Title + instruction in `LOCALE`
   - "Generate & Download PDF" button in `LOCALE`
   - "Edit answers" link in `LOCALE`
   - "Output guarantee" banner copy in `LOCALE`
   - Disclaimer in `LOCALE`
8. Click Generate. Confirm the success state shows:
   - "PDF downloaded!" in `LOCALE`
   - Submit-to-Jobcenter line in `LOCALE`
   - On iPhone/iPad: the Save-to-Files instruction in `LOCALE`
9. Trigger an error (e.g. force-stop the backend then retry generate). Confirm
   the user-facing error message in `LOCALE`.
10. Re-upload an unsupported file (e.g. a photo) to trigger the Level-4 OCR
    diagnostic screen. Confirm the screen + status copy in `LOCALE`.
11. Repeat steps 4–10 with KG1.

## Pass criteria

For each locale you must observe **zero** of the following:
- A label that is in English when `LOCALE != en`.
- A label that is the raw German PDF label when `LOCALE != de`.
- Any "Translation unavailable" string.
- An internal field_id leaking to a user-facing surface.
- A modal/banner/button switching to English mid-flow.

The original PDF wording inside the rendered form image stays in German —
that is by design and is the official document language.

## Locale switch on a saved form

1. Upload a Jobcenter BuT in French.
2. Click the language switcher (or restart) and re-enter as Albanian.
3. Confirm Albanian questions render immediately without a re-upload — this
   verifies that `FieldDefinition.question` carries all Tier-A locales after
   the backend `field_map_to_defs` pre-fill change.

## Backend invariant

Run `pytest tests/test_locale_coverage.py -v` and verify all 76 tests pass.
That covers the same locale matrix programmatically for both templates.
