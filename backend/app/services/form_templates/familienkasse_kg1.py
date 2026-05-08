"""
Verified field map for Familienkasse KG1 (Antrag auf Kindergeld).

This is the second Level 1 verified template after Jobcenter BuT. It uses
the Phase F/0 fill_strategy="acroform" path: the engine writes user answers
directly into the source PDF's AcroForm widgets (no fitz overlay, no
WriteSpecs).

Source PDF
----------
templates_source/familienkasse_kg1_v1.pdf
SHA256: 53651bbe336039b6ca3852f1fa7288b4841349afd1978a4b91469fea15eaac43

Fingerprint
-----------
The form contains the literal phrases:
  "Antrag auf Kindergeld"
  "Familienkasse"
  "Steuer-Identifikationsnummer"
  "Anlage Kind"
plus the section marker "Kontoverbindung" or "Bankverbindung".

Field strategy (KG1 v1, locked in Phase F1 scope decisions)
-----------------------------------------------------------
- Auto-fill (confidence=1.0):  3 header + 9 applicant + 8 partner +
                               5 bank + 3 abweichende-Person + 20 Tabelle-1
                               + 2 Datum + 2 logical radio groups
                               + 1 Familienstand "seit" date
- Manual    (confidence=0.5):  4 applicant Steuer-ID widgets,
                               4 partner Steuer-ID widgets,
                               25 Tabelle-2 Zählkinder widgets
- Excluded:                    3 pushbuttons (Speichern/Drucken/Alle löschen)
                               filtered out at AcroForm extraction level

Radio groups (Phase F1 mechanism)
---------------------------------
- kg1_applicant_marital_status  → 7 PDF radio widgets (ledig … verwitwet)
- kg1_bank_account_holder       → 2 PDF radio widgets (Antragsteller / andere-Person)

Every shown field has a verified question in en/de/fr/ar/tr/sq via
VERIFIED_BY_FIELD_ID. weak_questions=0 invariant must hold.
"""
from __future__ import annotations

from app.services.form_templates import RadioGroup, VerifiedTemplate


# ── Widget name constants (fully-qualified XFA path; matches PyPDF /T) ───────

# Header (Page 1 of the PDF, but rendered on physical page 2)
W_KG_NR           = "topmostSubform[0].Seite1[0].#area[0].Kopfzeile[0].KG-Nr[0]"
W_TELEFON         = "topmostSubform[0].Seite1[0].#area[0].Kopfzeile[0].#area[3].Telefon[0]"
W_ANZAHL_ANLAGEN  = "topmostSubform[0].Seite1[0].#area[0].Überschrift[0].Anzahl-Anlagen[0]"

# Punkt 1 — Antragsteller
W_APP_STEUER_ID_1 = "topmostSubform[0].Seite1[0].Punkt-1[0].Steuer-ID[0].Steuer-ID-1[0]"
W_APP_STEUER_ID_2 = "topmostSubform[0].Seite1[0].Punkt-1[0].Steuer-ID[0].Steuer-ID-2[0]"
W_APP_STEUER_ID_3 = "topmostSubform[0].Seite1[0].Punkt-1[0].Steuer-ID[0].Steuer-ID-3[0]"
W_APP_STEUER_ID_4 = "topmostSubform[0].Seite1[0].Punkt-1[0].Steuer-ID[0].Steuer-ID-4[0]"
W_APP_TITEL       = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-1[0].Titel-Antragsteller[0]"
W_APP_NAME        = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-1[0].Name-Antragsteller[0]"
W_APP_VORNAME     = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-2[0].Vorname-Antragsteller[0]"
W_APP_GEBURTSNAME = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-2[0].Geburtsname-Antragsteller[0]"
W_APP_GEB_DATUM   = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-3[0].Geburtsdatum-Antragsteller[0]"
W_APP_GEB_ORT     = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-3[0].Geburtsort-Antragsteller[0]"
W_APP_GESCHLECHT  = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-3[0].Geschlecht-Antragsteller[0]"
W_APP_STAATSANG   = "topmostSubform[0].Seite1[0].Punkt-1[0].Pkt-1-Zeile-3[0].Staatsangehörigkeit-Antragsteller[0]"
W_APP_ANSCHRIFT   = "topmostSubform[0].Seite1[0].Punkt-1[0].Anschrift-Antragsteller[0]"

