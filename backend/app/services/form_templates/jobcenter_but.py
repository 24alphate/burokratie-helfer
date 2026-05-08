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


# ── Guidance content (English + German) ───────────────────────────────────────
# Keyed by field_id. Each value is the kwargs dict for GuidanceText.
# Fallback order in the UI: user locale → "en" → "de".

_GUIDANCE: dict = {
    "applicant_name_vorname": {
        "plain_language": {
            "en": "Your full legal name as it appears on your ID, passport, or residence permit.",
            "de": "Ihr vollständiger Name, wie er auf Ihrem Ausweis oder Aufenthaltstitel steht.",
        },
        "format_hint": {
            "en": "Last name first, then first name. Example: Müller, Anna",
            "de": "Zuerst Nachname, dann Vorname. Beispiel: Müller, Anna",
        },
    },
    "applicant_postanschrift": {
        "plain_language": {
            "en": "Your current home address: street, house number, postal code, and city.",
            "de": "Ihre aktuelle Wohnanschrift: Straße, Hausnummer, Postleitzahl und Ort.",
        },
        "format_hint": {
            "en": "Example: Hauptstraße 12, 18055 Rostock",
            "de": "Beispiel: Hauptstraße 12, 18055 Rostock",
        },
    },
    "bedarfsgemeinschaft_nummer": {
        "plain_language": {
            "en": "The Jobcenter's identification number for your household (Bedarfsgemeinschaft). It links all members of your benefit case.",
            "de": "Die Nummer, unter der das Jobcenter Ihren Haushalt (Ihre Bedarfsgemeinschaft) führt.",
        },
        "where_to_find": {
            "en": "Look at a recent Jobcenter letter — usually on the first page near the top right, labelled 'BG-Nummer' or 'Nummer der Bedarfsgemeinschaft'.",
            "de": "Auf einem aktuellen Jobcenter-Brief, meist oben rechts auf der ersten Seite, als 'BG-Nummer' oder 'Nummer der Bedarfsgemeinschaft'.",
        },
        "format_hint": {
            "en": "Copy it exactly as written, including spaces, slashes, or dashes.",
            "de": "Genau so abschreiben wie angegeben, einschließlich Leerzeichen, Schrägstrichen oder Bindestrichen.",
        },
        "example": {"en": "12345BG0001234", "de": "12345BG0001234"},
        "common_mistakes": {
            "en": ["Do not enter your tax ID, health insurance number, or phone number here."],
            "de": ["Bitte nicht Steuer-ID, Krankenversicherungsnummer oder Telefonnummer eintragen."],
        },
    },
    "tag_der_antragstellung": {
        "plain_language": {
            "en": "Today's date — the date you are completing and submitting this application.",
            "de": "Das heutige Datum — der Tag, an dem Sie diesen Antrag ausfüllen und einreichen.",
        },
        "format_hint": {
            "en": "German date format: DD.MM.YYYY",
            "de": "Deutsches Datumsformat: TT.MM.JJJJ",
        },
        "example": {"en": "06.05.2026", "de": "06.05.2026"},
    },
    "benefit_sgb_ii": {
        "plain_language": {
            "en": "Check this if you currently receive Bürgergeld (basic income support) from the Jobcenter under SGB II.",
            "de": "Ankreuzen, wenn Sie aktuell Bürgergeld vom Jobcenter nach dem SGB II erhalten.",
        },
        "where_to_find": {
            "en": "Check your most recent Jobcenter approval letter — it will mention 'SGB II' or 'Bürgergeld'.",
            "de": "Auf Ihrem aktuellen Bewilligungsbescheid des Jobcenters steht 'SGB II' oder 'Bürgergeld'.",
        },
        "warning": {
            "en": "If you are unsure which benefit you receive, check your latest approval letter before selecting.",
            "de": "Wenn Sie unsicher sind, prüfen Sie bitte zuerst Ihren aktuellen Bescheid.",
        },
    },
    "benefit_sgb_xii": {
        "plain_language": {
            "en": "Check this if you receive social assistance under SGB XII, typically managed by the social welfare office (Sozialamt), not the Jobcenter.",
            "de": "Ankreuzen, wenn Sie Sozialhilfe nach SGB XII vom Sozialamt erhalten (nicht vom Jobcenter).",
        },
        "where_to_find": {
            "en": "Check a letter from your Sozialamt mentioning 'SGB XII' or 'Sozialhilfe'.",
            "de": "Auf einem Brief Ihres Sozialamts, auf dem 'SGB XII' oder 'Sozialhilfe' steht.",
        },
    },
    "benefit_kinderzuschlag": {
        "plain_language": {
            "en": "Check this if you receive the child supplement (Kinderzuschlag) for your children. This is paid by the Familienkasse.",
            "de": "Ankreuzen, wenn Sie Kinderzuschlag von der Familienkasse erhalten.",
        },
        "where_to_find": {
            "en": "Look for a letter from the Familienkasse mentioning 'Kinderzuschlag'.",
            "de": "Auf einem Brief der Familienkasse mit dem Begriff 'Kinderzuschlag'.",
        },
    },
    "benefit_wohngeld": {
        "plain_language": {
            "en": "Check this if you currently receive housing benefit (Wohngeld) from your city or district office.",
            "de": "Ankreuzen, wenn Sie Wohngeld von der Wohngeldstelle Ihrer Stadt oder Gemeinde erhalten.",
        },
        "where_to_find": {
            "en": "Look for a letter from the Wohngeldstelle or city office mentioning 'Wohngeld'.",
            "de": "Auf einem Brief der Wohngeldstelle Ihrer Stadt oder Gemeinde.",
        },
    },
    "benefit_asylbewerberleistungsgesetz": {
        "plain_language": {
            "en": "Check this if you receive benefits under the Asylum Seekers' Benefits Act (AsylbLG).",
            "de": "Ankreuzen, wenn Sie Leistungen nach dem Asylbewerberleistungsgesetz erhalten.",
        },
        "where_to_find": {
            "en": "Check a letter from the Sozialamt or Ausländerbehörde mentioning 'AsylbLG' or 'Asylbewerberleistungsgesetz'.",
            "de": "Auf einem Brief des Sozialamts oder der Ausländerbehörde.",
        },
    },
    "benefit_sonstige": {
        "plain_language": {
            "en": "Check this if you receive other benefits not listed above. Write the name of the benefit in the space provided on the form.",
            "de": "Ankreuzen, wenn Sie andere, oben nicht genannte Leistungen erhalten. Bitte Leistung angeben.",
        },
    },
    "bg_nummer": {
        "plain_language": {
            "en": "The case reference number (Aktenzeichen) of the approved benefit that entitles you to apply for Bildung und Teilhabe.",
            "de": "Das Aktenzeichen des Bewilligungsbescheids, der Ihre Berechtigung für Bildung-und-Teilhabe-Leistungen belegt.",
        },
        "where_to_find": {
            "en": "Find it on the most recent approval letter for your benefit, labelled 'BG-Nummer', 'Aktenzeichen', or 'Geschäftszeichen'.",
            "de": "Auf dem aktuellen Bewilligungsbescheid Ihrer Leistung, als 'BG-Nummer', 'Aktenzeichen' oder 'Geschäftszeichen'.",
        },
        "format_hint": {
            "en": "Copy it exactly as written.",
            "de": "Genau so abschreiben wie angegeben.",
        },
    },
    "zustaendiger_standort": {
        "plain_language": {
            "en": "The name or address of the Jobcenter office responsible for your case.",
            "de": "Der Name oder die Adresse der für Sie zuständigen Jobcenter-Dienststelle.",
        },
        "where_to_find": {
            "en": "Look at the sender details on any recent Jobcenter letter.",
            "de": "Im Briefkopf oder Absender auf einem aktuellen Jobcenter-Schreiben.",
        },
    },
    "child_name_vorname_geburtsdatum": {
        "plain_language": {
            "en": "The full name and date of birth of the child for whom you are applying for these benefits.",
            "de": "Der vollständige Name und das Geburtsdatum des Kindes, für das Sie die Leistungen beantragen.",
        },
        "format_hint": {
            "en": "Last name, First name, Date of Birth (DD.MM.YYYY). Example: Müller, Lena, 12.03.2016",
            "de": "Nachname, Vorname, Geburtsdatum (TT.MM.JJJJ). Beispiel: Müller, Lena, 12.03.2016",
        },
    },
    "institution_name": {
        "plain_language": {
            "en": "The official name of the school, kindergarten, daycare, or training institution the child attends.",
            "de": "Der offizielle Name der Schule, Kita, Einrichtung oder Ausbildungsstätte, die das Kind besucht.",
        },
        "format_hint": {
            "en": "Use the full official name, e.g. 'Grundschule am Mühlenberg'.",
            "de": "Den vollständigen offiziellen Namen verwenden, z.B. 'Grundschule am Mühlenberg'.",
        },
    },
    "institution_address": {
        "plain_language": {
            "en": "The street address of the school or institution the child attends.",
            "de": "Die Anschrift der Schule oder Einrichtung, die das Kind besucht.",
        },
        "format_hint": {
            "en": "Include street, house number, postal code, and city.",
            "de": "Straße, Hausnummer, Postleitzahl und Ort angeben.",
        },
    },
    "leistung_a_ausflug": {
        "plain_language": {
            "en": "Check this if you are applying for support with costs for day trips organised by the school or kindergarten (e.g. museum visits, excursions).",
            "de": "Ankreuzen, wenn Sie die Übernahme der Kosten für eintägige Ausflüge der Schule oder Kita beantragen.",
        },
    },
    "leistung_b_klassenfahrt": {
        "plain_language": {
            "en": "Check this if you are applying for support with costs for multi-day class trips or kindergarten trips.",
            "de": "Ankreuzen, wenn Sie die Übernahme der Kosten für mehrtägige Klassenfahrten oder Kita-Fahrten beantragen.",
        },
    },
    "leistung_c_schuelerbefoerderung": {
        "plain_language": {
            "en": "Check this if you need financial support for transporting the child to and from school.",
            "de": "Ankreuzen, wenn Sie Unterstützung für die Kosten der Schülerbeförderung beantragen.",
        },
        "why_needed": {
            "en": "This covers public transport passes or private vehicle costs where no public option is available.",
            "de": "Fördert ÖPNV-Tickets oder Kosten für Privatfahrzeuge, wenn keine öffentliche Verbindung möglich ist.",
        },
    },
    "leistung_d_lernfoerderung": {
        "plain_language": {
            "en": "Check this if the child needs tutoring or learning support to reach the expected grade level.",
            "de": "Ankreuzen, wenn das Kind Lernförderung (z.B. Nachhilfe) benötigt, um das Klassenziel zu erreichen.",
        },
        "required_documents": {
            "en": ["Statement from the school confirming the need for tutoring"],
            "de": ["Schulbescheinigung über den Bedarf an Lernförderung"],
        },
    },
    "leistung_e_mittagessen": {
        "plain_language": {
            "en": "Check this if you want support for the cost of shared lunch at school, after-school care (Hort), kindergarten, or daycare.",
            "de": "Ankreuzen, wenn Sie Zuschuss zu den Kosten des gemeinschaftlichen Mittagessens in Schule, Hort oder Kita beantragen.",
        },
        "required_documents": {
            "en": ["Proof of lunch registration", "Invoice or monthly cost statement from the school or provider"],
            "de": ["Anmeldenachweis für das Mittagessen", "Rechnung oder monatliche Kostenaufstellung des Anbieters"],
        },
    },
    "leistung_f_soziale_teilhabe": {
        "plain_language": {
            "en": "Check this if you want support for social or cultural activities for the child — such as sports club membership, music lessons, or cultural events.",
            "de": "Ankreuzen, wenn Sie Zuschuss für soziale und kulturelle Aktivitäten des Kindes beantragen (z.B. Vereinsbeitrag, Musikunterricht).",
        },
        "why_needed": {
            "en": "This covers up to 15 EUR per month for activities that promote social participation.",
            "de": "Fördert bis zu 15 EUR pro Monat für Aktivitäten zur sozialen Teilhabe.",
        },
    },
    "transport_cost_period": {
        "plain_language": {
            "en": "How often the transport costs you are reporting occur: monthly, quarterly, or annually.",
            "de": "Der Abrechnungszeitraum für die angegebenen Beförderungskosten: monatlich, vierteljährlich oder jährlich.",
        },
        "format_hint": {
            "en": "Write: 'monatlich' (monthly), 'vierteljährlich' (quarterly), or 'jährlich' (annual).",
            "de": "Eintragen: 'monatlich', 'vierteljährlich' oder 'jährlich'.",
        },
    },
    "transport_public_cost_eur": {
        "plain_language": {
            "en": "The cost of the public transport pass or ticket used for the child's school journey, in Euros.",
            "de": "Die Kosten für das ÖPNV-Ticket oder die Monatskarte für den Schulweg des Kindes, in Euro.",
        },
        "format_hint": {
            "en": "Enter the amount in EUR, e.g. 29.50",
            "de": "Betrag in EUR angeben, z.B. 29,50",
        },
    },
    "transport_private_cost_eur": {
        "plain_language": {
            "en": "The cost of private transport (e.g. by car) when no suitable public transport is available.",
            "de": "Die Kosten für private Beförderung (z.B. mit dem Auto), wenn kein geeigneter ÖPNV verfügbar ist.",
        },
        "format_hint": {
            "en": "Enter the amount in EUR.",
            "de": "Betrag in EUR angeben.",
        },
    },
    "transport_distance_km": {
        "plain_language": {
            "en": "The one-way distance in kilometres between the child's home address and the school.",
            "de": "Die einfache Entfernung in Kilometern zwischen Wohnanschrift und Schule.",
        },
        "format_hint": {
            "en": "Enter the one-way distance (not round trip) in km. Example: 5",
            "de": "Einfache Strecke (nicht Hin- und Rückweg) in km angeben. Beispiel: 5",
        },
        "example": {"en": "5", "de": "5"},
    },
    "essen_anbieter": {
        "plain_language": {
            "en": "The name of the company or organisation that provides the lunch at school or childcare.",
            "de": "Der Name des Unternehmens oder Anbieters, der das Mittagessen in der Schule oder Kita liefert.",
        },
        "where_to_find": {
            "en": "Usually printed on the monthly invoice or the school's lunch registration form.",
            "de": "Auf der monatlichen Rechnung oder dem Anmeldeformular für das Schulessen.",
        },
    },
    "lunch_school_hort": {
        "plain_language": {
            "en": "Check this if the child eats lunch at school or at after-school care (Hort).",
            "de": "Ankreuzen, wenn das Kind in einer Schule oder einem Hort zu Mittag isst.",
        },
    },
    "lunch_kita_kindertagespflege": {
        "plain_language": {
            "en": "Check this if the child eats lunch at a kindergarten (Kita) or with a childminder (Kindertagespflege).",
            "de": "Ankreuzen, wenn das Kind in einer Kita oder Kindertagespflege zu Mittag isst.",
        },
    },
    "consent_direct_settlement": {
        "plain_language": {
            "en": "Check this to allow the Jobcenter to pay the provider (school, club, etc.) directly instead of reimbursing you.",
            "de": "Ankreuzen, um dem Jobcenter zu erlauben, den Leistungsanbieter direkt zu bezahlen (statt Ihnen das Geld zu erstatten).",
        },
        "why_needed": {
            "en": "This is the standard procedure. The Jobcenter transfers the amount directly to the school, lunch provider, or club.",
            "de": "Dies ist das übliche Verfahren. Das Jobcenter überweist den Betrag direkt an Schule, Essensanbieter oder Verein.",
        },
    },
    "ort_datum_antragsteller": {
        "plain_language": {
            "en": "The city where you are submitting the application, and today's date.",
            "de": "Der Ort, an dem Sie den Antrag einreichen, und das heutige Datum.",
        },
        "format_hint": {
            "en": "Write: City, DD.MM.YYYY — Example: Rostock, 06.05.2026",
            "de": "Format: Ort, TT.MM.JJJJ — Beispiel: Rostock, 06.05.2026",
        },
        "example": {"en": "Rostock, 06.05.2026", "de": "Rostock, 06.05.2026"},
    },
}

