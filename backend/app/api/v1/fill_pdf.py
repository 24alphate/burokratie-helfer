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
import re
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel

from app.config import settings
from app.services.pdf_token import verify_pdf_token

log = logging.getLogger("burokratie.fill_pdf")


def _smart_filename(template_id: str | None, original_filename: str) -> str:
    """
    Build a human-readable download filename.

    Verified template:  <template-name-slug>_<YYYY-MM-DD>.pdf
                        e.g. "jobcenter-but-v1_2026-05-07.pdf"
    Other:              <original-stem>_filled_<YYYY-MM-DD>.pdf
    """
    today = date.today().isoformat()
    if template_id:
        from app.services.form_templates import find_template_by_id
        tmpl = find_template_by_id(template_id)
        if tmpl:
            slug = re.sub(r"[^A-Za-z0-9-]+", "-", tmpl.template_id).strip("-").lower()
            return f"{slug}_{today}.pdf"
    stem = original_filename.rsplit(".", 1)[0] or "form"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)
    return f"{stem}_filled_{today}.pdf"

router = APIRouter(tags=["stateless"])


def expand_logical_fields(template, answers: dict[str, str]) -> dict[str, str]:
    """
    Expand a verified template's logical fields into per-widget writes for the
    AcroForm fill paths. Two mechanisms, both used by KG1:

      RadioGroup — one chosen value → "Yes" on the chosen widget, "Off" on
                   every sibling (Adobe's on/off representation).
      SplitField — one value (e.g. an 11-digit Steuer-ID) → char-sliced across
                   N comb widgets. Non-digits are stripped first; if the cleaned
                   length doesn't match sum(slices) we skip the group rather than
                   write a garbled partial number.

    The logical field_id is popped from the result; only real PDF widget names
    remain. Shared by the 'acroform' (PyPDF) and 'fitz_acroform' branches so the
    two paths can never drift apart.
    """
    expanded = dict(answers)

    # ── Radio groups ──────────────────────────────────────────────────────────
    for rg in list(getattr(template, "get_radio_groups", lambda: [])()):
        chosen = expanded.pop(rg.field_id, None)
        selected_widget = None
        if chosen is not None:
            for value, widget in rg.options:
                if value == chosen:
                    selected_widget = widget
                    break
            if selected_widget is None:
                log.warning(
                    "fill-pdf RADIO_GROUP_VALUE_NOT_IN_OPTIONS field_id=%s value=%r",
                    rg.field_id, chosen,
                )
        for widget_name in rg.widget_names:
            expanded[widget_name] = "Yes" if widget_name == selected_widget else "Off"

    # ── Split fields ──────────────────────────────────────────────────────────
    for sf in list(getattr(template, "get_split_fields", lambda: [])()):
        raw = expanded.pop(sf.field_id, None)
        if raw is None or not str(raw).strip():
            continue  # unanswered / blank → leave every target widget empty
        digits = re.sub(r"\D", "", str(raw))
        expected = sum(sf.slices)
        if len(digits) != expected:
            log.warning(
                "fill-pdf SPLIT_FIELD_LENGTH_MISMATCH field_id=%s got=%d expected=%d",
                sf.field_id, len(digits), expected,
            )
            continue  # refuse to write a partial / wrong-length number
        pos = 0
        for widget_name, n in zip(sf.widget_names, sf.slices):
            expanded[widget_name] = digits[pos:pos + n]
            pos += n

    return expanded


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
    # Phase E/E1 — May be None for tokens signed before E1; treated as
    # "unknown level" → summary fallback allowed, same as Level 3.
    support_level: int | None = token_data.get("support_level")

    log.info(
        "fill-pdf START filename=%s template_id=%s support_level=%s field_count=%d answer_count=%d",
        filename, template_id, support_level, len(field_ids), len(body.answers),
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

    safe_name = _smart_filename(template_id, filename)

    # ── 3a. Verified template → dispatch on template.fill_strategy ──────────
    # Per Hard Rule 7 (Part I): for Level 1 templates, fill errors surface
    # as a clean error, not a silent fallback to a summary or minimal PDF.
    # Phase F/0-B added the "acroform" branch alongside the existing
    # "fitz_overlay" branch so verified templates can use the AcroForm fill
    # path WITHOUT hand-authored WriteSpecs.
    if template_id:
        from app.services.form_templates import find_template_by_id
        template = find_template_by_id(template_id)
        if template:
            template_fill_strategy = getattr(template, "fill_strategy", "fitz_overlay")

            # ── 3a-i. Verified template + fitz_overlay ─────────────────────
            if template_fill_strategy == "fitz_overlay":
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
                    log.critical(
                        "fill-pdf FITZ_OVERLAY_FAILED template_id=%s err=%s",
                        template_id, e,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "We could not fill your form. Please try again, "
                            "or upload a different copy of the document."
                        ),
                    )
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

            # ── 3a-ii. Verified template + acroform fill (Phase F/0-B) ─────
            # Strict mirror of Phase E1's Level 2 policy: the engine writes
            # directly into the source PDF's AcroForm widgets via PyPDFGenerator,
            # but NEVER returns a summary or minimal PDF, and NEVER returns a
            # zero-fill PDF when the user supplied answers. Anything that
            # would violate these rules surfaces as a friendly 500.
            if template_fill_strategy == "acroform":
                import os
                import tempfile
                from app.services.pdf_generator.base import PDFGenerationRequest
                from app.services.pdf_generator.pypdf_generator import PyPDFGenerator

                # Phase F1 + v2 — expand logical fields (radio groups + split
                # fields like the Steuer-ID) into per-widget writes BEFORE
                # handing off to PyPDFGenerator. The logical field_id stays in
                # extracted_field_ids (so the grounding guard above accepts it),
                # but the actual PDF widgets never appear in extracted_field_ids
                # — only the engine knows about them via the template.
                expanded_answers = expand_logical_fields(template, body.answers)

                _generator = PyPDFGenerator()
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
                try:
                    with os.fdopen(tmp_fd, "wb") as f:
                        f.write(pdf_bytes)
                    gen_request = PDFGenerationRequest(
                        template_id=template_id,
                        field_values=expanded_answers,
                        blank_pdf_path=tmp_path,
                        field_labels=body.field_labels,
                    )
                    try:
                        result = await _generator.generate(gen_request)
                    except Exception as e:
                        log.critical(
                            "fill-pdf VERIFIED_ACROFORM_GENERATOR_CRASHED "
                            "template_id=%s err=%s",
                            template_id, e,
                        )
                        raise HTTPException(
                            status_code=500,
                            detail=(
                                "We could not safely fill this PDF. Please try "
                                "another PDF or fill this one manually."
                            ),
                        )
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                if result.warnings:
                    log.warning(
                        "fill-pdf VERIFIED_ACROFORM_WARNINGS template_id=%s: %s",
                        template_id, result.warnings,
                    )

                # Strict invariant 1 — generator MUST have taken the AcroForm
                # path. Summary or minimal output for a verified template is
                # a safety violation.
                if result.strategy != "acroform":
                    log.critical(
                        "fill-pdf VERIFIED_ACROFORM_NON_ACROFORM_OUTPUT "
                        "template_id=%s strategy=%s warnings=%s",
                        template_id, result.strategy, result.warnings,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "We could not safely fill this PDF. Please try "
                            "another PDF or fill this one manually."
                        ),
                    )

                # Strict invariant 2 — zero fields written when the user
                # supplied answers means the widgets did not accept our
                # values. Refuse rather than return an empty form.
                if result.field_count_filled == 0 and len(body.answers) > 0:
                    log.critical(
                        "fill-pdf VERIFIED_ACROFORM_ZERO_FILL "
                        "template_id=%s answers=%d",
                        template_id, len(body.answers),
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "We could not safely fill this PDF. Please try "
                            "another PDF or fill this one manually."
                        ),
                    )

                log.info(
                    "fill-pdf VERIFIED_ACROFORM_DONE template_id=%s filled=%d",
                    template_id, result.field_count_filled,
                )
                return Response(
                    content=result.pdf_bytes,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="{safe_name}"',
                        # Verified-acroform path is still strictly Level 1.
                        # The advertisement uses the precise strategy name so
                        # the frontend can show the right output guarantee.
                        "X-Fill-Strategy": "acroform",
                        "X-Fields-Filled": str(result.field_count_filled),
                        "Access-Control-Expose-Headers":
                            "X-Fill-Strategy,X-Fields-Filled,X-Not-Fillable-Fields",
                    },
                )

            # ── 3a-iii. Verified template + fitz_acroform fill (Phase F6) ──
            # Same strict policy as 3a-ii, but uses PyMuPDF instead of
            # PyPDF to write into the AcroForm widgets. Required for
            # XFA-styled PDFs (e.g. Familienkasse KG1) whose /Btn widgets
            # have no /AP appearance dict — PyPDF can't write to those;
            # fitz can.
            if template_fill_strategy == "fitz_acroform":
                # Same logical-field expansion as the PyPDF branch (radio groups
                # + split fields). Runs BEFORE the fill so the downstream filler
                # only ever sees real per-widget writes.
                expanded_answers = expand_logical_fields(template, body.answers)

                from app.services.pdf_generator.fitz_acroform_fill import (
                    fill_acroform_via_fitz,
                )
                try:
                    result = fill_acroform_via_fitz(pdf_bytes, expanded_answers)
                except Exception as e:
                    log.critical(
                        "fill-pdf VERIFIED_FITZ_ACROFORM_CRASHED "
                        "template_id=%s err=%s",
                        template_id, e,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "We could not safely fill this PDF. Please try "
                            "another PDF or fill this one manually."
                        ),
                    )

                if result.warnings:
                    log.warning(
                        "fill-pdf VERIFIED_FITZ_ACROFORM_WARNINGS "
                        "template_id=%s: %s",
                        template_id, result.warnings,
                    )

                # Strict invariant: zero fields written when the user
                # supplied answers means the widgets did not accept our
                # values. Refuse rather than return an empty form.
                if result.field_count_filled == 0 and len(expanded_answers) > 0:
                    log.critical(
                        "fill-pdf VERIFIED_FITZ_ACROFORM_ZERO_FILL "
                        "template_id=%s answers=%d",
                        template_id, len(expanded_answers),
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=(
                            "We could not safely fill this PDF. Please try "
                            "another PDF or fill this one manually."
                        ),
                    )

                log.info(
                    "fill-pdf VERIFIED_FITZ_ACROFORM_DONE template_id=%s filled=%d",
                    template_id, result.field_count_filled,
                )
                return Response(
                    content=result.pdf_bytes,
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'attachment; filename="{safe_name}"',
                        # Same advertisement as the PyPDF acroform path —
                        # both write into the original PDF's AcroForm
                        # widgets. The frontend doesn't need to care which
                        # backend was used.
                        "X-Fill-Strategy": "acroform",
                        "X-Fields-Filled": str(result.field_count_filled),
                        "Access-Control-Expose-Headers":
                            "X-Fill-Strategy,X-Fields-Filled,X-Not-Fillable-Fields",
                    },
                )

            # Defence in depth: an unknown strategy on a Level 1 template is
            # a config bug. Refuse rather than silently fall through to the
            # legacy AcroForm/summary path below.
            log.critical(
                "fill-pdf UNKNOWN_FILL_STRATEGY template_id=%s strategy=%s",
                template_id, template_fill_strategy,
            )
            raise HTTPException(
                status_code=500,
                detail=(
                    "We could not safely fill this PDF. Please try "
                    "another PDF or fill this one manually."
                ),
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
        try:
            result = await _generator.generate(gen_request)
        except Exception as e:
            # Phase E/E1 — Level 2 must NEVER silently degrade to a summary.
            # Anything that crashes the generator surfaces as a clean error.
            log.critical(
                "fill-pdf PYPDF_GENERATOR_CRASHED level=%s err=%s",
                support_level, e,
            )
            if support_level == 2:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        "We could not safely fill this PDF. Please try another "
                        "PDF or fill this one manually."
                    ),
                )
            # Levels 3/None: re-raise as a generic 500; the client-side
            # friendlyError() maps it to a user-safe message.
            raise HTTPException(
                status_code=500,
                detail=(
                    "Something went wrong while preparing your form. "
                    "Please try again or upload a different copy of the PDF."
                ),
            )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.warnings:
        log.warning("fill-pdf WARNINGS filename=%s: %s", filename, result.warnings)

    # Phase E/E1 — Level 2 invariant: the generator MUST have produced an
    # AcroForm-filled output. If it returned a summary or a minimal placeholder,
    # the user would receive a "PDF" that is NOT their original form filled in.
    # Refuse instead of silently downgrading.
    if support_level == 2 and result.strategy != "acroform":
        log.critical(
            "fill-pdf LEVEL_2_NON_ACROFORM_OUTPUT strategy=%s filename=%s warnings=%s",
            result.strategy, filename, result.warnings,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "We could not safely fill this PDF. Please try another "
                "PDF or fill this one manually."
            ),
        )
    # Phase E/E1 — Same invariant for the field-count: an AcroForm fill that
    # writes zero fields while the user provided answers means the widgets
    # didn't accept our values. Refuse rather than return an empty PDF.
    if (
        support_level == 2
        and result.strategy == "acroform"
        and result.field_count_filled == 0
        and len(body.answers) > 0
    ):
        log.critical(
            "fill-pdf LEVEL_2_ZERO_FILL filename=%s answers=%d",
            filename, len(body.answers),
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "We could not safely fill this PDF. Please try another "
                "PDF or fill this one manually."
            ),
        )

    log.info(
        "fill-pdf LEGACY_DONE filename=%s strategy=%s filled_fields=%d output_kb=%d",
        filename, result.strategy, result.field_count_filled, len(result.pdf_bytes) // 1024,
    )

    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            # Phase E/E1 — Header now reports the EXACT strategy taken so the
            # frontend can show the right output-guarantee message.
            "X-Fill-Strategy": result.strategy,
            "X-Fields-Filled": str(result.field_count_filled),
            "Access-Control-Expose-Headers": "X-Fill-Strategy,X-Fields-Filled,X-Not-Fillable-Fields",
        },
    )