# Familienstand radio widgets (7 options) + a "seit" date field
W_FS_LEDIG        = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].ledig[0]"
W_FS_SEIT         = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].seit[0]"
W_FS_VERHEIRATET  = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].verheiratet[0]"
W_FS_PARTNER      = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].Partner[0]"
W_FS_GESCHIEDEN   = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].geschieden[0]"
W_FS_AUFGEHOBEN   = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].aufgehoben[0]"
W_FS_GETRENNT     = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].getrennt[0]"
W_FS_VERWITWET    = "topmostSubform[0].Seite1[0].Punkt-1[0].Familienstand[0].#area[12].verwitwet[0]"

# Punkt 2 — Partner
# NB: Partner Steuer-ID widget names have a literal backslash before the dot.
# These are the actual /T names in the PDF, preserved verbatim.
W_PRT_STEUER_ID_1 = "topmostSubform[0].Seite1[0].Punkt-2[0].Steuer-ID-2[1].Steuer-ID-2\\.1[0]"
W_PRT_STEUER_ID_2 = "topmostSubform[0].Seite1[0].Punkt-2[0].Steuer-ID-2[1].Steuer-ID-2\\.2[0]"
W_PRT_STEUER_ID_3 = "topmostSubform[0].Seite1[0].Punkt-2[0].Steuer-ID-2[1].Steuer-ID-2\\.3[0]"
W_PRT_STEUER_ID_4 = "topmostSubform[0].Seite1[0].Punkt-2[0].Steuer-ID-2[1].Steuer-ID-2\\.4[0]"
W_PRT_NAME        = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Name-Partner[0]"
W_PRT_VORNAME     = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Vorname-Partner[0]"
W_PRT_TITEL       = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Titel-Partner[0]"
W_PRT_GEB_DATUM   = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Geburtsdatum-Partner[0]"
W_PRT_STAATSANG   = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Staatsangehörigkeit-Partner[0]"
W_PRT_GESCHLECHT  = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Geschlecht-Partner[0]"
W_PRT_GEBURTSNAME = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Geburtsname-Partner[0]"
W_PRT_ANSCHRIFT   = "topmostSubform[0].Seite1[0].Punkt-2[0].#area[15].Anschrift-Partner[0]"

# Punkt 3 — Bankverbindung
W_BANK_IBAN       = "topmostSubform[0].Seite1[0].Punkt-3[0].IBAN[0]"
W_BANK_BIC        = "topmostSubform[0].Seite1[0].Punkt-3[0].BIC[0]"
W_BANK_NAME       = "topmostSubform[0].Seite1[0].Punkt-3[0].Bank[0]"
W_BANK_OWNER_APP  = "topmostSubform[0].Seite1[0].Punkt-3[0].Antragsteller[0]"
W_BANK_OWNER_OTH  = "topmostSubform[0].Seite1[0].Punkt-3[0].andere-Person[0]"
W_BANK_OWNER_NAME = "topmostSubform[0].Seite1[0].Punkt-3[0].Name-Kontoinhaber[0]"

# Punkt 4 — Abweichende Person (only filled when Punkt 3 says "andere-Person")
W_AP_NAME         = "topmostSubform[0].Page2[0].Punkt-4[0].Name-abweichende-Person[0]"
W_AP_VORNAME      = "topmostSubform[0].Page2[0].Punkt-4[0].Vorname-abweichende-Person[0]"
W_AP_ANSCHRIFT    = "topmostSubform[0].Page2[0].Punkt-4[0].Anschrift-abweichende-Person[0]"

# Punkt 5 — Tabelle 1 Kinder (5 rows × 4 columns)
# Column meanings (verified F3): Zelle1=Vorname/Familienname, Zelle2=Geburtsdatum,
# Zelle3=Geschlecht, Zelle4=Familienkasse + Kindergeldnummer
def _w_t1(row: int, cell: int) -> str:
    return (
        f"topmostSubform[0].Page2[0].Punkt-5[0].Tabelle1-Kinder[0]"
        f".Zeile{row}[0].Zelle{cell}[0]"
    )

