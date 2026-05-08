"""
Stage 4A — Tesseract diagnostic OCR provider.

Renders each PDF page to a PIL Image via PyMuPDF, runs `pytesseract.image_to_data`
in `deu+eng` language mode, returns an OCRDiagnostic with per-block bbox +
confidence + the assembled full text.

Failure modes (all return a valid OCRDiagnostic, never raise):

    Tesseract binary missing      → make_unavailable()
    German+English lang pack
      missing                     → fall back to whichever languages ARE
                                    installed; record warning in
                                    technical_message
    PyMuPDF can't open PDF        → make_failed(...)
    Unhandled exception           → make_failed(...)

Stage 4A explicitly does NOT:
    - generate FieldDefinitions
    - call an LLM
    - mutate pdf_bytes
    - touch any other pipeline state

Performance note: Tesseract is slow (10–30s per page on typical hardware).
We cap at MAX_OCR_PAGES pages — anything beyond is dropped silently from
OCR analysis (the remaining pages still appear in page_count).
"""
from __future__ import annotations

import io
import logging
from typing import Optional

from app.services.ocr.diagnostic import (
    LOW_CONFIDENCE_THRESHOLD,
    OCRDiagnostic,
    OCRDiagnosticProvider,
    OCRPageQuality,
    OCRPageResult,
    OCRTextBlock,
    STATUS_LOW_CONFIDENCE,
    STATUS_NO_TEXT_FOUND,
    STATUS_READABLE,
    make_failed,
    make_unavailable,
)


log = logging.getLogger("burokratie.ocr_tesseract")

# Cap to avoid runaway costs / timeouts on adversarial uploads.
# Stage 4A is diagnostic-only — 5 pages is plenty for fingerprint signal.
MAX_OCR_PAGES = 5

# Render DPI — higher = sharper but slower. 200 dpi is the standard
# Tesseract sweet-spot for 12pt body text.
RENDER_DPI = 200

# Languages we ask Tesseract to try. Falls back gracefully when not all
# packs are installed.
PREFERRED_LANGUAGES = "deu+eng"

# Per-image preflight cap to bail out on obviously-broken bitmaps.
MIN_PAGE_PIXELS = 100


