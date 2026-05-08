# Level 2 — AcroForm architecture map

Phase D/D1. Audit of the current code that powers Level 2 (fillable AcroForm
PDFs) end-to-end. Read this before changing anything in the AcroForm path.

## Trigger

A PDF is routed to Level 2 by [route_document()](../burokratie-helfer/backend/app/services/pdf_pipeline.py) when:
1. `find_matching_template(text)` returns `None` (no verified template), AND
2. `detect_pdf_type()` returns `"acroform"` — i.e., the catalog has a non-empty `/AcroForm/Fields` array.

The route returns:
```
DocumentRoute(
    support_level=2,
    extraction_source="acroform",
    pdf_type="acroform",
    template_id=None,
)
```

## Stage 1 — Extraction

Single entry point: `extract_acroform_fields(pdf_bytes) → list[FieldMapEntry]`.

```
extract_acroform_fields()
  ├─ pypdf.PdfReader(bytes)
  ├─ trailer["/Root"]["/AcroForm"]["/Fields"]  ← fields_arr
  ├─ _collect_widget_positions(reader)         ← walks all /Annots once,
  │                                              builds {field_name: (page, bbox)}
  └─ _walk_field_tree(fields_arr, seen, widget_positions)
       └─ for each field:
            ├─ if no /FT but has /Kids → recurse (group node)
            ├─ /T              → field_id (preserved as the PDF widget name)
            ├─ /FT + /Ff       → _classify_field_type(ft, flags)
            │     /Tx                      → "text"
            │     /Sig                     → "signature"
            │     /Ch + FF_MULTISELECT     → "multiselect"
            │     /Ch                      → "select"
            │     /Btn + FF_PUSHBUTTON     → None  (skipped)
            │     /Btn + FF_RADIO          → "radio"
            │     /Btn                     → "checkbox"
            ├─ /V or /DV       → current_value (prefilled)
            ├─ if select/multi → /Opt list  → options
            ├─ if radio        → _radio_options_from_kids() walks /Kids[*]/AP/N
            ├─ /TU             → human_label (preferred — tooltip text)
            └─ fallback        → _clean_acroform_field_name(/T)
```

Key data structures emitted:

```python
FieldMapEntry(
    field_id        = "<exact PDF widget name>",   # never altered — fill_pdf depends on this
    original_label  = "<TU tooltip OR cleaned widget name>",
    field_type      = "text|date|number|checkbox|radio|select|multiselect|signature",
    source_page     = int,                         # 1-indexed
    bbox            = [x0, y0, x1, y1] | None,     # widget rect in PDF points
    options         = list[str],                   # PDF-native export values
    current_value   = str,                         # prefilled value if any
    confidence      = 1.0,                         # AcroForm = ground truth
    source          = "acroform",
    source_text     = "<raw widget name>",         # grounding evidence
    semantic_key    = None,                        # set by post-extraction inference
)
```

### Helpers

- **`_classify_field_type(ft, flags) → Optional[str]`**
  Pure function: maps PDF field-type code (`/Tx`, `/Btn`, `/Ch`, `/Sig`) plus
  the `/Ff` flag bits (`_FF_RADIO`, `_FF_PUSHBUTTON`, `_FF_MULTISELECT`) to
  one of our 7 field types. Returns `None` for pushbuttons → caller skips
  them (we never ask "what would you click?").

- **`_radio_options_from_kids(field_obj) → list[str]`**
  Reads `/Kids[*]/AP/N` to extract export values for radio groups. Falls
  back to `[]` when the structure is missing or `/Off`-only (a parser quirk
  in some PDFs).

- **`_collect_widget_positions(reader) → dict[name → (page, bbox)]`**
  One-pass page-and-annotation traversal. Captures `/T` (or parent `/T` for
  child widgets), `/Subtype == /Widget`, and `/Rect`. Cap of 200 widgets
  per page, no AP stream resolution (cheap).

- **`_walk_field_tree(fields_array, seen, widget_positions, depth)`**
  Recursive descent through the `/Fields` tree. Handles intermediate group
  nodes (no `/FT`, has `/Kids`) up to depth 5. Dedupes by widget name via
  `seen` set. `MAX_FIELDS = 200` global cap.

- **`_clean_acroform_field_name(name)`**
  Best-effort cleanup of the technical widget name when `/TU` is missing:
  1. Strip known prefixes via `_ACROFORM_PREFIX_RE`
     (`txtf`, `chk`, `date`, `num`, `cb`, …).
  2. Expand German compound abbreviations (`GebDatum → Geburtsdatum`,
     `PLZ → Postleitzahl`, …) via `_DE_COMPOUND_RE`.
  3. Split camelCase: `PersonVorname → Person Vorname`.
  4. Collapse `_`/`.` → spaces.
  5. Strip the leading namespace word (`Person`, `Adresse`, `Bank`, …) via
     `_NAMESPACE_WORDS`.
  Output is in the document language (German) — the question layer
  translates downstream.

