# KG1 Manual QA Checklist

Phase F/F8 deliverable. Run before demoing or shipping KG1 to production.

The automated suite (`tests/test_familienkasse_kg1.py`, 36 tests) proves the
backend invariants. **This checklist covers what only a human can verify**:
in-browser UX, real PDF viewer rendering, mobile flow.

## What's already programmatically verified (no need to repeat manually)

These were checked during the F8 automated pass — see [the automated artifacts](../burokratie-helfer/templates_source/qa_output/):

- ✅ All 6 locales (en/de/fr/ar/tr/sq): `support_level=1`, `fill_strategy=acroform`,
  `weak_questions=0`, `ai_calls_made=0`, `question_sources={'verified': 52}`
- ✅ All 12 sample text answers round-trip correctly through widgets
- ✅ All 9 radio widgets (7 Familienstand + 2 Bank account-holder) carry
  the correct `/Yes` / `/Off` after expansion
- ✅ All 46 manual + intentionally-skipped widgets (8 Steuer-ID + 25 Zählkinder
  + 4 unfilled Tabelle-1 rows + Datum-2) stay `None` in the output
- ✅ Page count preserved (5 input → 5 output)
- ✅ Output starts with `%PDF-1.7` magic
- ✅ Tabelle 1 preamble localized in all 6 locales
- ✅ Edge cases: empty Tabelle, no partner, minimal fill, empty answers,
  invented field, valid+invented all behave per spec

## What you (a human) need to verify

### Before you start

1. Backend must be running (`uvicorn app.main:app` in `backend/`) OR
   point `NEXT_PUBLIC_API_URL` at a deployed backend.
2. Frontend must be running: `npm run dev` in `frontend/` →
   <http://localhost:3000>.
3. Have the official KG1 PDF ready at
   [templates_source/familienkasse_kg1_v1.pdf](../burokratie-helfer/templates_source/familienkasse_kg1_v1.pdf)
   (already there).
4. Optional: open the pre-filled sample artifact at
   [templates_source/qa_output/familienkasse_kg1_v1_filled_sample.pdf](../burokratie-helfer/templates_source/qa_output/familienkasse_kg1_v1_filled_sample.pdf)
   — the same one the automated suite produced, so you can compare against
   what the browser flow ends up generating.

---

## Section 1 — Browser upload (per locale)

For each locale, repeat the upload + question flow. **Locales: en, de, fr, ar, tr, sq.**

### Steps
1. Open `http://localhost:3000`
2. Pick the locale on the home screen
3. Click **Start**
4. Upload `familienkasse_kg1_v1.pdf`
5. Wait for processing (should be < 3 seconds)

### Confirm (per locale)
- [ ] **Green** Level 1 banner reads `Verified form` (or locale equivalent)
- [ ] Banner subtitle includes template name: `familienkasse_kg1_v1` or
      "Familienkasse — Antrag auf Kindergeld (KG1)"
- [ ] Output guarantee on review screen reads "Fillable PDF: your answers
      will be inserted into the PDF's digital form fields." (locale-equivalent)
- [ ] In the upload-page diagnostic table: `extraction_source = verified_template`,
      `template_id = familienkasse_kg1_v1`, `fill_strategy = acroform`,
      `field_count = 85`, `questions_shown = 52`
- [ ] **No** raw German labels appear as user-facing questions
      (no "Vorname-Antragsteller", no "topmostSubform[0]…")
- [ ] **No** "Translation unavailable" or `?` placeholders
- [ ] All questions render in the selected locale (Arabic should be RTL)

### Section 2 — Question flow visual QA

Browse through the 52 questions. Spot-check:
- [ ] Question text is understandable to a non-German speaker
- [ ] Help text appears when expanded (GuidancePanel)
- [ ] Date fields show example like `15.03.1985`
- [ ] Number fields show format hint (e.g. for Anzahl-Anlagen)
- [ ] **Tabelle 1 preamble is shown** on the first child question and
      explicitly says "only for children for whom you already receive Kindergeld"
- [ ] Steuer-ID is **not** asked as a normal question
      (verify by searching the question list — none should mention "Steuer")
- [ ] Zählkinder is **not** asked as a normal question
- [ ] (KNOWN v1 LIMITATION) Partner section IS shown to all users — note
      this in the demo as "we'll skip these for a single applicant"
- [ ] (KNOWN v1 LIMITATION) Familienstand "seit when" date IS shown even
      when user picks `ledig` — note this similarly

### Section 3 — Fill representative answers

Use the exact sample data from the F8 spec:

| Field | Value |
|---|---|
| First name | Anna |
| Last name | Müller |
| Birth date | 15.03.1985 |
| Address | Musterstraße 1, 18055 Rostock |
| Phone | 017612345678 |
| Familienstand | verheiratet |
| Familienstand "seit" | 01.06.2015 |
| IBAN | DE89370400440532013000 |
| BIC | COBADEFFXXX |
| Bank | Commerzbank |
| Account holder | applicant |
| Child 1 first name | Lena Müller |
| Child 1 birth date | 12.03.2016 |
| Child 1 gender | w |
| Child 1 Familienkasse | Familienkasse Rostock, KG-Nr 12345BG0001234 |
| Form date 1 | (today) |

