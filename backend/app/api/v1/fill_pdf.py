"""
POST /api/v1/fill-pdf — stateless PDF filling endpoint.

The client sends:
  {
    "pdf_token": "<signed token from /process-pdf>",
    "answers":   { "field_id": "user answer", ... }
  }

The server:
  1. Verifies the token signature and expiry (4-hour window)
  2. Decodes pdf_bytes + field_ids from the token
  3. Validates all answer keys are in field_ids (grounding guard)
  4. Writes PDF bytes to a short-lived temp file (within this request only)
  5. Fills the PDF using pypdf (AcroForm) or reportlab (flat PDF fallback)
  6. Deletes the temp file and streams the filled PDF

The temp file exists only for the duration of the request — it is NOT stored
between requests.  Writing it to /tmp within a single Lambda invocation is safe
and expected on Vercel.  No cold-start issues.
"""
from __future__ import annotations

import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel

from app.config import settings
from app.services.pdf_generator.base import PDFGenerationRequest
from app.services.pdf_generator.pypdf_generator import PyPDFGenerator
from app.services.pdf_token import verify_pdf_token

log = logging.getLogger("burokratie.fill_pdf")

router = APIRouter(tags=["stateless"])

_generator = PyPDFGenerator()


class FillPdfRequest(BaseModel):
    pdf_token: str
    answers: dict[str, str]                    # field_id → raw_answer
    field_labels: dict[str, str] = {}          # field_id → human label (for overlay PDF)


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

    log.info(
        "fill-pdf START filename=%s token_field_count=%d answer_count=%d",
        filename, len(field_ids), len(body.answers),
    )

    # ── 2. Grounding guard: every answer key must be in the extracted field map ──
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

    # ── 3. Write PDF to a temp file for this request only ────────────────────
    # We write to /tmp within this single Lambda invocation.
    # The file is deleted before the response is sent — it is NOT stored between requests.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(pdf_bytes)

        # ── 4. Fill the PDF ───────────────────────────────────────────────────
        gen_request = PDFGenerationRequest(
            template_id="stateless",
            field_values=body.answers,
            blank_pdf_path=tmp_path,
            field_labels=body.field_labels,
        )
        result = await _generator.generate(gen_request)

    finally:
        # Always delete the temp file — even if generation fails
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.warnings:
        log.warning("fill-pdf WARNINGS filename=%s: %s", filename, result.warnings)

    log.info(
        "fill-pdf DONE filename=%s filled_fields=%d output_kb=%d",
        filename, result.field_count_filled, len(result.pdf_bytes) // 1024,
    )

    # ── 5. Stream filled PDF to client ───────────────────────────────────────
    safe_name = filename.rsplit(".", 1)[0] + "_filled.pdf"
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