### Hard rules currently enforced

- `field_id` is the EXACT widget name from `/T`. It never gets renamed,
  cleaned, or renumbered. PyPDFGenerator reads back exactly the same name
  when filling.
- `confidence = 1.0` for every AcroForm field → all of them clear
  `CONF_SHOW_MIN = 0.70` and `CONF_REVIEW_MIN = 0.90` → `show_question=True`,
  `needs_review=False`.
- `MAX_FIELDS = 200` cap to prevent runaway PDFs (e.g. AcroForm with
  thousands of grid widgets).
- Pushbuttons (`/Btn` with `_FF_PUSHBUTTON`) are dropped at classification.
- Signatures (`/Sig`) are kept but typically routed away from the question
  flow downstream by the confidence/show gate (signature widgets carry
  confidence=0.5 in the verified-template path; in the AcroForm path they
  retain 1.0 and the user is asked for a signature placeholder).

## Stage 2 — Question resolution (process_pdf.py)

For each AcroForm `FieldMapEntry`, the same 4-priority chain Level 1 uses:

```
1. lookup_verified(field_id, original_label, locale)  → "verified"
2. lookup_semantic(infer_semantic_key(label), locale)  → "semantic"
3. get_deterministic_translation(label, lang)          → "deterministic"
4. translate_fields([...], lang)  ← Groq                 → "ai"
```

For Level 2, priority 1 returns either a generic-label hit
(`VERIFIED_BY_LABEL`: "Tag", "Monat", "Jahr", "Startort", "Zielort") or
None (since no template_id is set). Priority 2 inspects the cleaned
`original_label` against `LABEL_TO_SEMANTIC` and looks up
`SEMANTIC_QUESTIONS[key]` if matched. Priority 3 is the deterministic
dictionary in `question_translator.py` — the largest layer for AcroForm
PDFs. Priority 4 (Groq) only runs for fields that all 3 prior layers
missed.

The merge at process_pdf.py preserves source order: pre-resolved wins
over AI. `question_source` is propagated onto `FieldDefinition` for the
quality report.

## Stage 3 — Quality gating

Same `quality_flags()` checker as Level 1. For Level 2, the two
Level-1-specific flags (`verified_question_weak`, `template_field_not_verified`)
are silent because `extraction_source != "verified_template"`.

## Stage 4 — Filling (fill_pdf.py)

When the pdf_token has `template_id == None` and the PDF has AcroForm widgets:

```
fill_pdf endpoint
  └─ verify_pdf_token() → pdf_bytes, field_ids, template_id=None
  └─ grounding guard: every answer key must be in field_ids → 400 if not
  └─ since template_id is None → skip fitz_overlay branch
  └─ writes pdf_bytes to a temp file
  └─ PyPDFGenerator.generate(PDFGenerationRequest(blank_pdf_path=temp))
       └─ blank_path.exists() → reader = pypdf.PdfReader(temp)
       └─ reader.get_fields() → has AcroForm fields
       └─ _fill_acroform(request, warnings, reader)
            ├─ classify each field again: text vs radio vs checkbox
            ├─ writer.update_page_form_field_values(page, text_values)
            ├─ writer.update_page_form_field_values(page, radio_values)
            └─ for checkboxes: normalise raw answer → "Yes" or "Off"
                   (truthy: yes, ja, true, 1, x, on)
       └─ writer.add_metadata(...)
       └─ buffer.write() → bytes
  └─ Response: application/pdf
       headers: X-Fill-Strategy=pypdf_or_summary, X-Fields-Filled=N
```

### Hard rules currently enforced

- The grounding guard rejects any answer key not in `extracted_field_ids`
  (anti-injection / anti-typo defense).
- Field type classification is RE-DONE at fill time from the raw
  `reader.get_fields()` — process_pdf's classification is not trusted at
  fill time (defense in depth).
- Checkbox values are normalised on the wire to AcroForm's standard
  on/off representation.
- Pushbuttons in the form stay untouched — we never write to them.
- If `_fill_acroform` raises, the catch falls through to
  `_overlay_fallback` (the legacy reportlab summary). For Level 1 verified
  templates this fallback was disabled in Phase A R8.3 — fitz_overlay
  errors return 500 with a friendly message — but for Level 2 the
  fallback remains for now (AcroForm fill failures are rarer and the
  summary is at least usable as a paper-printable reference).

## Where Level 2 currently differs from Level 1

