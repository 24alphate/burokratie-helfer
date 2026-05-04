"""
PDF generation using pypdf for AcroForm field filling.
Falls back to reportlab text overlay when no AcroForm fields are present.
"""
import io
from pathlib import Path
from typing import Optional

from app.services.pdf_generator.base import PDFGeneratorService, PDFGenerationRequest, PDFGenerationResult


class PyPDFGenerator(PDFGeneratorService):
    async def generate(self, request: PDFGenerationRequest) -> PDFGenerationResult:
        blank_path = Path(request.blank_pdf_path)
        warnings: list[str] = []

        if blank_path.exists():
            try:
                result = await self._fill_acroform(request, warnings)
                return result
            except Exception as e:
                warnings.append(f"AcroForm fill failed ({e}), falling back to overlay.")

        return await self._overlay_fallback(request, warnings)

    async def _fill_acroform(
        self, request: PDFGenerationRequest, warnings: list[str]
    ) -> PDFGenerationResult:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(request.blank_pdf_path)
        writer = PdfWriter()
        writer.append(reader)

        filled = 0
        for page in writer.pages:
            try:
                writer.update_page_form_field_values(
                    page,
                    request.field_values,
                    auto_regenerate=False,
                )
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
        Creates a simple text-only PDF listing the field values.
        Used when no blank PDF template exists (e.g. during testing).
        """
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4

        warnings.append("No blank PDF template found — generating text summary PDF.")
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 50, "Bürokratie-Helfer — Ausgefüllte Angaben")
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 70, "Hinweis: Dies ist kein offizielles Formular. Bitte beim Jobcenter einreichen.")

        y = height - 110
        c.setFont("Helvetica", 11)
        for field_name, value in request.field_values.items():
            if y < 60:
                c.showPage()
                y = height - 50
            c.drawString(50, y, f"{field_name}:")
            c.drawString(250, y, str(value))
            y -= 20

        c.save()
        return PDFGenerationResult(
            pdf_bytes=buffer.getvalue(),
            field_count_filled=len(request.field_values),
            warnings=warnings,
        )


class PDFGeneratorFactory:
    @staticmethod
    def create(backend: str = "pypdf") -> PDFGeneratorService:
        if backend == "pypdf":
            return PyPDFGenerator()
        raise ValueError(f"Unknown PDF generator backend: {backend}. Supported: pypdf")