# Punkt 6 — Tabelle 2 Zählkinder (manual, deferred to v2)
def _w_t2(row: int, cell: int) -> str:
    return (
        f"topmostSubform[0].Page2[0].Punkt-6[0].Tabelle2-Zählkinder[0]"
        f".Zeile{row}[0].Zelle{cell}[0]"
    )

# Unterschrift dates
W_DATUM_1         = "topmostSubform[0].Page2[0].Unterschrift-1[0].Datum-1[0]"
W_DATUM_2         = "topmostSubform[0].Page2[0].Unterschrift-2[0].Datum-2[0]"


# ── Logical radio-group field IDs (NOT widget names — these are user-facing) ─

LOGICAL_FAMILIENSTAND   = "kg1_applicant_marital_status"
LOGICAL_BANK_OWNER      = "kg1_bank_account_holder"


# ── Semantic key inferences (best-effort, optional) ─────────────────────────

_SEMANTIC_KEYS: dict = {
    W_APP_VORNAME:     "person.first_name",
    W_APP_NAME:        "person.last_name",
    W_APP_GEBURTSNAME: "person.birth_name",
    W_APP_GEB_DATUM:   "person.birth_date",
    W_APP_GEB_ORT:     "person.birth_place",
    W_APP_GESCHLECHT:  "person.gender",
    W_APP_STAATSANG:   "person.nationality",
    W_APP_ANSCHRIFT:   "person.address",
    W_PRT_VORNAME:     "person.first_name",
    W_PRT_NAME:        "person.last_name",
    W_PRT_GEBURTSNAME: "person.birth_name",
    W_PRT_GEB_DATUM:   "person.birth_date",
    W_PRT_STAATSANG:   "person.nationality",
    W_PRT_GESCHLECHT:  "person.gender",
    W_PRT_ANSCHRIFT:   "person.address",
    W_BANK_IBAN:       "bank.iban",
    W_BANK_BIC:        "bank.bic",
    W_TELEFON:         "contact.phone",
}


# ── Fingerprint markers ──────────────────────────────────────────────────────
# All required phrases are German. Conservative: requires THREE federal-form
# phrases that all appear in KG1 but rarely appear together in other forms.
_REQUIRED = [
    "antrag auf kindergeld",
    "familienkasse",
    "steuer-identifikationsnummer",
]

# Section markers — at least one must appear. Reduces collision with the
# Anlage Kind which mentions Kindergeld but not these section names.
_SECTION_MARKERS = [
    "anlage kind",
    "bankverbindung",
    "kontoverbindung",
    "kindergeld bereits beziehe",
    "zählkinder",
]