class TesseractProvider(OCRDiagnosticProvider):
    """Default Stage 4A provider. Free, local, GDPR-clean."""

    def name(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        """
        Cheap pre-flight: does pytesseract exist AND can we call
        get_tesseract_version() without TesseractNotFoundError?
        Caches the result on the instance so repeat checks are free.
        """
        cached = getattr(self, "_available_cache", None)
        if cached is not None:
            return cached
        try:
            import pytesseract
            try:
                pytesseract.get_tesseract_version()
                self._available_cache = True
            except Exception as e:
                log.info("Tesseract not available: %s", e)
                self._available_cache = False
        except ImportError:
            log.info("pytesseract not installed in this environment")
            self._available_cache = False
        return self._available_cache

    def diagnose(self, pdf_bytes: bytes) -> OCRDiagnostic:
        if not self.is_available():
            return make_unavailable(provider_name=self.name())

        try:
            return self._run(pdf_bytes)
        except Exception as e:
            # Catch-all — never let an OCR failure crash the upload flow.
            log.exception("Tesseract diagnose() raised")
            return make_failed(
                provider_name=self.name(),
                technical_message=f"{type(e).__name__}: {e}",
            )

    # ── Internals ────────────────────────────────────────────────────────────

    def _run(self, pdf_bytes: bytes) -> OCRDiagnostic:
        """Main path. Assumes is_available() has returned True."""
        import fitz       # PyMuPDF — already a backend dependency
        import pytesseract
        from PIL import Image

        # Decide language string. If `deu` is missing, try with whatever
        # packs ARE installed. Tesseract raises if no requested lang exists.
        lang, lang_warning = self._resolve_language(pytesseract)

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            return make_failed(self.name(), f"fitz.open failed: {type(e).__name__}: {e}")

        page_count_total = doc.page_count
        # Render at most MAX_OCR_PAGES pages.
        pages_to_ocr = min(page_count_total, MAX_OCR_PAGES)

        per_page_results: list[OCRPageResult] = []
        all_blocks: list[OCRTextBlock] = []
        detected_lang_set: set[str] = set()

        try:
            for page_index in range(pages_to_ocr):
                page = doc[page_index]
                page_num = page_index + 1
                # Render to a PIL Image at RENDER_DPI
                zoom = RENDER_DPI / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                if pix.width < MIN_PAGE_PIXELS or pix.height < MIN_PAGE_PIXELS:
                    # Skip pages too tiny to be real
                    per_page_results.append(self._empty_page_result(
                        page_num, pix.width, pix.height,
                        issue=f"page-image too small ({pix.width}x{pix.height})",
                    ))
                    continue

                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # image_to_data returns dict-of-lists with per-word bbox + conf
                try:
                    data = pytesseract.image_to_data(
                        img,
                        lang=lang,
                        output_type=pytesseract.Output.DICT,
                    )
                except Exception as e:
                    per_page_results.append(self._empty_page_result(
                        page_num, pix.width, pix.height,
                        issue=f"pytesseract failed on page: {type(e).__name__}",
                    ))
                    continue

                blocks = self._parse_tesseract_output(data, page_num)
                all_blocks.extend(blocks)

                avg_conf = (
                    sum(b.confidence for b in blocks) / len(blocks)
                    if blocks else 0.0
                )
                quality = OCRPageQuality(
                    page=page_num,
                    width=pix.width,
                    height=pix.height,
                    dpi_estimate=RENDER_DPI,
                    text_block_count=len(blocks),
                    average_confidence=round(avg_conf, 4),
                    readable=(len(blocks) > 0 and avg_conf >= LOW_CONFIDENCE_THRESHOLD),
                    issues=[],
                )
                per_page_results.append(OCRPageResult(
                    page=page_num, blocks=blocks, quality=quality,
                ))

            # Pages beyond the cap: surface them as empty page results so the
            # frontend can show "we processed N of M pages" honestly.
            for page_index in range(pages_to_ocr, page_count_total):
                page_num = page_index + 1
                per_page_results.append(self._empty_page_result(
                    page_num, 0, 0,
                    issue=f"page exceeded OCR cap ({MAX_OCR_PAGES})",
                ))
        finally:
            doc.close()

        # Aggregates
        if all_blocks:
            average_confidence = round(
                sum(b.confidence for b in all_blocks) / len(all_blocks), 4
            )
        else:
            average_confidence = 0.0

        full_text = "\n".join(b.text for b in all_blocks if b.text.strip())
        readable_pages = sum(1 for p in per_page_results if p.quality.readable)
        unreadable_pages = page_count_total - readable_pages

        # Status decision — first-match wins:
        #   no blocks at all       → no_text_found
        #   blocks but avg < thr   → low_confidence
        #   else                   → readable
        if not all_blocks:
            status = STATUS_NO_TEXT_FOUND
            user_msg = (
                "We could not read text from this image. Please upload a "
                "digital PDF or retake the photo."
            )
        elif average_confidence < LOW_CONFIDENCE_THRESHOLD:
            status = STATUS_LOW_CONFIDENCE
            user_msg = (
                "The scan is hard to read. Try again with better lighting, "
                "a flat page, and no shadows."
            )
        else:
            status = STATUS_READABLE
            user_msg = (
                "We can read some text from this scan, but OCR form filling "
                "is not enabled yet. This scan may be usable in a future step."
            )

        # Determine detected languages: Tesseract doesn't reliably report
        # per-block language, so we report what we ASKED for.
        detected_languages = [c for c in lang.split("+") if c]

        tech = (
            f"tesseract pages={pages_to_ocr}/{page_count_total} "
            f"avg_conf={average_confidence:.2f} blocks={len(all_blocks)} "
            f"lang={lang}"
        )
        if lang_warning:
            tech += f" lang_warning={lang_warning!r}"

        return OCRDiagnostic(
            provider=self.name(),
            page_count=page_count_total,
            pages=per_page_results,
            full_text=full_text,
            average_confidence=average_confidence,
            detected_languages=detected_languages,
            readable_pages=readable_pages,
            unreadable_pages=unreadable_pages,
            diagnostic_status=status,
            user_message=user_msg,
            technical_message=tech,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _resolve_language(self, pytesseract) -> tuple[str, Optional[str]]:
        """
        Return (lang_string, warning_or_None). Tries PREFERRED_LANGUAGES
        ('deu+eng'); falls back to whichever components ARE installed; if
        neither, falls back to '' (Tesseract default = English-ish).
        """
        try:
            installed = set(pytesseract.get_languages(config="") or [])
        except Exception:
            return PREFERRED_LANGUAGES, None  # let it fail downstream if so
        wanted = [c for c in PREFERRED_LANGUAGES.split("+") if c]
        present = [c for c in wanted if c in installed]
        if present == wanted:
            return PREFERRED_LANGUAGES, None
        if present:
            return "+".join(present), f"lang pack(s) missing: {set(wanted) - set(present)}"
        # Nothing matched — let Tesseract use its default and warn
        return "eng" if "eng" in installed else "", (
            f"no requested lang packs installed ({set(wanted)}); installed={installed}"
        )

    def _parse_tesseract_output(self, data: dict, page_num: int) -> list[OCRTextBlock]:
        """
        pytesseract image_to_data dict has parallel arrays:
            text[]  conf[]  left[]  top[]  width[]  height[]  level[]
        Filter to non-empty words with conf >= 0 (Tesseract uses -1 for
        non-text "container" rows).
        """
        blocks: list[OCRTextBlock] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            try:
                conf_raw = float(data["conf"][i])
            except (ValueError, TypeError):
                conf_raw = -1.0
            if conf_raw < 0:
                continue
            x = float(data["left"][i])
            y = float(data["top"][i])
            w = float(data["width"][i])
            h = float(data["height"][i])
            blocks.append(OCRTextBlock(
                text=text,
                page=page_num,
                bbox=[x, y, x + w, y + h],
                # Tesseract reports confidence as a 0–100 integer; normalize.
                confidence=round(conf_raw / 100.0, 4),
            ))
        return blocks

    def _empty_page_result(
        self, page_num: int, w: int, h: int, issue: str,
    ) -> OCRPageResult:
        quality = OCRPageQuality(
            page=page_num,
            width=w,
            height=h,
            dpi_estimate=RENDER_DPI,
            text_block_count=0,
            average_confidence=0.0,
            readable=False,
            issues=[issue],
        )
        return OCRPageResult(page=page_num, blocks=[], quality=quality)


def get_default_provider() -> OCRDiagnosticProvider:
    """
    Single entry point for the routing layer. Always returns SOMETHING —
    the provider's is_available() handles the "engine missing" case.
    """
    return TesseractProvider()
