# Source PDFs for verified templates

This directory holds the canonical source PDF for every registered Level 1 template.

## Structure

```
templates_source/
  registry.json          # SHA256 hash + metadata for every template
  jobcenter_but_v1.pdf   # source PDF — exactly what the template was authored against
  wohngeld_v1.pdf        # (future)
  ...
```

## Why we store source PDFs

1. **Reproducibility** — anyone can regenerate WriteSpec coordinates from the exact PDF the template was tuned against.
2. **Version monitoring** — the daily version-monitor service downloads the live source URL and compares its hash against `registry.json`. A hash mismatch means the form changed.
3. **Golden testing** — acceptance tests load the source PDF, run the full process → fill cycle, and compare against a golden output.
4. **Onboarding** — new contributors can author or audit a template without hunting for the right PDF version.

## registry.json schema

```json
{
  "templates": {
    "jobcenter_but_v1": {
      "name": "Jobcenter — Antrag auf Leistungen für Bildung und Teilhabe",
      "source_url": "https://www.arbeitsagentur.de/.../but-antrag.pdf",
      "source_pdf": "jobcenter_but_v1.pdf",
      "sha256": "...",
      "version_label": "Stand: 01/2026",
      "added_at": "2026-05-07",
      "owner": "team-bh"
    }
  }
}
```

## Adding a new source PDF

```bash
# 1. Download the official PDF
curl -o templates_source/wohngeld_v1.pdf https://example.de/.../wohngeld.pdf

# 2. Compute the hash
python -m tools.template_author hash templates_source/wohngeld_v1.pdf

# 3. Add an entry to registry.json with the hash and source URL

# 4. Commit both the PDF and registry.json change in the same PR
```

## Why .pdf files are committed (not gitignored)

These are public government documents. Storing them in the repo makes the whole authoring + testing chain reproducible from a single git checkout. Total size budget: under 50 MB across 200 templates (typical PDF is 100–500 KB).
