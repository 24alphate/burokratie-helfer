"""
Generates a blank ALG II form PDF with AcroForm text fields matching pdf_field_map.
Run once: python create_blank_pdf.py
Output: static_pdfs/alg2_blank.pdf
"""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, black

OUTPUT = Path(__file__).parent / "static_pdfs" / "alg2_blank.pdf"

# (label_text, field_name, x, y, width, height)
FIELDS = [
    # Personal data
    ("Vorname (First name)", "Vorname", 160, 720, 200, 18),
    ("Familienname (Family name)", "Familienname", 160, 695, 200, 18),
    ("Geburtsdatum (Date of birth)", "Geburtsdatum", 160, 670, 120, 18),
    ("Staatsangehörigkeit (Nationality)", "Staatsangehörigkeit", 160, 645, 180, 18),
    # Address
    ("Straße und Hausnummer (Street)", "StraßeHausnummer", 160, 610, 220, 18),
    ("Postleitzahl (Postal code)", "Postleitzahl", 160, 585, 80, 18),
    ("Ort (City)", "Ort", 260, 585, 140, 18),
    # Employment
    ("Beschäftigungsstatus (Employment)", "Beschäftigungsstatus", 160, 550, 200, 18),
    ("Monatliches Einkommen (Monthly income €)", "MonatlichesEinkommen", 160, 525, 120, 18),
    # Partner
    ("Lebenspartner vorhanden? (Partner?)", "LebenspartnerVorhanden", 160, 490, 60, 18),
    ("Vorname Partner (Partner first name)", "PartnerVorname", 160, 465, 180, 18),
    ("Familienname Partner (Partner family name)", "PartnerFamilienname", 160, 440, 180, 18),
    # Children & bank
    ("Anzahl Kinder unter 18 (Children under 18)", "AnzahlKinder", 160, 405, 60, 18),
    ("IBAN", "IBAN", 160, 380, 220, 18),
    # Signature
    ("Datum (Date)", "Datum", 160, 330, 120, 18),
]

LIGHT_BLUE = HexColor("#dbeafe")
BORDER_BLUE = HexColor("#3b82f6")
LABEL_GRAY = HexColor("#374151")
HEADER_BLUE = HexColor("#1e40af")


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=A4)
    width, height = A4
    form = c.acroForm

    # Header
    c.setFillColor(HEADER_BLUE)
    c.rect(40, height - 80, width - 80, 55, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(55, height - 45, "Antrag auf Arbeitslosengeld II (ALG II)")
    c.setFont("Helvetica", 10)
    c.drawString(55, height - 65, "Jobcenter — Bitte alle Felder ausfüllen / Please complete all fields")

    # Disclaimer
    c.setFillColor(HexColor("#92400e"))
    c.setFont("Helvetica", 8)
    c.drawString(40, height - 100,
        "⚠  Dies ist eine Ausfüllhilfe. Bitte beim Jobcenter als Originalformular einreichen.")

    # Section: Persönliche Angaben
    _section_header(c, "Persönliche Angaben / Personal Information", 40, 740, width - 80)

    # Draw all fields
    for label, field_name, x, y, w, h in FIELDS:
        # Label
        c.setFillColor(LABEL_GRAY)
        c.setFont("Helvetica", 8)
        c.drawString(40, y + 4, label + ":")

        # AcroForm text field
        form.textfield(
            name=field_name,
            tooltip=label,
            x=x,
            y=y,
            width=w,
            height=h,
            fontName="Helvetica",
            fontSize=10,
            borderColor=BORDER_BLUE,
            fillColor=LIGHT_BLUE,
            textColor=black,
            borderWidth=1,
            forceBorder=True,
        )

    # Signature line
    c.setStrokeColor(LABEL_GRAY)
    c.setLineWidth(0.5)
    c.line(40, 310, 260, 310)
    c.setFillColor(LABEL_GRAY)
    c.setFont("Helvetica", 8)
    c.drawString(40, 298, "Unterschrift / Signature")

    # Section dividers
    _section_header(c, "Anschrift / Address", 40, 630, width - 80)
    _section_header(c, "Beschäftigung / Employment", 40, 575, width - 80)
    _section_header(c, "Lebenspartner / Partner", 40, 515, width - 80)
    _section_header(c, "Haushalt & Bankverbindung / Household & Bank", 40, 430, width - 80)
    _section_header(c, "Erklärung / Declaration", 40, 350, width - 80)

    c.setFillColor(LABEL_GRAY)
    c.setFont("Helvetica", 7)
    c.drawString(40, 280,
        "Ich versichere, dass meine Angaben vollständig und wahrheitsgemäß sind. / "
        "I confirm that my information is complete and truthful.")

    # Footer
    c.setFillColor(HexColor("#6b7280"))
    c.setFont("Helvetica", 7)
    c.drawString(40, 20, "Erstellt mit Bürokratie-Helfer (Ausfüllhilfe — kein amtliches Formular) · Form assistance only, not legal advice")

    c.save()
    print(f"Blank PDF created: {OUTPUT}")


def _section_header(c, text, x, y, w):
    c.setFillColor(HexColor("#eff6ff"))
    c.rect(x, y - 4, w, 16, fill=1, stroke=0)
    c.setFillColor(HEADER_BLUE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 4, y + 2, text)


if __name__ == "__main__":
    build()