# ── Semantic keys — for future answer reuse (does not affect field_id / PDF filling) ──
# Only map to keys that actually exist in SEMANTIC_QUESTIONS.
_SEMANTIC_KEYS: dict = {
    "applicant_name_vorname":     "person.full_name",
    "bedarfsgemeinschaft_nummer": "jobcenter.bg_number",
    "tag_der_antragstellung":     "submission.date",
    "institution_name":           "institution.name",
    "ort_datum_antragsteller":    "submission.place_date",
}


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
                guidance=_GUIDANCE.get(field_id),
                semantic_key=_SEMANTIC_KEYS.get(field_id),
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

    def get_write_specs(self) -> list:
        from app.services.form_templates import WriteSpec

        # Helper: text field — write below the label line
        def txt(field_id, label_search, page, offset_y=10.0, font_size=9.0):
            return WriteSpec(
                field_id=field_id, field_type="text", source_page=page,
                strategy="label_search", label_search=label_search,
                offset_x=0.0, offset_y=offset_y, font_size=font_size,
            )

        # Helper: checkbox — draw X to the left of the label text (where the box is).
        # offset_x=-12 positions the X center ~12pt left of the label's x0,
        # which places it inside the checkbox square for standard BuT form layout.
        # alt: shorter / umlaut-free strings tried if the primary label_search fails.
        def chk(field_id, label_search, page, offset_x=-12.0, offset_y=-3.0, alt=()):
            return WriteSpec(
                field_id=field_id, field_type="checkbox", source_page=page,
                strategy="label_search", label_search=label_search,
                offset_x=offset_x, offset_y=offset_y,
                font_size=9.0, checkbox_size=5.0,
                alt_label_searches=list(alt),
            )

        # Helper: skip (signature — user signs manually)
        def sig(field_id, page):
            return WriteSpec(
                field_id=field_id, field_type="signature", source_page=page,
                strategy="skip",
            )

        return [
            # ── Section 1: Persönliche Angaben ────────────────────────────────
            txt("applicant_name_vorname",        "Name, Vorname",                          1),
            txt("applicant_postanschrift",        "Postanschrift",                          1),
            txt("bedarfsgemeinschaft_nummer",     "Nummer der Bedarfsgemeinschaft",         1),
            txt("tag_der_antragstellung",         "Tag der Antragstellung",                 1),

            # Benefit type checkboxes — alt= gives shorter fallback strings for
            # cases where the primary search_for() finds nothing (encoding / spacing).
            chk("benefit_sgb_ii",
                "Leistungen nach dem SGB II",       1,
                alt=["nach dem SGB II", "SGB II"]),
            chk("benefit_sgb_xii",
                "Leistungen nach dem SGB XII",      1,
                alt=["nach dem SGB XII", "SGB XII"]),
            chk("benefit_kinderzuschlag",
                "Kinderzuschlag nach dem BKGG",     1,
                alt=["Kinderzuschlag nach", "BKGG"]),
            chk("benefit_wohngeld",
                "Wohngeld nach dem WoGG",           1,
                alt=["Wohngeld nach", "WoGG"]),
            chk("benefit_asylbewerberleistungsgesetz",
                "Leistungen nach dem Asylbewerberleistungsgesetz", 1,
                alt=["Asylbewerberleistungsgesetz", "Asylbewerber"]),
            chk("benefit_sonstige",
                "Sonstige",                         1,
                alt=["Sonstige Leistungen"]),

            txt("bg_nummer",                      "BG-Nummer / Aktenzeichen",               1),
            txt("zustaendiger_standort",           "Zuständiger Standort",                   1),

            # ── Section 2: Kind / Jugendliche/r ──────────────────────────────
            txt("child_name_vorname_geburtsdatum", "Name, Vorname, Geburtsdatum des Kindes", 1),
            txt("institution_name",               "Name der Schule / Kindertagesstätte / Einrichtung", 1),
            txt("institution_address",            "Anschrift der Schule / Kindertagesstätte", 1),

            # ── Section 3: Beantragte Leistung A–F ───────────────────────────
            chk("leistung_a_ausflug",
                "A Eintägige Ausflüge von Schulen und Kindertageseinrichtungen", 1,
                alt=["A Eintägige", "Eintägige Ausflüge", "Eintägige"]),
            chk("leistung_b_klassenfahrt",
                "B Mehrtägige Klassenfahrten und Fahrten der Kindertageseinrichtungen", 1,
                alt=["B Mehrtägige", "Mehrtägige Klassenfahrten", "Klassenfahrten"]),
            chk("leistung_c_schuelerbefoerderung",
                "C Schülerbeförderung",             1,
                alt=["Schülerbeförderung", "C Sch"]),
            chk("leistung_d_lernfoerderung",
                "D Lernförderung",                  1,
                alt=["Lernförderung", "D Lernf"]),
            chk("leistung_e_mittagessen",
                "E Gemeinschaftliches Mittagessen",  1,
                alt=["Gemeinschaftliches Mittagessen", "Mittagessen"]),
            chk("leistung_f_soziale_teilhabe",
                "F Soziale und kulturelle Teilhabe", 1,
                alt=["Soziale und kulturelle Teilhabe", "kulturelle Teilhabe"]),

            # ── Section 3.C: Schülerbeförderung ──────────────────────────────
            txt("transport_cost_period",          "Kosten der Beförderung monatlich / vierteljährlich / jährlich", 2),
            txt("transport_public_cost_eur",      "Kosten für öffentliche Verkehrsmittel",  2),
            txt("transport_private_cost_eur",     "Kosten für private Beförderung (Kraftfahrzeug)", 2),
            txt("transport_distance_km",          "Einfache Strecke in km",                 2),

            # ── Section 3.E: Mittagessen ──────────────────────────────────────
            txt("essen_anbieter",                 "Name des Essenanbieters",                2),
            chk("lunch_school_hort",
                "in einer Schule oder einem Hort",  2,
                alt=["Schule oder einem Hort", "einem Hort"]),
            chk("lunch_kita_kindertagespflege",
                "in einer Kindertageseinrichtung oder Kindertagespflege", 2,
                alt=["Kindertageseinrichtung oder Kindertagespflege", "Kindertagespflege"]),
            txt("lunch_sonstige_angaben",         "Sonstige Angaben",                       2),

            # ── Declarations / Signature ──────────────────────────────────────
            chk("consent_direct_settlement",
                "Ich bin damit einverstanden, dass das Jobcenter die Leistung direkt mit dem Leistungsanbieter abrechnet", 2,
                alt=["Ich bin damit einverstanden", "direkt mit dem Leistungsanbieter", "einverstanden"]),
            txt("ort_datum_antragsteller",        "Ort, Datum",                             2),
            sig("signature_antragsteller",                                                    2),
            txt("ort_datum_vertreter",            "Ort, Datum (gesetzlicher Vertreter)",    2),
            sig("signature_vertreter",                                                        2),
        ]