Confirm:
- [ ] All fields accept the input
- [ ] No JavaScript errors in browser console
- [ ] "Generate & Download PDF" button enables once enough fields are filled

### Section 4 — Download verification

Click **Generate & Download PDF**. Open the resulting file.

Side-by-side comparison: open
[the automated sample](../burokratie-helfer/templates_source/qa_output/familienkasse_kg1_v1_filled_sample.pdf)
in another window to compare.

- [ ] File downloads successfully
- [ ] Filename includes "familienkasse-kg1-v1" + today's date
- [ ] PDF opens in your default viewer
- [ ] **Page count = 5** (use viewer's page indicator)
- [ ] Original layout unchanged (KG1 official form visual identity intact)
- [ ] Applicant values visible in correct fields (Anna, Müller, 15.03.1985, …)
- [ ] IBAN per-character grid is filled correctly
- [ ] BIC, bank name, account holder name visible
- [ ] **Familienstand: only "verheiratet" is checked** (other 6 boxes empty)
- [ ] **Account holder: only "Antragsteller" is checked** (other empty)
- [ ] Tabelle 1 row 1 has Lena Müller, 12.03.2016, w, Familienkasse Rostock…
- [ ] **Tabelle 1 rows 2–5 are blank**
- [ ] **Steuer-ID boxes are blank** (correct — manual)
- [ ] **Tabelle 2 Zählkinder is fully blank** (correct — manual)
- [ ] **Signature areas blank** (correct — wet signature)
- [ ] No summary PDF was generated (you got the original Familienkasse form)
- [ ] No visual corruption (no overlapping text, no garbled chars,
      no missing umlauts in `Müller`, `Straße`)

### Section 5 — Viewer compatibility

Open the same downloaded PDF in 2–3 viewers:

- [ ] **Chrome PDF viewer** — text + radios render correctly
- [ ] **Adobe Acrobat / Adobe Reader** if available — highest fidelity
- [ ] **macOS Preview** OR **Windows Edge PDF / built-in viewer**
- [ ] (Optional) Print preview — fields appear correctly when printed

If a viewer renders the form differently, note WHICH viewer + WHICH field
in the report.

### Section 6 — Mobile QA

Open `http://<your-ip>:3000` (the `dev:mobile` script in frontend/package.json
binds to 0.0.0.0).

- [ ] Upload from phone works (use Files / Photos sharing the PDF)
- [ ] Questions are readable on small screen
- [ ] Review page shows all answered fields
- [ ] Download triggers
- [ ] **On iPhone**: the "On iPhone or iPad" Save-to-Files instruction panel
      appears on the success screen (Phase A/C3 deliverable)
- [ ] On Android Chrome: download saves to Downloads

### Section 7 — Error / edge cases

These are programmatically verified but worth a manual sanity check:

- [ ] Leave Tabelle 1 fully empty → PDF still generates correctly,
      just with empty rows
- [ ] Don't fill any partner fields → output PDF has empty Punkt 2 section
- [ ] Fill only the 4 most basic fields and download → PDF generates,
      most widgets stay blank
- [ ] Click "Delete my saved data" on the questions page → state is wiped,
      back to home page (Phase E/E4)
- [ ] Refresh the questions page mid-fill → answers persist (Zustand)

---

## Final report template

After running through this checklist, fill in:

- **Locales tested**: ___
- **Browser(s) tested**: ___
- **PDF viewer(s) tested**: ___
- **Mobile device tested**: ___ (or "skipped")
- **Visual placement**: ___ (good / acceptable / issues)
- **Unreadable / misplaced fields**: ___ (none / list)
- **UX confusion observed**: ___ (especially around partner-section + Familienstand-seit
  unconditionality, which are KNOWN v1 limitations)
- **Demo-ready?**: yes / no — if no, list blockers

## Known v1 limitations (show honestly in any demo)

These are intentional scope choices, NOT bugs. Acknowledge them upfront:

1. **Steuer-ID is manual.** The 8 Steuer-ID widgets stay blank. The user
   fills them by hand on the printed PDF. (Reason: each Steuer-ID is split
   across 4 widgets, and asking the user "digits 1–2 of 11" is bad UX.
   Splitting one logical answer across multiple widgets is a v2 engine
   feature.)
2. **Tabelle 2 Zählkinder is manual.** The 25 widgets stay blank.
   (Reason: Zählkinder is a conceptually subtle disclosure section; we
   deliberately did not author guidance for v1.)
3. **Partner section is unconditional.** Single applicants will see all 8
   partner questions. Convention: leave them blank. (v2: gate with
   "Do you have a partner?")
4. **Familienstand "seit" date is unconditional.** A `ledig` user is still
   asked "Since when has your current marital status applied?" — they
   can leave it blank. (v2: conditional question flow.)
5. **Anzahl-Anlagen is text** with format hint, not numeric input. A user
   could type "one" instead of "1".
6. **Wet signature required.** The form has 2 signature lines that are
   never auto-filled — user prints + signs by hand.
