"""
PDF generation using pypdf for AcroForm field filling.

For AcroForm PDFs:   fills fields in-place and returns the filled PDF.
For flat PDFs:       generates a formatted answer summary PDF using reportlab.
                     The summary lists every answer with its original form label,
                     a checkbox symbol for yes/no answers, and a disclaimer.

Detection: if reader.get_fields() returns an empty dict, the PDF has no AcroForm
and we skip to the overlay immediately — no silent no-op.
"""
import io
from pathlib import Path

from app.services.pdf_generator.base import PDFGeneratorService, PDFGenerationRequest, PDFGenerationResult


class PyPDFGenerator(PDFGeneratorService):
    async def generate(self, request: PDFGenerationRequest) -> PDFGenerationResult:
        blank_path = Path(request.blank_pdf_path)
        warnings: list[str] = []

        if blank_path.exists():
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(blank_path))
                acroform_fields = reader.get_fields() or {}

                if acroform_fields:
                    # AcroForm PDF — fill fields in-place
                    return await self._fill_acroform(request, warnings, reader)
                else:
                    # Flat / scanned PDF — no AcroForm fields to fill
                    warnings.append(
                        "PDF has no AcroForm fields — generating formatted answer summary."
                    )
            except Exception as e:
                warnings.append(f"PDF inspection failed ({e}), falling back to summary.")

        return await self._overlay_fallback(request, warnings)

    async def _fill_acroform(
        self,
        request: PDFGenerationRequest,
        warnings: list[str],
        reader,  # already-opened PdfReader, passed to avoid re-reading
    ) -> PDFGenerationResult:
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.append(reader)

        # Classify each field so we can format values correctly
        radio_fields:    set[str] = set()
        checkbox_fields: set[str] = set()
        _FF_RADIO   = 1 << 15
        _FF_PUSHBTN = 1 << 16
        try:
            for fname, fobj in (reader.get_fields() or {}).items():
                ft = str(fobj.get("/FT", "/Tx"))
                ff = int(str(fobj.get("/Ff", "0")).split(".")[0] or "0")
                if ft == "/Btn" and not (ff & _FF_PUSHBTN):
                    clean = fname.lstrip("/").strip()
                    if ff & _FF_RADIO:
                        radio_fields.add(clean)
                    else:
                        checkbox_fields.add(clean)
        except Exception as e:
            warnings.append(f"Field-type detection warning: {e}")

        filled = 0
        for page in writer.pages:
            try:
                text_values = {
                    k: v for k, v in request.field_values.items()
                    if k not in radio_fields and k not in checkbox_fields
                }
                if text_values:
                    writer.update_page_form_field_values(page, text_values, auto_regenerate=False)

                radio_values = {
                    k: v for k, v in request.field_values.items()
                    if k in radio_fields and v
                }
                if radio_values:
                    writer.update_page_form_field_values(page, radio_values, auto_regenerate=False)

                for k, v in request.field_values.items():
                    if k in checkbox_fields:
                        normalised = "Yes" if str(v).lower() in (
                            "yes", "ja", "true", "1", "x", "on"
                        ) else "Off"
                        try:
                            writer.update_page_form_field_values(
                                page, {k: normalised}, auto_regenerate=False,
                            )
                        except Exception as e:
                            warnings.append(f"Checkbox '{k}': {e}")

                filled = len(request.field_values)
            except Exception as e:
                warnings.append(f"Page field update warning: {e}")

        writer.add_metadata({"/Producer": "Bürokratie-Helfer MVP 1.0"})
        buffer = io.BytesIO()
        writer.write(buffer)
        return PDFGenerationResult(
            pdf_bytes=buffer.getvalue(),
            field_count_filled=filled,
            warnings=warnings,
        )

    async def _overlay_fallback(
        self, request: PDFGenerationRequest, warnings: list[str]
    ) -> PDFGenerationResult:
        """
        Formatted answer summary PDF using reportlab.

        When the original is a flat PDF (no AcroForm), we cannot fill it
        programmatically. Instead we generate a clean summary document the user
        can bring alongside the original form, or use as a reference when
        filling it by hand.

        field_labels maps field_id → human-readable label.
        When provided, labels are shown instead of raw field_ids.
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            warnings.append("reportlab not installed — returning minimal PDF.")
            return PDFGenerationResult(
                pdf_bytes=b"%PDF-1.4",
                field_count_filled=0,
                warnings=warnings,
            )

        labels = request.field_labels  # field_id → label (may be empty)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        MARGIN = 50
        LINE = 18
        y = height - MARGIN

        def new_page():
            nonlocal y
            c.showPage()
            y = height - MARGIN

        def draw_header():
            nonlocal y
            c.setFillColorRGB(0.13, 0.37, 0.71)
            c.rect(0, height - 70, width, 70, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(MARGIN, height - 30, "Bürokratie-Helfer — Ausgefüllte Angaben")
            c.setFont("Helvetica", 9)
            c.drawString(MARGIN, height - 50, "Ihre Antworten für das Formular / Your answers for the form")
            c.setFillColorRGB(0, 0, 0)
            y = height - 85

        draw_header()

        # Disclaimer banner
        c.setFillColorRGB(1.0, 0.95, 0.8)
        c.rect(MARGIN, y - 28, width - 2 * MARGIN, 28, fill=1, stroke=0)
        c.setFillColorRGB(0.5, 0.3, 0)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN + 6, y - 10,
            "Dieses Dokument ist kein offizielles Formular. Bitte tragen Sie die Angaben in das Originalformular ein.")
        c.drawString(MARGIN + 6, y - 20,
            "This is not an official form. Please transfer these answers to the original document.")
        c.setFillColorRGB(0, 0, 0)
        y -= 40

        # Answers
        c.setFont("Helvetica", 9)
        filled = 0
        for field_id, value in request.field_values.items():
            if y < 80:
                new_page()
                draw_header()

            label = labels.get(field_id, field_id)
            is_bool = str(value).lower() in ("yes", "no", "ja", "nein", "true", "false")

            # Row background alternation
            row_idx = filled % 2
            if row_idx == 0:
                c.setFillColorRGB(0.97, 0.97, 0.97)
                c.rect(MARGIN, y - 14, width - 2 * MARGIN, LINE, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)

            # Label (left column, 55% of row width)
            col_split = MARGIN + (width - 2 * MARGIN) * 0.58
            c.setFont("Helvetica", 9)
            label_display = label[:60] + "…" if len(label) > 60 else label
            c.drawString(MARGIN + 4, y - 10, label_display)

            # Value (right column)
            if is_bool:
                checked = str(value).lower() in ("yes", "ja", "true", "1")
                symbol = "☑" if checked else "☐"
                try:
                    c.setFont("Helvetica", 12)
                    c.drawString(col_split + 4, y - 11, symbol)
                except Exception:
                    c.setFont("Helvetica", 9)
                    c.drawString(col_split + 4, y - 10, "YES" if checked else "NO")
                c.setFont("Helvetica", 9)
                val_display = ("Ja / Yes" if checked else "Nein / No")
                c.drawString(col_split + 20, y - 10, val_display)
            else:
                c.setFont("Helvetica-Bold", 9)
                val_str = str(value)
                val_display = val_str[:50] + "…" if len(val_str) > 50 else val_str
                c.drawString(col_split + 4, y - 10, val_display)
                c.setFont("Helvetica", 9)

            y -= LINE
            filled += 1

        # Footer
        if y < 60:
            new_page()
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.setFont("Helvetica", 7)
        c.drawString(MARGIN, 30,
            f"Bürokratie-Helfer · {filled} Felder / fields · burokratie-helfer.vercel.app")

        c.save()
        return PDFGenerationResult(
            pdf_bytes=buffer.getvalue(),
            field_count_filled=filled,
            warnings=warnings,
        )


class PDFGeneratorFactory:
    @staticmethod
    def create(backend: str = "pypdf") -> PDFGeneratorService:
        if backend == "pypdf":
            return PyPDFGenerator()
        raise ValueError(f"Unknown PDF generator backend: {backend}. Supported: pypdf")