class FamilienkasseKg1Template(VerifiedTemplate):
    template_id   = "familienkasse_kg1_v1"
    name          = "Familienkasse — Antrag auf Kindergeld (KG1)"
    fill_strategy = "acroform"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        required_ok = all(p in lo for p in _REQUIRED)
        section_ok  = any(s in lo for s in _SECTION_MARKERS)
        return required_ok and section_ok

    def get_field_map(self) -> list:
        from app.services.pdf_pipeline import FieldMapEntry

        def auto(field_id, label, ftype, page, opts=None, src_text=None):
            """Build an auto-fill FieldMapEntry (confidence=1.0, shown)."""
            return FieldMapEntry(
                field_id=field_id,
                original_label=label,
                field_type=ftype,
                source_page=page,
                options=opts or [],
                current_value="",
                confidence=1.0,
                source="verified_template",
                source_text=src_text or label,
                reason="pdf_field",
                semantic_key=_SEMANTIC_KEYS.get(field_id),
            )

        def manual(field_id, label, page, src_text=None):
            """Build a manual FieldMapEntry (confidence=0.5, hidden)."""
            return FieldMapEntry(
                field_id=field_id,
                original_label=label,
                field_type="text",
                source_page=page,
                options=[],
                current_value="",
                confidence=0.5,           # show_question=False via the gate
                source="verified_template",
                source_text=src_text or label,
                reason="pdf_field",
            )

        # All field_type values for v1 are "text" (matching the underlying
        # /Tx widgets), except the two logical radio groups and the gender
        # selects. This avoids tripping date_missing_example for date-shaped
        # fields without forcing us to author a separate _GUIDANCE dict —
        # the format hint lives inside each verified question entry.
        return [
            # ── Header (Page 1) ──────────────────────────────────────────
            auto(W_KG_NR,          "Kindergeld-Nummer",    "text", 1,
                 src_text="Kindergeld-Nr."),
            auto(W_TELEFON,        "Telefonnummer",        "text", 1,
                 src_text="Telefonnummer (Rückfragen)"),
            auto(W_ANZAHL_ANLAGEN, "Anzahl der Anlagen",   "text", 1,
                 src_text="Anzahl beigefügter Anlagen"),

            # ── Punkt 1 — Antragsteller (Page 1) ─────────────────────────
            manual(W_APP_STEUER_ID_1, "Steuer-ID Block 1", 1),
            manual(W_APP_STEUER_ID_2, "Steuer-ID Block 2", 1),
            manual(W_APP_STEUER_ID_3, "Steuer-ID Block 3", 1),
            manual(W_APP_STEUER_ID_4, "Steuer-ID Block 4", 1),
            auto(W_APP_TITEL,       "Titel",                "text", 1,
                 src_text="Titel (akademischer Titel, optional)"),
            auto(W_APP_NAME,        "Name",                 "text", 1,
                 src_text="Name (Familienname)"),
            auto(W_APP_VORNAME,     "Vorname",              "text", 1),
            auto(W_APP_GEBURTSNAME, "Geburtsname",          "text", 1,
                 src_text="Geburtsname (falls abweichend)"),
            auto(W_APP_GEB_DATUM,   "Geburtsdatum",         "text", 1),
            auto(W_APP_GEB_ORT,     "Geburtsort",           "text", 1),
            auto(W_APP_GESCHLECHT,  "Geschlecht",           "select", 1,
                 opts=["m", "w", "d"]),
            auto(W_APP_STAATSANG,   "Staatsangehörigkeit",  "text", 1),
            auto(W_APP_ANSCHRIFT,   "Anschrift",            "text", 1,
                 src_text="Anschrift (Straße, Hausnummer, PLZ, Ort)"),

            # Logical Familienstand radio question (covers 7 widgets)
            auto(LOGICAL_FAMILIENSTAND, "Familienstand", "radio", 1,
                 opts=["ledig", "verheiratet", "Lebenspartnerschaft",
                       "geschieden", "Lebenspartnerschaft aufgehoben",
                       "dauernd getrennt lebend", "verwitwet"],
                 src_text="Familienstand"),
            auto(W_FS_SEIT, "seit", "text", 1,
                 src_text="Familienstand seit (TT.MM.JJJJ)"),

            # ── Punkt 2 — Partner (Page 1) ───────────────────────────────
            manual(W_PRT_STEUER_ID_1, "Steuer-ID des Partners Block 1", 1),
            manual(W_PRT_STEUER_ID_2, "Steuer-ID des Partners Block 2", 1),
            manual(W_PRT_STEUER_ID_3, "Steuer-ID des Partners Block 3", 1),
            manual(W_PRT_STEUER_ID_4, "Steuer-ID des Partners Block 4", 1),
            auto(W_PRT_NAME,        "Name des Partners",       "text", 1),
            auto(W_PRT_VORNAME,     "Vorname des Partners",    "text", 1),
            auto(W_PRT_TITEL,       "Titel des Partners",      "text", 1),
            auto(W_PRT_GEB_DATUM,   "Geburtsdatum des Partners","text", 1),
            auto(W_PRT_STAATSANG,   "Staatsangehörigkeit des Partners","text", 1),
            auto(W_PRT_GESCHLECHT,  "Geschlecht des Partners", "select", 1,
                 opts=["m", "w", "d"]),
            auto(W_PRT_GEBURTSNAME, "Geburtsname des Partners","text", 1),
            auto(W_PRT_ANSCHRIFT,   "Anschrift des Partners",  "text", 1),

            # ── Punkt 3 — Bankverbindung (Page 1) ────────────────────────
            auto(W_BANK_IBAN,        "IBAN",       "text", 1),
            auto(W_BANK_BIC,         "BIC",        "text", 1),
            auto(W_BANK_NAME,        "Bank",       "text", 1,
                 src_text="Name der Bank"),
            # Logical account-holder radio (covers 2 widgets)
            auto(LOGICAL_BANK_OWNER, "Kontoinhaber", "radio", 1,
                 opts=["Antragsteller", "andere Person"],
                 src_text="Kontoinhaber"),
            auto(W_BANK_OWNER_NAME,  "Name des Kontoinhabers", "text", 1),

            # ── Punkt 4 — Abweichende Person (Page 2) ────────────────────
            auto(W_AP_NAME,      "Name der abweichenden Person",     "text", 2),
            auto(W_AP_VORNAME,   "Vorname der abweichenden Person",  "text", 2),
            auto(W_AP_ANSCHRIFT, "Anschrift der abweichenden Person","text", 2),

            # ── Punkt 5 — Tabelle 1 Kinder (5 rows × 4 columns, Page 2) ──
            # Column meanings verified by F3 visual inspection.
            *[
                auto(_w_t1(row, cell), label, ftype, 2)
                for row in (1, 2, 3, 4, 5)
                for cell, label, ftype in (
                    (1, f"Kind {row} — Vorname",      "text"),
                    (2, f"Kind {row} — Geburtsdatum", "text"),
                    (3, f"Kind {row} — Geschlecht",   "text"),
                    (4, f"Kind {row} — Familienkasse + Kindergeldnummer", "text"),
                )
            ],

            # ── Punkt 6 — Tabelle 2 Zählkinder (manual, deferred to v2) ──
            *[
                manual(_w_t2(row, cell),
                       f"Zählkind {row} — Spalte {cell}", 2)
                for row in (1, 2, 3, 4, 5)
                for cell in (1, 2, 3, 4, 5)
            ],

            # ── Unterschrift dates (Page 2) ──────────────────────────────
            auto(W_DATUM_1, "Datum (Unterschrift 1)", "text", 2),
            auto(W_DATUM_2, "Datum (Unterschrift 2)", "text", 2),
        ]

    def get_radio_groups(self) -> list[RadioGroup]:
        return [
            # 7-option marital-status radio. The widget names map to the
            # German option strings the user picks. The user-visible
            # question's options list (in get_field_map above) MUST keep
            # the same ordering so the option index stays consistent.
            RadioGroup(
                field_id=LOGICAL_FAMILIENSTAND,
                widget_names=[
                    W_FS_LEDIG, W_FS_VERHEIRATET, W_FS_PARTNER,
                    W_FS_GESCHIEDEN, W_FS_AUFGEHOBEN, W_FS_GETRENNT,
                    W_FS_VERWITWET,
                ],
                options=[
                    ("ledig",                          W_FS_LEDIG),
                    ("verheiratet",                    W_FS_VERHEIRATET),
                    ("Lebenspartnerschaft",            W_FS_PARTNER),
                    ("geschieden",                     W_FS_GESCHIEDEN),
                    ("Lebenspartnerschaft aufgehoben", W_FS_AUFGEHOBEN),
                    ("dauernd getrennt lebend",        W_FS_GETRENNT),
                    ("verwitwet",                      W_FS_VERWITWET),
                ],
            ),
            # Bank account-holder: applicant or another person?
            RadioGroup(
                field_id=LOGICAL_BANK_OWNER,
                widget_names=[W_BANK_OWNER_APP, W_BANK_OWNER_OTH],
                options=[
                    ("Antragsteller", W_BANK_OWNER_APP),
                    ("andere Person", W_BANK_OWNER_OTH),
                ],
            ),
        ]
