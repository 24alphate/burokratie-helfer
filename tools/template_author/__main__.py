"""
template-author — CLI for authoring Bürokratie-Helfer verified templates.

Subcommands:
  extract     Parse a PDF and dump field candidates (AcroForm + pdfplumber) as JSON
  fingerprint Suggest 3 unique phrases that uniquely identify the form
  validate    Run validate_template() on a registered template (or all templates)
  list        List all registered templates with field counts and locale coverage
  hash        Compute and store SHA256 hash for a source PDF

Usage (run from the burokratie-helfer/ repo root):
  python -m tools.template_author extract path/to/form.pdf
  python -m tools.template_author fingerprint path/to/form.pdf
  python -m tools.template_author validate jobcenter_but_v1
  python -m tools.template_author validate --all
  python -m tools.template_author list
  python -m tools.template_author hash path/to/form.pdf
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "burokratie-helfer" / "backend"
if not BACKEND_ROOT.exists():
    BACKEND_ROOT = REPO_ROOT / "backend"

sys.path.insert(0, str(BACKEND_ROOT))


def _cmd_extract(args: argparse.Namespace) -> int:
    from tools.template_author.extract import extract_pdf_fields
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    result = extract_pdf_fields(pdf_path.read_bytes())
    import json
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(out)
    return 0


def _cmd_fingerprint(args: argparse.Namespace) -> int:
    from tools.template_author.fingerprint import suggest_fingerprint_phrases
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    suggestions = suggest_fingerprint_phrases(pdf_path.read_bytes(), top_n=args.top_n)
    print(f"Fingerprint candidates for {pdf_path.name}:")
    print(f"  (suggested 3 most unique phrases — verify against control PDFs)")
    print()
    for i, phrase in enumerate(suggestions, 1):
        print(f"  {i}. {phrase!r}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from app.services.form_templates import _all_templates, validate_template
    templates = _all_templates()
    if not args.all_templates:
        templates = [t for t in templates if t.template_id == args.template_id]
        if not templates:
            print(f"ERROR: template not found: {args.template_id}", file=sys.stderr)
            return 1
    total_errors = 0
    for t in templates:
        errors = validate_template(t)
        status = "OK" if not errors else f"{len(errors)} error(s)"
        print(f"[{t.template_id}] {status}")
        for err in errors:
            print(f"  - {err}")
        total_errors += len(errors)
    print()
    print(f"Validated {len(templates)} template(s), {total_errors} error(s) total")
    return 1 if total_errors else 0


def _cmd_list(args: argparse.Namespace) -> int:
    from app.services.form_templates import _all_templates
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    templates = _all_templates()
    locales = ["en", "de", "fr", "ar", "tr", "sq", "es", "ru", "uk"]
    for t in templates:
        field_map = t.get_field_map()
        non_sig = [f for f in field_map if f.confidence > 0.5]
        write_specs = t.get_write_specs()
        coverage = {}
        for loc in locales:
            covered = sum(
                1 for f in non_sig
                if VERIFIED_BY_FIELD_ID.get(f.field_id, {}).get(loc, {}).get("question")
            )
            coverage[loc] = f"{covered}/{len(non_sig)}"
        print(f"{t.template_id}")
        print(f"  name:        {t.name}")
        print(f"  fields:      {len(field_map)} ({len(non_sig)} non-signature)")
        print(f"  write_specs: {len(write_specs)}")
        print(f"  locales:     " + ", ".join(f"{loc}={c}" for loc, c in coverage.items()))
        print()
    return 0


def _cmd_hash(args: argparse.Namespace) -> int:
    import hashlib
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    print(f"SHA256({pdf_path.name}) = {digest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="template-author",
        description="CLI for authoring Bürokratie-Helfer verified templates",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="Extract field candidates from a PDF")
    p_extract.add_argument("pdf", help="Path to source PDF")
    p_extract.add_argument("-o", "--output", help="Write JSON to this file")
    p_extract.set_defaults(func=_cmd_extract)

    p_fp = sub.add_parser("fingerprint", help="Suggest unique phrases for fingerprinting")
    p_fp.add_argument("pdf", help="Path to source PDF")
    p_fp.add_argument("--top-n", type=int, default=10, help="Number of phrases to suggest")
    p_fp.set_defaults(func=_cmd_fingerprint)

    p_val = sub.add_parser("validate", help="Validate a template against the contract")
    p_val.add_argument("template_id", nargs="?", default="", help="Template ID to validate")
    p_val.add_argument("--all", dest="all_templates", action="store_true", help="Validate all templates")
    p_val.set_defaults(func=_cmd_validate)

    p_list = sub.add_parser("list", help="List all registered templates")
    p_list.set_defaults(func=_cmd_list)

    p_hash = sub.add_parser("hash", help="Compute SHA256 of a PDF")
    p_hash.add_argument("pdf", help="Path to source PDF")
    p_hash.set_defaults(func=_cmd_hash)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
