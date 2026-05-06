"""
Verified field map for the Jobcenter "Bildung und Teilhabe" (BuT) application form.

This is the standard German federal form for educational and social participation
benefits (§ 28 SGB II / § 34 SGB XII). It is used across Jobcenter offices
including Landkreis Rostock.

Fingerprint
-----------
The form always contains all three of these strings:
  "Bildung und Teilhabe"
  "Persönliche Angaben"
  "Beantragte Leistung"

And at least one section identifier:
  "Schülerbeförderung" | "Lernförderung" | "Mittagessen"

Field map
---------
All fields have confidence=1.0 and source="verified_template".
Signature fields have confidence=0.5 so they are excluded from the question flow
(show_question=False via the confidence gate) — the user signs the printed PDF.

Page numbers are approximate (vary by print version) but preserved for ordering.
"""
from __future__ import annotations

from app.services.form_templates import VerifiedTemplate


_REQUIRED = [
    "bildung und teilhabe",
    "persönliche angaben",
    "beantragte leistung",
]

_SECTION_MARKERS = [
    "schülerbeförderung",
    "lernförderung",
    "mittagessen",
    "klassenfahrt",
    "ausflüge",
]


class JobcenterButTemplate(VerifiedTemplate):
    template_id = "jobcenter_but_v1"
    name = "Jobcenter — Antrag auf Leistungen für Bildung und Teilhabe"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        required_ok = all(s in lo for s in _REQUIRED)
        section_ok  = any(s in lo for s in _SECTION_MARKERS)
        return required_ok and section_ok

    def get_field_map(self) -> list:
        from app.services.pdf_pipeline import FieldMapEntry

        def f(field_id, label, ftype, page, opts=None, conf=1.0, src_text=None):
            return FieldMapEntry(
                field_id=field_id,
                original_label=label,
                field_type=ftype,
                source_page=page,
                options=opts or [],
                current_value="",
                confidence=conf,
                source="verified_template",
                source_text=src_text or label,
                reason="pdf_field",
            )

        return [
            # ── 1. Persönliche Angaben (Antragsteller/in) ─────────────────────
            f("applicant_name_vorname",
              "Name, Vorname (Antragsteller/in)",
              "text", 1,
              src_text="Name, Vorname"),

            f("applicant_postanschrift",
              "Postanschrift (Straße, Hausnummer, PLZ, Ort)",
              "text", 1,
              src_text="Postanschrift"),

            f("bedarfsgemeinschaft_nummer",
              "Nummer der Bedarfsgemeinschaft",
              "text", 1,
              src_text="Nummer der Bedarfsgemeinschaft"),

            f("tag_der_antragstellung",
              "Tag der Antragstellung",
              "date", 1,
              src_text="Tag der Antragstellung"),

            # Current benefit type — checkboxes (§ 28 SGB II / § 34 SGB XII etc.)
            f("benefit_sgb_ii",
              "Ich beziehe Leistungen nach SGB II",
              "checkbox", 1,
              src_text="Leistungen nach dem SGB II"),

            f("benefit_sgb_xii",
              "Ich beziehe Leistungen nach SGB XII",
              "checkbox", 1,
              src_text="Leistungen nach dem SGB XII"),

            f("benefit_kinderzuschlag",
              "Ich beziehe Kinderzuschlag (BKGG)",
              "checkbox", 1,
              src_text="Kinderzuschlag nach dem BKGG"),

            f("benefit_wohngeld",
              "Ich beziehe Wohngeld (WoGG)",
              "checkbox", 1,
              src_text="Wohngeld nach dem WoGG"),

            f("benefit_asylbewerberleistungsgesetz",
              "Ich beziehe Leistungen nach dem Asylbewerberleistungsgesetz",
              "checkbox", 1,
              src_text="Leistungen nach dem Asylbewerberleistungsgesetz"),

            f("benefit_sonstige",
              "Sonstige Leistungen (bitte angeben)",
              "checkbox", 1,
              src_text="Sonstige"),

            f("bg_nummer",
              "BG-Nummer / Aktenzeichen der bewilligten Leistung",
              "text", 1,
              src_text="BG-Nummer / Aktenzeichen"),

            f("zustaendiger_standort",
              "Zuständiger Standort / Jobcenter-Stelle",
              "text", 1,
              src_text="Zuständiger Standort"),

            # ── 2. Kind / Jugendliche/r ───────────────────────────────────────
            f("child_name_vorname_geburtsdatum",
              "Name, Vorname, Geburtsdatum des Kindes / Jugendlichen",
              "text", 1,
              src_text="Name, Vorname, Geburtsdatum des Kindes"),

            f("institution_name",
              "Name der Schule / Kita / Einrichtung",
              "text", 1,
              src_text="Name der Schule / Kindertagesstätte / Einrichtung"),

            f("institution_address",
              "Anschrift der Schule / Kita / Einrichtung",
              "text", 1,
              src_text="Anschrift der Schule / Kindertagesstätte"),

            # ── 3. Beantragte Leistung (checkboxes A–F) ───────────────────────
            f("leistung_a_ausflug",
              "A: Eintägige Ausflüge von Schule / Kita",
              "checkbox", 1,
              src_text="A Eintägige Ausflüge von Schulen und Kindertageseinrichtungen"),

            f("leistung_b_klassenfahrt",
              "B: Mehrtägige Klassenfahrten / Fahrten der Kita",
              "checkbox", 1,
              src_text="B Mehrtägige Klassenfahrten und Fahrten der Kindertageseinrichtungen"),

            f("leistung_c_schuelerbefoerderung",
              "C: Schülerbeförderung",
              "checkbox", 1,
              src_text="C Schülerbeförderung"),

            f("leistung_d_lernfoerderung",
              "D: Lernförderung",
              "checkbox", 1,
              src_text="D Lernförderung"),

            f("leistung_e_mittagessen",
              "E: Gemeinschaftliches Mittagessen (Schule / Kita / Hort)",
              "checkbox", 1,
              src_text="E Gemeinschaftliches Mittagessen"),

            f("leistung_f_soziale_teilhabe",
              "F: Soziale und kulturelle Teilhabe",
              "checkbox", 1,
              src_text="F Soziale und kulturelle Teilhabe"),

            # ── 3.C Schülerbeförderung (transport details) ───────────────────
            f("transport_cost_period",
              "Kosten der Beförderung (monatlich / vierteljährlich / jährlich)",
              "text", 2,
              src_text="Kosten der Beförderung monatlich / vierteljährlich / jährlich"),

            f("transport_public_cost_eur",
              "Kosten öffentliche Verkehrsmittel (EUR)",
              "number", 2,
              src_text="Kosten für öffentliche Verkehrsmittel"),

            f("transport_private_cost_eur",
              "Kosten private Beförderung / Kraftfahrzeug (EUR)",
              "number", 2,
              src_text="Kosten für private Beförderung (Kraftfahrzeug)"),

            f("transport_distance_km",
              "Einfache Strecke in km",
              "number", 2,
              src_text="Einfache Strecke in km"),

            # ── 3.E Mittagessen (lunch details) ──────────────────────────────
            f("essen_anbieter",
              "Name des Essenanbieters",
              "text", 2,
              src_text="Name des Essenanbieters"),

            f("lunch_school_hort",
              "Mittagessen in Schule oder Hort",
              "checkbox", 2,
              src_text="in einer Schule oder einem Hort"),

            f("lunch_kita_kindertagespflege",
              "Mittagessen in Kita oder Kindertagespflege",
              "checkbox", 2,
              src_text="in einer Kindertageseinrichtung oder Kindertagespflege"),

            f("lunch_sonstige_angaben",
              "Sonstige Angaben zum Mittagessen",
              "text", 2,
              src_text="Sonstige Angaben"),

            # ── Declarations / Signature ──────────────────────────────────────
            f("consent_direct_settlement",
              "Einverständnis: Jobcenter rechnet direkt mit Leistungsanbieter ab",
              "checkbox", 2,
              src_text="Ich bin damit einverstanden, dass das Jobcenter die Leistung direkt mit dem Leistungsanbieter abrechnet"),

            f("ort_datum_antragsteller",
              "Ort, Datum (Antragsteller/in)",
              "text", 2,
              src_text="Ort, Datum"),

            # Signatures: confidence < 0.70 → show_question=False (user signs printed PDF)
            f("signature_antragsteller",
              "Unterschrift (Antragsteller/in)",
              "signature", 2,
              conf=0.5,
              src_text="Unterschrift der antragstellenden Person"),

            f("ort_datum_vertreter",
              "Ort, Datum (gesetzlicher Vertreter / Vormund)",
              "text", 2,
              src_text="Ort, Datum (gesetzlicher Vertreter)"),

            f("signature_vertreter",
              "Unterschrift (gesetzlicher Vertreter / Vormund)",
              "signature", 2,
              conf=0.5,
              src_text="Unterschrift des gesetzlichen Vertreters"),
        ]
