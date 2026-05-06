"""
POST /api/v1/fill-pdf — stateless PDF filling endpoint.

Filling strategy (chosen automatically from the token):

  1. Verified template (template_id present in token)
     → fitz_overlay: overlay text and X marks onto the ORIGINAL PDF bytes.
     → Returns the original PDF layout with answers filled in.

  2. AcroForm PDF (no template_id, but PDF has AcroForm fields)
     → pypdf: fill AcroForm field values in-place.
     → Returns the original PDF with field values written.

  3. Unknown flat PDF (no template_id, no AcroForm)
     → reportlab: generate a formatted answer-summary document.
     → Returns a new document (not the original layout).

Request body:
  {
    "pdf_token":     "<signed token from /process-pdf>",
    "answers":       { "field_id": "user answer", ... },
    "field_labels":  { "field_id": "German label", ... },   // for summary fallback
    "debug_overlay": false                                   // dev: draw red boxes at write positions
  }

Response headers on verified-template fills:
  X-Fill-Strategy:      "fitz_overlay"
  X-Fields-Filled:      "12"
  X-Not-Fillable-Fields: "signature_antragsteller,signature_vertreter"
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel

from app.config import settings
from app.services.pdf_token import verify_pdf_token

log = logging.getLogger("burokratie.fill_pdf")

router = APIRouter(tags=["stateless"])


class FillPdfRequest(BaseModel):
    pdf_token: str
    answers: dict[str, str]               # field_id → raw answer
    field_labels: dict[str, str] = {}     # field_id → German label (used by summary fallback)
    debug_overlay: bool = False           # dev: draw red boxes at write positions


@router.post("/fill-pdf")
async def fill_pdf(body: FillPdfRequest):
    """
    Decode the PDF token and fill the form with the provided answers.

    Returns the filled PDF as application/pdf (triggers browser download).

    Errors:
      400 — answer key not in extracted field map (grounding guard)
      401 — token expired (user must re-upload)
      403 — token signature invalid
      422 — no answers provided
    """
    if not body.answers:
        raise HTTPException(status_code=422, detail="No answers provided.")

    # ── 1. Verify + decode token ──────────────────────────────────────────────
    try:
        token_data = verify_pdf_token(body.pdf_token, settings.secret_key)
    except SignatureExpired:
        raise HTTPException(
            status_code=401,
            detail="PDF session expired (> 4 hours). Please re-upload the PDF.",
        )
    except (BadSignature, Exception) as e:
        log.warning("fill-pdf BAD_TOKEN: %s", e)
        raise HTTPException(
            status_code=403,
            detail="Invalid PDF token. Please re-upload the PDF.",
        )

    pdf_bytes: bytes     = token_data["pdf_bytes"]
    field_ids: list[str] = token_data["field_ids"]
    filename: str        = token_data.get("filename", "form.pdf")
    template_id: str | None = token_data.get("template_id")

    log.info(
        "fill-pdf START filename=%s template_id=%s field_count=%d answer_count=%d",
        filename, template_id, len(field_ids), len(body.answers),
    )

    # ── 2. Grounding guard ───────────────────────────────────────────────────
    extracted_set = set(field_ids)
    invalid_keys  = [k for k in body.answers if k not in extracted_set]
    if invalid_keys:
        log.error("fill-pdf GROUNDING_VIOLATION invalid_keys=%s", invalid_keys)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Answer key(s) not in extracted PDF field map: {invalid_keys}. "
                "Only fields extracted from the uploaded PDF can be filled."
            ),
        )

    safe_name = filename.rsplit(".", 1)[0] + "_filled.pdf"

    # ── 3a. Verified template → fitz overlay onto original PDF ───────────────
    if template_id:
        from app.services.form_templates import find_template_by_id
        template = find_template_by_id(template_id)
        if template:
            write_specs = template.get_write_specs()
            from app.services.pdf_generator.fitz_overlay import fill_with_fitz
            try:
                out_bytes, filled_ids, skipped_ids = fill_with_fitz(
                    pdf_bytes,
                    body.answers,
                    write_specs,
                    debug=body.debug_overlay,
                )
            except Exception as e:
                log.error("fill-pdf FITZ_ERROR: %s — falling back to summary", e)
                # Fall through to legacy path
            else:
                log.info(
                    "fill-pdf FITZ_DONE filename=%s filled=%d skipped=%d",
                    filename, len(filled_ids), len(skipped_ids),
                )
                headers = {
                    "Content-Disposition": f'attachment; filename="{safe_name}"',
                    "X-Fill-Strategy": "fitz_overlay",
                    "X-Fields-Filled": str(len(filled_ids)),
                    "Access-Control-Expose-Headers":
                        "X-Fill-Strategy,X-Fields-Filled,X-Not-Fillable-Fields",
                }
                if skipped_ids:
                    # Only include fields the user answered but couldn't be placed
                    not_placed = [s for s in skipped_ids if s in body.answers]
                    if not_placed:
                        headers["X-Not-Fillable-Fields"] = ",".join(not_placed)
                return Response(
                    content=out_bytes,
                    media_type="application/pdf",
                    headers=headers,
                )

    # ── 3b. AcroForm / unknown flat → legacy PyPDFGenerator path ─────────────
    import os
    import tempfile
    from app.services.pdf_generator.base import PDFGenerationRequest
    from app.services.pdf_generator.pypdf_generator import PyPDFGenerator

    _generator = PyPDFGenerator()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(pdf_bytes)
        gen_request = PDFGenerationRequest(
            template_id=template_id or "stateless",
            field_values=body.answers,
            blank_pdf_path=tmp_path,
            field_labels=body.field_labels,
        )
        result = await _generator.generate(gen_request)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.warnings:
        log.warning("fill-pdf WARNINGS filename=%s: %s", filename, result.warnings)

    log.info(
        "fill-pdf LEGACY_DONE filename=%s filled_fields=%d output_kb=%d",
        filename, result.field_count_filled, len(result.pdf_bytes) // 1024,
    )

    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Fill-Strategy": "pypdf_or_summary",
            "Access-Control-Expose-Headers": "X-Fill-Strategy,X-Fields-Filled,X-Not-Fillable-Fields",
        },
    )