| Property | Level 1 (verified) | Level 2 (AcroForm) |
|---|---|---|
| field_id source | template module `get_field_map()` | PDF `/T` widget name |
| confidence | 1.0, hand-verified | 1.0, AcroForm-trusted |
| Question source | `verified` (always) | `verified` (label-matched) → `semantic` → `deterministic` → `ai` |
| `question_source` distribution | 100% verified | mixed |
| `weak_questions` invariant | must be 0 | best-effort, allowed > 0 |
| `ai_calls_made` | must be 0 | allowed > 0 |
| Fill path | `fill_with_fitz` (overlay onto original PDF) | `PyPDFGenerator._fill_acroform` (writes into widget values) |
| Fill failure behavior | clean 500 (Hard Rule 7) | falls back to reportlab summary |
| User-facing trust | "✓ Verified form" | "○ Recognized form fields" |

## Files participating in Level 2

| File | Role |
|---|---|
| [pdf_pipeline.py](../burokratie-helfer/backend/app/services/pdf_pipeline.py) | Extraction (`extract_acroform_fields`, `_walk_field_tree`, etc.) and routing |
| [question_translator.py](../burokratie-helfer/backend/app/services/question_translator.py) | Deterministic dictionary, AI translator |
| [verified_questions.py](../burokratie-helfer/backend/app/services/verified_questions.py) | `VERIFIED_BY_LABEL` (priority-1 generic-label hits) |
| [semantic_questions.py](../burokratie-helfer/backend/app/services/semantic_questions.py) | `LABEL_TO_SEMANTIC` + `SEMANTIC_QUESTIONS` (priority-2) |
| [process_pdf.py](../burokratie-helfer/backend/app/api/v1/process_pdf.py) | Resolution chain orchestration; quality report |
| [fill_pdf.py](../burokratie-helfer/backend/app/api/v1/fill_pdf.py) | Strategy selection (template_id present? → fitz; else → PyPDF) |
| [pypdf_generator.py](../burokratie-helfer/backend/app/services/pdf_generator/pypdf_generator.py) | `_fill_acroform` writes back into the original PDF; `_overlay_fallback` reportlab summary |
| [SupportLevelBanner.tsx](../burokratie-helfer/frontend/src/components/questions/SupportLevelBanner.tsx) | Level 2 = blue "Recognized form fields" surface |

## Known Level 2 limitations (today)

1. **No `semantic_key` post-inference for AcroForm fields.**
   The verified-template path sets `semantic_key` explicitly. The AcroForm
   path leaves it `None`, so the priority-2 lookup never fires for AcroForm
   PDFs — they go straight from priority 1 (label match) to priority 3
   (deterministic) to priority 4 (AI). A small enhancement (D3) would
   call `infer_semantic_key(original_label)` after extraction to populate
   `semantic_key` and let the same fields benefit from the semantic layer.

2. **No AcroForm-specific quality metrics in `analysis_report`.**
   We get the generic question-quality report, but not field-type counts,
   bbox-missing counts, semantic-key coverage, or fill_strategy. D2 adds these.

3. **No AcroForm round-trip integration test against a multi-field PDF.**
   `test_pdf_fill_fidelity.py` covers fitz overlay (Level 1). PyPDFGenerator's
   AcroForm path has only a synthetic-fixture test in `test_pdf_generator.py`,
   gated by an external blank PDF that may not exist locally. D4 adds a
   stand-alone round-trip test.

4. **No edge-case coverage for:**
   - Nested field trees (`/Kids` with no `/FT` parents)
   - Fields with explicit `/TU` tooltips
   - Duplicate field names (currently dedup'd by `seen` set, silent overwrite)
   - Checkbox export values other than "Yes"/"Off"
   - Multiselect fields with `/Opt` arrays of `[export_value, display_label]` pairs
   D5 adds parametric tests for these.

5. **Field-id collisions after `_clean_acroform_field_name()` are silent.**
   Two fields whose technical names clean to the same human label (e.g.
   `txtfPersonName` and `chkPersonName`) keep their distinct `field_id`s
   (which is correct for filling) but get the same `original_label`. The
   user sees two questions with the same text. Documented as P3-D5.

6. **Fill failure for Level 2 silently falls back to reportlab summary.**
   This is intentional for now (the summary is at least usable as a
   paper-fillable reference) but means a user can get a "PDF" that is NOT
   their original form filled in. Could be tightened later.

## What "Level 2 readiness" looks like after Phase D

- `analysis_report.support_level == 2` with field-type counts
- Common AcroForm labels (Vorname, Nachname, Geburtsdatum, PLZ, Ort,
  Straße, Telefon, E-Mail) resolved without AI
- Round-trip test for a synthetic multi-field AcroForm fixture proves:
  extraction → questions → fill → output PDF has the same widget count
- Edge cases (nested trees, /TU labels, duplicate names) are tested
- User sees the Level 2 banner with the honest "we will fill those fields
  directly — please review" message
