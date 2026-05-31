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

from app.services.form_templates import RadioGroup, SplitField, VerifiedTemplate


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

# Phase v2 — logical split fields (one user question → several comb widgets).
# The 11-digit Steuer-ID is laid out on the PDF as 4 comb boxes (2/3/3/3).
LOGICAL_APP_STEUER_ID   = "kg1_applicant_steuer_id"
LOGICAL_PRT_STEUER_ID   = "kg1_partner_steuer_id"

# Slice plan for both Steuer-ID groups, verified against the PDF widgets'
# /MaxLen (2, 3, 3, 3 — comb fields). sum == 11 == length of a German IdNr.
_STEUER_ID_SLICES = [2, 3, 3, 3]


# ── Conditional-flow gates (Phase v2) ────────────────────────────────────────
# Schema mirrors FormEngine.evaluate_condition. Evaluated client-side in the
# stateless pipeline; re-applied at fill time when the review page filters
# answers to currently-applicable fields.

# Punkt 2 (partner) is shown ONLY for applicants who currently have a spouse /
# registered partner. Scope decision: verheiratet + Lebenspartnerschaft only.
_COND_HAS_PARTNER = {
    "type": "field_in",
    "field_key": LOGICAL_FAMILIENSTAND,
    "values": ["verheiratet", "Lebenspartnerschaft"],
}

# "Familienstand seit" only makes sense once the status is not 'ledig'.
_COND_NOT_LEDIG = {
    "type": "field_not_equals",
    "field_key": LOGICAL_FAMILIENSTAND,
    "value": "ledig",
}

# Punkt 4 (abweichende Person) only when the Kindergeld account belongs to
# someone other than the applicant.
_COND_OTHER_ACCOUNT = {
    "type": "field_equals",
    "field_key": LOGICAL_BANK_OWNER,
    "value": "andere Person",
}


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
# (Verified by F3 + smoke check against the actual KG1 PDF text extraction.)
_REQUIRED = [
    "antrag auf kindergeld",
    "familienkasse",
    "steuerliche identifikationsnummer",  # the form uses this German phrasing
]

# Section markers — at least one must appear. Reduces collision with the
# Anlage Kind form which also mentions Kindergeld but not these markers.
_SECTION_MARKERS = [
    "anlage kind",
    "kontoverbindung",
    "zählkinder",
    "kindergeldnummer",
]


class FamilienkasseKg1Template(VerifiedTemplate):
    template_id   = "familienkasse_kg1_v1"
    name          = "Familienkasse — Antrag auf Kindergeld (KG1)"
    # Phase F6 — KG1 is an XFA-styled PDF: its /Btn widgets are bare stubs
    # without /AP appearance dicts, which PyPDF cannot write to. The new
    # "fitz_acroform" strategy walks page-level widgets via PyMuPDF, which
    # handles both born-acroform and XFA-stub PDFs equally well.
    fill_strategy = "fitz_acroform"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        required_ok = all(p in lo for p in _REQUIRED)
        section_ok  = any(s in lo for s in _SECTION_MARKERS)
        return required_ok and section_ok

    def get_field_map(self) -> list:
        from app.services.pdf_pipeline import FieldMapEntry

        def auto(field_id, label, ftype, page, opts=None, src_text=None, condition=None):
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
                condition=condition,
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
            # Steuer-ID: ONE logical 11-digit question. The four 2/3/3/3 comb
            # widgets are filled by slicing the answer at fill time — see
            # get_split_fields(). The raw widget names never enter the question
            # flow or extracted_field_ids.
            auto(LOGICAL_APP_STEUER_ID, "Steuer-Identifikationsnummer", "text", 1,
                 src_text="Steuerliche Identifikationsnummer"),
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
                 src_text="Familienstand seit (TT.MM.JJJJ)",
                 condition=_COND_NOT_LEDIG),

            # ── Punkt 2 — Partner (Page 1) ───────────────────────────────
            # Shown only when the applicant has a current spouse / registered
            # partner (verheiratet | Lebenspartnerschaft). Single, divorced,
            # widowed and permanently-separated applicants skip this section.
            # Partner Steuer-ID is a logical split field, like the applicant's.
            auto(LOGICAL_PRT_STEUER_ID, "Steuer-Identifikationsnummer des Partners",
                 "text", 1, src_text="Steuerliche Identifikationsnummer (Partner)",
                 condition=_COND_HAS_PARTNER),
            auto(W_PRT_NAME,        "Name des Partners",       "text", 1, condition=_COND_HAS_PARTNER),
            auto(W_PRT_VORNAME,     "Vorname des Partners",    "text", 1, condition=_COND_HAS_PARTNER),
            auto(W_PRT_TITEL,       "Titel des Partners",      "text", 1, condition=_COND_HAS_PARTNER),
            auto(W_PRT_GEB_DATUM,   "Geburtsdatum des Partners","text", 1, condition=_COND_HAS_PARTNER),
            auto(W_PRT_STAATSANG,   "Staatsangehörigkeit des Partners","text", 1, condition=_COND_HAS_PARTNER),
            auto(W_PRT_GESCHLECHT,  "Geschlecht des Partners", "select", 1,
                 opts=["m", "w", "d"], condition=_COND_HAS_PARTNER),
            auto(W_PRT_GEBURTSNAME, "Geburtsname des Partners","text", 1, condition=_COND_HAS_PARTNER),
            auto(W_PRT_ANSCHRIFT,   "Anschrift des Partners",  "text", 1, condition=_COND_HAS_PARTNER),

            # ── Punkt 3 — Bankverbindung (Page 1) ────────────────────────
            auto(W_BANK_IBAN,        "IBAN",       "text", 1),
            auto(W_BANK_BIC,         "BIC",        "text", 1),
            auto(W_BANK_NAME,        "Bank",       "text", 1,
                 src_text="Name der Bank"),
            # Logical account-holder radio (covers 2 widgets)
            auto(LOGICAL_BANK_OWNER, "Kontoinhaber", "radio", 1,
                 opts=["Antragsteller", "andere Person"],
                 src_text="Kontoinhaber"),
            auto(W_BANK_OWNER_NAME,  "Name des Kontoinhabers", "text", 1,
                 condition=_COND_OTHER_ACCOUNT),

            # ── Punkt 4 — Abweichende Person (Page 2) ────────────────────
            # Shown only when the Kindergeld is paid to someone other than the
            # applicant (Kontoinhaber == "andere Person").
            auto(W_AP_NAME,      "Name der abweichenden Person",     "text", 2,
                 condition=_COND_OTHER_ACCOUNT),
            auto(W_AP_VORNAME,   "Vorname der abweichenden Person",  "text", 2,
                 condition=_COND_OTHER_ACCOUNT),
            auto(W_AP_ANSCHRIFT, "Anschrift der abweichenden Person","text", 2,
                 condition=_COND_OTHER_ACCOUNT),

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

    def get_split_fields(self) -> list[SplitField]:
        return [
            # 11-digit Steuer-ID → 4 comb widgets (2 / 3 / 3 / 3 chars).
            SplitField(
                field_id=LOGICAL_APP_STEUER_ID,
                widget_names=[
                    W_APP_STEUER_ID_1, W_APP_STEUER_ID_2,
                    W_APP_STEUER_ID_3, W_APP_STEUER_ID_4,
                ],
                slices=_STEUER_ID_SLICES,
            ),
            SplitField(
                field_id=LOGICAL_PRT_STEUER_ID,
                widget_names=[
                    W_PRT_STEUER_ID_1, W_PRT_STEUER_ID_2,
                    W_PRT_STEUER_ID_3, W_PRT_STEUER_ID_4,
                ],
                slices=_STEUER_ID_SLICES,
            ),
        ]


# ── Verified questions for all 52 shown KG1 fields ────────────────────────────
# Merged into VERIFIED_BY_FIELD_ID at module import time (see _register at bottom).
# Locales required by Phase F1 scope: en, de, fr, ar, tr, sq.

# Standard "Tabelle 1" preamble re-used in every child-row question's `help`.
_T1_PRE = {
    "en": "This section is only for children for whom you already receive Kindergeld. If this is your first Kindergeld application, you can skip these fields.",
    "de": "Dieser Abschnitt ist nur für Kinder, für die Sie bereits Kindergeld erhalten. Wenn dies Ihr erster Kindergeldantrag ist, können Sie diese Felder überspringen.",
    "fr": "Cette section concerne seulement les enfants pour lesquels vous recevez déjà le Kindergeld. Si c'est votre première demande de Kindergeld, vous pouvez ignorer ces champs.",
    "ar": "هذا القسم مخصص فقط للأطفال الذين تتلقى لهم بالفعل علاوة الأطفال (Kindergeld). إذا كان هذا هو طلبك الأول للحصول على Kindergeld، يمكنك تخطي هذه الحقول.",
    "tr": "Bu bölüm yalnızca halihazırda Kindergeld aldığınız çocuklar içindir. Bu ilk Kindergeld başvurunuzsa, bu alanları atlayabilirsiniz.",
    "sq": "Ky seksion është vetëm për fëmijët për të cilët merrni tashmë Kindergeld. Nëse kjo është aplikimi juaj i parë për Kindergeld, mund t'i kaloni këto fusha.",
}

_GESCHLECHT_FORMAT = {
    "en": "Please enter 'm' (male), 'w' (female), or 'd' (diverse).",
    "de": "Bitte 'm' für männlich, 'w' für weiblich oder 'd' für divers eintragen.",
    "fr": "Saisissez 'm' (homme), 'w' (femme) ou 'd' (divers).",
    "ar": "أدخل 'm' (ذكر) أو 'w' (أنثى) أو 'd' (متنوع).",
    "tr": "Lütfen 'm' (erkek), 'w' (kadın) veya 'd' (diğer) girin.",
    "sq": "Ju lutemi shkruani 'm' (mashkull), 'w' (femër) ose 'd' (divers).",
}

_DATE_FORMAT = {
    "en": "Format: DD.MM.YYYY",
    "de": "Format: TT.MM.JJJJ",
    "fr": "Format : JJ.MM.AAAA",
    "ar": "التنسيق: يوم.شهر.سنة",
    "tr": "Biçim: GG.AA.YYYY",
    "sq": "Formati: DD.MM.VVVV",
}


def _kind_question(idx: int, kind: str) -> dict:
    """
    Tabelle-1 child row question generator.
    `kind` is one of: 'vorname' | 'geburtsdatum' | 'geschlecht' | 'familienkasse'.
    All four versions carry the standard "already receive Kindergeld" preamble.
    """
    if kind == "vorname":
        return {
            "en": {"question": f"Child {idx} — first name (and different family name, if any)?",
                   "help": _T1_PRE["en"], "example": "Lena Müller"},
            "de": {"question": f"Kind {idx} — Vorname (und ggf. abweichender Familienname)?",
                   "help": _T1_PRE["de"], "example": "Lena Müller"},
            "fr": {"question": f"Enfant {idx} — prénom (et nom de famille différent, le cas échéant) ?",
                   "help": _T1_PRE["fr"], "example": "Lena Müller"},
            "ar": {"question": f"الطفل رقم {idx} — الاسم الأول (واسم العائلة المختلف، إن وجد)؟",
                   "help": _T1_PRE["ar"], "example": "Lena Müller"},
            "tr": {"question": f"Çocuk {idx} — adı (ve farklıysa soyadı)?",
                   "help": _T1_PRE["tr"], "example": "Lena Müller"},
            "sq": {"question": f"Fëmija {idx} — emri (dhe mbiemri tjetër nëse ka)?",
                   "help": _T1_PRE["sq"], "example": "Lena Müller"},
        }
    if kind == "geburtsdatum":
        return {
            "en": {"question": f"Child {idx} — date of birth?",
                   "help": _T1_PRE["en"], "example": "12.03.2016", "format": _DATE_FORMAT["en"]},
            "de": {"question": f"Kind {idx} — Geburtsdatum?",
                   "help": _T1_PRE["de"], "example": "12.03.2016", "format": _DATE_FORMAT["de"]},
            "fr": {"question": f"Enfant {idx} — date de naissance ?",
                   "help": _T1_PRE["fr"], "example": "12.03.2016", "format": _DATE_FORMAT["fr"]},
            "ar": {"question": f"الطفل رقم {idx} — تاريخ الميلاد؟",
                   "help": _T1_PRE["ar"], "example": "12.03.2016", "format": _DATE_FORMAT["ar"]},
            "tr": {"question": f"Çocuk {idx} — doğum tarihi?",
                   "help": _T1_PRE["tr"], "example": "12.03.2016", "format": _DATE_FORMAT["tr"]},
            "sq": {"question": f"Fëmija {idx} — data e lindjes?",
                   "help": _T1_PRE["sq"], "example": "12.03.2016", "format": _DATE_FORMAT["sq"]},
        }
    if kind == "geschlecht":
        return {
            "en": {"question": f"Child {idx} — gender?",
                   "help": _T1_PRE["en"], "example": "m", "format": _GESCHLECHT_FORMAT["en"]},
            "de": {"question": f"Kind {idx} — Geschlecht?",
                   "help": _T1_PRE["de"], "example": "w", "format": _GESCHLECHT_FORMAT["de"]},
            "fr": {"question": f"Enfant {idx} — genre ?",
                   "help": _T1_PRE["fr"], "example": "m", "format": _GESCHLECHT_FORMAT["fr"]},
            "ar": {"question": f"الطفل رقم {idx} — الجنس؟",
                   "help": _T1_PRE["ar"], "example": "w", "format": _GESCHLECHT_FORMAT["ar"]},
            "tr": {"question": f"Çocuk {idx} — cinsiyet?",
                   "help": _T1_PRE["tr"], "example": "m", "format": _GESCHLECHT_FORMAT["tr"]},
            "sq": {"question": f"Fëmija {idx} — gjinia?",
                   "help": _T1_PRE["sq"], "example": "m", "format": _GESCHLECHT_FORMAT["sq"]},
        }
    if kind == "familienkasse":
        return {
            "en": {"question": f"Child {idx} — current Familienkasse + Kindergeld number?",
                   "help": _T1_PRE["en"], "example": "Familienkasse Rostock — KG-Nr 12345BG0001234"},
            "de": {"question": f"Kind {idx} — aktuelle Familienkasse + Kindergeldnummer?",
                   "help": _T1_PRE["de"], "example": "Familienkasse Rostock — KG-Nr 12345BG0001234"},
            "fr": {"question": f"Enfant {idx} — Familienkasse actuelle + numéro Kindergeld ?",
                   "help": _T1_PRE["fr"], "example": "Familienkasse Rostock — KG-Nr 12345BG0001234"},
            "ar": {"question": f"الطفل رقم {idx} — مكتب Familienkasse الحالي + رقم Kindergeld؟",
                   "help": _T1_PRE["ar"], "example": "Familienkasse Rostock — KG-Nr 12345BG0001234"},
            "tr": {"question": f"Çocuk {idx} — mevcut Familienkasse + Kindergeld numarası?",
                   "help": _T1_PRE["tr"], "example": "Familienkasse Rostock — KG-Nr 12345BG0001234"},
            "sq": {"question": f"Fëmija {idx} — Familienkasse aktuale + numri i Kindergeld?",
                   "help": _T1_PRE["sq"], "example": "Familienkasse Rostock — KG-Nr 12345BG0001234"},
        }
    raise ValueError(f"Unknown kind: {kind!r}")


_KG1_QUESTIONS: dict = {

    # ── Header ────────────────────────────────────────────────────────────────
    W_KG_NR: {
        "en": {"question": "What is your Kindergeld reference number, if you already have one?",
               "help": "Leave blank if this is your first Kindergeld application. Otherwise copy from any previous Familienkasse letter.",
               "example": "12345BG0001234"},
        "de": {"question": "Wie lautet Ihre Kindergeld-Nummer, falls Sie bereits eine haben?",
               "help": "Bitte leer lassen, wenn dies Ihr erster Kindergeldantrag ist. Sonst von einem früheren Familienkasse-Brief übernehmen.",
               "example": "12345BG0001234"},
        "fr": {"question": "Quel est votre numéro de référence Kindergeld, si vous en avez déjà un ?",
               "help": "Laissez vide s'il s'agit de votre première demande. Sinon copiez-le depuis un courrier antérieur de la Familienkasse.",
               "example": "12345BG0001234"},
        "ar": {"question": "ما هو رقم Kindergeld الخاص بك إن وجد؟",
               "help": "اتركه فارغًا إذا كان هذا أول طلب لك. وإلا انسخه من رسالة سابقة من Familienkasse.",
               "example": "12345BG0001234"},
        "tr": {"question": "Mevcutsa Kindergeld referans numaranız nedir?",
               "help": "İlk başvurunuzsa boş bırakın. Aksi takdirde Familienkasse'den gelen önceki bir mektuptan kopyalayın.",
               "example": "12345BG0001234"},
        "sq": {"question": "Cili është numri juaj i referencës Kindergeld, nëse keni një të tillë?",
               "help": "Lëreni bosh nëse ky është aplikimi juaj i parë për Kindergeld. Përndryshe kopjojeni nga një letër e mëparshme e Familienkasse.",
               "example": "12345BG0001234"},
    },
    W_TELEFON: {
        "en": {"question": "What is your phone number for Familienkasse callbacks?",
               "help": "The Familienkasse may call you with questions about your application.",
               "example": "0151 12345678"},
        "de": {"question": "Wie lautet Ihre Telefonnummer für Rückfragen?",
               "help": "Die Familienkasse kann Sie bei Rückfragen telefonisch erreichen.",
               "example": "0151 12345678"},
        "fr": {"question": "Quel est votre numéro de téléphone pour les rappels de la Familienkasse ?",
               "help": "La Familienkasse peut vous appeler pour des questions sur votre demande.",
               "example": "0151 12345678"},
        "ar": {"question": "ما هو رقم هاتفك للاتصال من قبل Familienkasse؟",
               "help": "قد تتصل بك Familienkasse للاستفسار عن طلبك.",
               "example": "0151 12345678"},
        "tr": {"question": "Familienkasse geri arama için telefon numaranız nedir?",
               "help": "Familienkasse başvurunuz hakkında sorularla sizi arayabilir.",
               "example": "0151 12345678"},
        "sq": {"question": "Cili është numri juaj i telefonit për thirrjet e Familienkasse?",
               "help": "Familienkasse mund t'ju telefonojë për pyetje rreth aplikimit tuaj.",
               "example": "0151 12345678"},
    },
    W_ANZAHL_ANLAGEN: {
        "en": {"question": "How many 'Anlage Kind' attachments are you submitting with this application?",
               "help": "One Anlage Kind per child for whom you are NEWLY applying for Kindergeld.",
               "example": "1"},
        "de": {"question": "Wie viele Anlagen 'Kind' fügen Sie diesem Antrag bei?",
               "help": "Eine Anlage Kind pro Kind, für das Sie NEU Kindergeld beantragen.",
               "example": "1"},
        "fr": {"question": "Combien d'annexes 'Anlage Kind' joignez-vous à cette demande ?",
               "help": "Une Anlage Kind par enfant pour lequel vous demandez le Kindergeld pour la première fois.",
               "example": "1"},
        "ar": {"question": "كم عدد ملاحق 'Anlage Kind' التي ترفقها مع هذا الطلب؟",
               "help": "ملحق Anlage Kind واحد لكل طفل تتقدم بطلب جديد للحصول على Kindergeld له.",
               "example": "1"},
        "tr": {"question": "Bu başvuruya kaç 'Anlage Kind' eki gönderiyorsunuz?",
               "help": "Yeni Kindergeld başvurusunda bulunduğunuz her çocuk için bir Anlage Kind.",
               "example": "1"},
        "sq": {"question": "Sa shtojca 'Anlage Kind' po dërgoni me këtë aplikim?",
               "help": "Një Anlage Kind për çdo fëmijë për të cilin po aplikoni për herë të parë për Kindergeld.",
               "example": "1"},
    },

    # ── Punkt 1 — Antragsteller ───────────────────────────────────────────────
    LOGICAL_APP_STEUER_ID: {
        "en": {"question": "What is your tax identification number (Steuer-Identifikationsnummer)?",
               "help": "It has 11 digits. You find it on letters from the Finanzamt or on the 'Bescheinigung über die Identifikationsnummer'. Enter the digits only.",
               "example": "12 345 678 901"},
        "de": {"question": "Wie lautet Ihre steuerliche Identifikationsnummer?",
               "help": "Sie besteht aus 11 Ziffern. Sie finden sie in Schreiben des Finanzamts oder auf der 'Bescheinigung über die Identifikationsnummer'. Geben Sie nur die Ziffern ein.",
               "example": "12 345 678 901"},
        "fr": {"question": "Quel est votre numéro d'identification fiscale (Steuer-Identifikationsnummer) ?",
               "help": "Il comporte 11 chiffres. Vous le trouverez sur les courriers du Finanzamt. Saisissez uniquement les chiffres.",
               "example": "12 345 678 901"},
        "ar": {"question": "ما هو رقم التعريف الضريبي الخاص بك (Steuer-Identifikationsnummer)؟",
               "help": "يتكون من 11 رقمًا. تجده في الرسائل الواردة من مكتب الضرائب (Finanzamt). أدخل الأرقام فقط.",
               "example": "12 345 678 901"},
        "tr": {"question": "Vergi kimlik numaranız (Steuer-Identifikationsnummer) nedir?",
               "help": "11 hanelidir. Finanzamt'tan gelen mektuplarda bulabilirsiniz. Yalnızca rakamları girin.",
               "example": "12 345 678 901"},
        "sq": {"question": "Cili është numri juaj i identifikimit tatimor (Steuer-Identifikationsnummer)?",
               "help": "Ka 11 shifra. E gjeni në letrat nga Finanzamt. Shkruani vetëm shifrat.",
               "example": "12 345 678 901"},
    },
    W_APP_TITEL: {
        "en": {"question": "Your academic title (if any)?", "help": "Optional. Examples: Dr., Prof.", "example": "Dr."},
        "de": {"question": "Ihr akademischer Titel (falls vorhanden)?", "help": "Optional. Beispiele: Dr., Prof.", "example": "Dr."},
        "fr": {"question": "Votre titre universitaire (le cas échéant) ?", "help": "Facultatif.", "example": "Dr."},
        "ar": {"question": "لقبك الأكاديمي (إن وجد)؟", "help": "اختياري.", "example": "Dr."},
        "tr": {"question": "Akademik unvanınız (varsa)?", "help": "İsteğe bağlı.", "example": "Dr."},
        "sq": {"question": "Titulli juaj akademik (nëse ka)?", "help": "Opsional.", "example": "Dr."},
    },
    W_APP_NAME: {
        "en": {"question": "What is your family name?", "example": "Müller"},
        "de": {"question": "Wie lautet Ihr Familienname?", "example": "Müller"},
        "fr": {"question": "Quel est votre nom de famille ?", "example": "Müller"},
        "ar": {"question": "ما هو اسم عائلتك؟", "example": "Müller"},
        "tr": {"question": "Soyadınız nedir?", "example": "Müller"},
        "sq": {"question": "Cili është mbiemri juaj?", "example": "Müller"},
    },
    W_APP_VORNAME: {
        "en": {"question": "What is your first name?", "example": "Anna"},
        "de": {"question": "Wie lautet Ihr Vorname?", "example": "Anna"},
        "fr": {"question": "Quel est votre prénom ?", "example": "Anna"},
        "ar": {"question": "ما هو اسمك الأول؟", "example": "Anna"},
        "tr": {"question": "Adınız nedir?", "example": "Anna"},
        "sq": {"question": "Cili është emri juaj?", "example": "Anna"},
    },
    W_APP_GEBURTSNAME: {
        "en": {"question": "What is your birth name (only if different from your current family name)?",
               "help": "Maiden name or earlier family name. Leave blank if unchanged."},
        "de": {"question": "Wie lautet Ihr Geburtsname (nur falls abweichend vom heutigen Familiennamen)?",
               "help": "Mädchenname oder früherer Familienname. Leer lassen, wenn unverändert."},
        "fr": {"question": "Quel est votre nom de naissance (uniquement s'il diffère du nom actuel) ?",
               "help": "Nom de jeune fille ou ancien nom. Laissez vide si inchangé."},
        "ar": {"question": "ما هو اسمك عند الولادة (فقط إذا كان مختلفًا عن اسمك الحالي)؟",
               "help": "اتركه فارغًا إذا لم يتغير."},
        "tr": {"question": "Doğum soyadınız nedir (yalnızca mevcut soyadınızdan farklıysa)?",
               "help": "Değişmediyse boş bırakın."},
        "sq": {"question": "Cili është mbiemri juaj i lindjes (vetëm nëse ndryshon nga mbiemri aktual)?",
               "help": "Lëreni bosh nëse nuk ka ndryshuar."},
    },
    W_APP_GEB_DATUM: {
        "en": {"question": "What is your date of birth?", "example": "15.03.1985", "format": _DATE_FORMAT["en"]},
        "de": {"question": "Wie lautet Ihr Geburtsdatum?", "example": "15.03.1985", "format": _DATE_FORMAT["de"]},
        "fr": {"question": "Quelle est votre date de naissance ?", "example": "15.03.1985", "format": _DATE_FORMAT["fr"]},
        "ar": {"question": "ما هو تاريخ ميلادك؟", "example": "15.03.1985", "format": _DATE_FORMAT["ar"]},
        "tr": {"question": "Doğum tarihiniz nedir?", "example": "15.03.1985", "format": _DATE_FORMAT["tr"]},
        "sq": {"question": "Cila është data juaj e lindjes?", "example": "15.03.1985", "format": _DATE_FORMAT["sq"]},
    },
    W_APP_GEB_ORT: {
        "en": {"question": "What is your place of birth?", "example": "Damascus"},
        "de": {"question": "Wie lautet Ihr Geburtsort?", "example": "Damaskus"},
        "fr": {"question": "Quel est votre lieu de naissance ?", "example": "Damas"},
        "ar": {"question": "ما هو مكان ولادتك؟", "example": "دمشق"},
        "tr": {"question": "Doğum yeriniz nedir?", "example": "Şam"},
        "sq": {"question": "Cili është vendi juaj i lindjes?", "example": "Damask"},
    },
    W_APP_GESCHLECHT: {
        "en": {"question": "What is your gender?", "example": "w", "format": _GESCHLECHT_FORMAT["en"]},
        "de": {"question": "Welches Geschlecht haben Sie?", "example": "w", "format": _GESCHLECHT_FORMAT["de"]},
        "fr": {"question": "Quel est votre genre ?", "example": "w", "format": _GESCHLECHT_FORMAT["fr"]},
        "ar": {"question": "ما هو جنسك؟", "example": "w", "format": _GESCHLECHT_FORMAT["ar"]},
        "tr": {"question": "Cinsiyetiniz nedir?", "example": "w", "format": _GESCHLECHT_FORMAT["tr"]},
        "sq": {"question": "Cili është gjinia juaj?", "example": "w", "format": _GESCHLECHT_FORMAT["sq"]},
    },
    W_APP_STAATSANG: {
        "en": {"question": "What is your nationality?", "example": "Syrian"},
        "de": {"question": "Welche Staatsangehörigkeit haben Sie?", "example": "syrisch"},
        "fr": {"question": "Quelle est votre nationalité ?", "example": "syrienne"},
        "ar": {"question": "ما هي جنسيتك؟", "example": "سورية"},
        "tr": {"question": "Uyruğunuz nedir?", "example": "Suriye"},
        "sq": {"question": "Cila është shtetësia juaj?", "example": "Siriane"},
    },
    W_APP_ANSCHRIFT: {
        "en": {"question": "What is your address (street, house number, postal code, city)?",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "de": {"question": "Wie lautet Ihre Anschrift (Straße, Hausnummer, PLZ, Ort)?",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "fr": {"question": "Quelle est votre adresse (rue, numéro, code postal, ville) ?",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "ar": {"question": "ما هو عنوانك (الشارع، رقم المنزل، الرمز البريدي، المدينة)؟",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "tr": {"question": "Adresiniz nedir (sokak, kapı numarası, posta kodu, şehir)?",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "sq": {"question": "Cila është adresa juaj (rruga, numri, kodi postar, qyteti)?",
               "example": "Hauptstraße 12, 18055 Rostock"},
    },

    # ── Familienstand (logical radio + "seit" date) ──────────────────────────
    LOGICAL_FAMILIENSTAND: {
        "en": {"question": "What is your marital status?",
               "help": "Choose the option that matches your status today."},
        "de": {"question": "Wie ist Ihr Familienstand?",
               "help": "Wählen Sie die Option, die Ihrem heutigen Status entspricht."},
        "fr": {"question": "Quelle est votre situation familiale ?",
               "help": "Choisissez l'option qui correspond à votre statut actuel."},
        "ar": {"question": "ما هي حالتك الاجتماعية؟",
               "help": "اختر الخيار الذي يتوافق مع وضعك الحالي."},
        "tr": {"question": "Medeni durumunuz nedir?",
               "help": "Bugünkü durumunuza uygun seçeneği seçin."},
        "sq": {"question": "Cila është gjendja juaj civile?",
               "help": "Zgjidhni opsionin që përputhet me statusin tuaj sot."},
    },
    W_FS_SEIT: {
        "en": {"question": "Since when has your current marital status applied?",
               "example": "01.06.2020", "format": _DATE_FORMAT["en"]},
        "de": {"question": "Seit wann besteht Ihr derzeitiger Familienstand?",
               "example": "01.06.2020", "format": _DATE_FORMAT["de"]},
        "fr": {"question": "Depuis quand votre situation familiale actuelle s'applique-t-elle ?",
               "example": "01.06.2020", "format": _DATE_FORMAT["fr"]},
        "ar": {"question": "منذ متى تنطبق حالتك الاجتماعية الحالية؟",
               "example": "01.06.2020", "format": _DATE_FORMAT["ar"]},
        "tr": {"question": "Mevcut medeni durumunuz ne zamandan beri geçerli?",
               "example": "01.06.2020", "format": _DATE_FORMAT["tr"]},
        "sq": {"question": "Që kur është aktuale gjendja juaj civile?",
               "example": "01.06.2020", "format": _DATE_FORMAT["sq"]},
    },

    # ── Punkt 2 — Partner ─────────────────────────────────────────────────────
    LOGICAL_PRT_STEUER_ID: {
        "en": {"question": "What is your partner's tax identification number (Steuer-Identifikationsnummer)?",
               "help": "It has 11 digits. Found on letters from the Finanzamt addressed to your partner. Enter the digits only.",
               "example": "12 345 678 901"},
        "de": {"question": "Wie lautet die steuerliche Identifikationsnummer Ihres Partners / Ihrer Partnerin?",
               "help": "Sie besteht aus 11 Ziffern. Zu finden in Schreiben des Finanzamts an Ihren Partner. Nur die Ziffern eingeben.",
               "example": "12 345 678 901"},
        "fr": {"question": "Quel est le numéro d'identification fiscale de votre partenaire ?",
               "help": "Il comporte 11 chiffres. Saisissez uniquement les chiffres.",
               "example": "12 345 678 901"},
        "ar": {"question": "ما هو رقم التعريف الضريبي لشريكك (Steuer-Identifikationsnummer)؟",
               "help": "يتكون من 11 رقمًا. أدخل الأرقام فقط.",
               "example": "12 345 678 901"},
        "tr": {"question": "Eşinizin/partnerinizin vergi kimlik numarası nedir?",
               "help": "11 hanelidir. Yalnızca rakamları girin.",
               "example": "12 345 678 901"},
        "sq": {"question": "Cili është numri i identifikimit tatimor i partnerit/partneres suaj?",
               "help": "Ka 11 shifra. Shkruani vetëm shifrat.",
               "example": "12 345 678 901"},
    },
    W_PRT_NAME: {
        "en": {"question": "What is your partner's family name?", "example": "Müller"},
        "de": {"question": "Wie lautet der Familienname Ihres Partners / Ihrer Partnerin?", "example": "Müller"},
        "fr": {"question": "Quel est le nom de famille de votre partenaire ?", "example": "Müller"},
        "ar": {"question": "ما هو اسم عائلة شريكك؟", "example": "Müller"},
        "tr": {"question": "Eşinizin/partnerinizin soyadı nedir?", "example": "Müller"},
        "sq": {"question": "Cili është mbiemri i partnerit/partneres suaj?", "example": "Müller"},
    },
    W_PRT_VORNAME: {
        "en": {"question": "What is your partner's first name?", "example": "Markus"},
        "de": {"question": "Wie lautet der Vorname Ihres Partners / Ihrer Partnerin?", "example": "Markus"},
        "fr": {"question": "Quel est le prénom de votre partenaire ?", "example": "Markus"},
        "ar": {"question": "ما هو الاسم الأول لشريكك؟", "example": "Markus"},
        "tr": {"question": "Eşinizin/partnerinizin adı nedir?", "example": "Markus"},
        "sq": {"question": "Cili është emri i partnerit/partneres suaj?", "example": "Markus"},
    },
    W_PRT_TITEL: {
        "en": {"question": "Partner's academic title (if any)?", "help": "Optional.", "example": "Dr."},
        "de": {"question": "Akademischer Titel des Partners (falls vorhanden)?", "help": "Optional.", "example": "Dr."},
        "fr": {"question": "Titre universitaire du partenaire (le cas échéant) ?", "help": "Facultatif.", "example": "Dr."},
        "ar": {"question": "اللقب الأكاديمي للشريك (إن وجد)؟", "help": "اختياري.", "example": "Dr."},
        "tr": {"question": "Eşin/partnerin akademik unvanı (varsa)?", "help": "İsteğe bağlı.", "example": "Dr."},
        "sq": {"question": "Titulli akademik i partnerit (nëse ka)?", "help": "Opsional.", "example": "Dr."},
    },
    W_PRT_GEB_DATUM: {
        "en": {"question": "Partner's date of birth?", "example": "20.07.1983", "format": _DATE_FORMAT["en"]},
        "de": {"question": "Geburtsdatum des Partners / der Partnerin?", "example": "20.07.1983", "format": _DATE_FORMAT["de"]},
        "fr": {"question": "Date de naissance du partenaire ?", "example": "20.07.1983", "format": _DATE_FORMAT["fr"]},
        "ar": {"question": "تاريخ ميلاد الشريك؟", "example": "20.07.1983", "format": _DATE_FORMAT["ar"]},
        "tr": {"question": "Eşin/partnerin doğum tarihi?", "example": "20.07.1983", "format": _DATE_FORMAT["tr"]},
        "sq": {"question": "Data e lindjes së partnerit/partneres?", "example": "20.07.1983", "format": _DATE_FORMAT["sq"]},
    },
    W_PRT_STAATSANG: {
        "en": {"question": "Partner's nationality?", "example": "German"},
        "de": {"question": "Staatsangehörigkeit des Partners / der Partnerin?", "example": "deutsch"},
        "fr": {"question": "Nationalité du partenaire ?", "example": "allemande"},
        "ar": {"question": "جنسية الشريك؟", "example": "ألمانية"},
        "tr": {"question": "Eşin/partnerin uyruğu?", "example": "Alman"},
        "sq": {"question": "Shtetësia e partnerit/partneres?", "example": "Gjermane"},
    },
    W_PRT_GESCHLECHT: {
        "en": {"question": "Partner's gender?", "example": "m", "format": _GESCHLECHT_FORMAT["en"]},
        "de": {"question": "Geschlecht des Partners / der Partnerin?", "example": "m", "format": _GESCHLECHT_FORMAT["de"]},
        "fr": {"question": "Genre du partenaire ?", "example": "m", "format": _GESCHLECHT_FORMAT["fr"]},
        "ar": {"question": "جنس الشريك؟", "example": "m", "format": _GESCHLECHT_FORMAT["ar"]},
        "tr": {"question": "Eşin/partnerin cinsiyeti?", "example": "m", "format": _GESCHLECHT_FORMAT["tr"]},
        "sq": {"question": "Gjinia e partnerit/partneres?", "example": "m", "format": _GESCHLECHT_FORMAT["sq"]},
    },
    W_PRT_GEBURTSNAME: {
        "en": {"question": "Partner's birth name (only if different from current family name)?", "help": "Leave blank if unchanged."},
        "de": {"question": "Geburtsname des Partners (nur falls abweichend)?", "help": "Leer lassen, wenn unverändert."},
        "fr": {"question": "Nom de naissance du partenaire (uniquement s'il diffère) ?", "help": "Laissez vide si inchangé."},
        "ar": {"question": "اسم الشريك عند الولادة (فقط إذا اختلف)؟", "help": "اتركه فارغًا إذا لم يتغير."},
        "tr": {"question": "Eşin/partnerin doğum soyadı (yalnızca farklıysa)?", "help": "Değişmediyse boş bırakın."},
        "sq": {"question": "Mbiemri i lindjes së partnerit (vetëm nëse ndryshon)?", "help": "Lëreni bosh nëse nuk ka ndryshuar."},
    },
    W_PRT_ANSCHRIFT: {
        "en": {"question": "Partner's address (only if different from yours)?", "help": "Leave blank if you live at the same address.",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "de": {"question": "Anschrift des Partners (nur falls abweichend von Ihrer)?", "help": "Leer lassen, wenn dieselbe Adresse.",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "fr": {"question": "Adresse du partenaire (uniquement si différente de la vôtre) ?", "help": "Laissez vide si vous vivez à la même adresse.",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "ar": {"question": "عنوان الشريك (فقط إذا اختلف عن عنوانك)؟", "help": "اتركه فارغًا إذا كنتم تعيشون في نفس العنوان.",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "tr": {"question": "Eşin/partnerin adresi (yalnızca sizinkinden farklıysa)?", "help": "Aynı adreste yaşıyorsanız boş bırakın.",
               "example": "Hauptstraße 12, 18055 Rostock"},
        "sq": {"question": "Adresa e partnerit (vetëm nëse ndryshon nga e juaja)?", "help": "Lëreni bosh nëse jetoni në të njëjtën adresë.",
               "example": "Hauptstraße 12, 18055 Rostock"},
    },

    # ── Punkt 3 — Bankverbindung ──────────────────────────────────────────────
    W_BANK_IBAN: {
        "en": {"question": "What is your bank account IBAN?",
               "help": "Find it at the top of your bank statement or in your banking app.",
               "example": "DE89 3704 0044 0532 0130 00"},
        "de": {"question": "Wie lautet die IBAN Ihres Bankkontos?",
               "help": "Sie finden sie oben auf Ihrem Kontoauszug oder in Ihrer Banking-App.",
               "example": "DE89 3704 0044 0532 0130 00"},
        "fr": {"question": "Quel est l'IBAN de votre compte bancaire ?",
               "help": "Vous le trouverez en haut de votre relevé bancaire ou dans votre application bancaire.",
               "example": "DE89 3704 0044 0532 0130 00"},
        "ar": {"question": "ما هو رقم IBAN لحسابك المصرفي؟",
               "help": "ستجده في أعلى كشف الحساب البنكي أو في تطبيق البنك.",
               "example": "DE89 3704 0044 0532 0130 00"},
        "tr": {"question": "Banka hesabınızın IBAN numarası nedir?",
               "help": "Hesap özetinizin üstünde veya bankacılık uygulamanızda bulabilirsiniz.",
               "example": "DE89 3704 0044 0532 0130 00"},
        "sq": {"question": "Cili është IBAN-i i llogarisë suaj bankare?",
               "help": "E gjeni në krye të deklaratës bankare ose në aplikacionin tuaj bankar.",
               "example": "DE89 3704 0044 0532 0130 00"},
    },
    W_BANK_BIC: {
        "en": {"question": "What is the BIC of your bank?",
               "help": "Sometimes called SWIFT code.", "example": "COBADEFFXXX"},
        "de": {"question": "Wie lautet die BIC Ihrer Bank?",
               "help": "Auch SWIFT-Code genannt.", "example": "COBADEFFXXX"},
        "fr": {"question": "Quel est le BIC de votre banque ?",
               "help": "Aussi appelé code SWIFT.", "example": "COBADEFFXXX"},
        "ar": {"question": "ما هو رمز BIC لبنكك؟",
               "help": "يُسمى أيضًا رمز SWIFT.", "example": "COBADEFFXXX"},
        "tr": {"question": "Bankanızın BIC numarası nedir?",
               "help": "SWIFT kodu olarak da bilinir.", "example": "COBADEFFXXX"},
        "sq": {"question": "Cili është BIC-i i bankës suaj?",
               "help": "Gjithashtu i njohur si kodi SWIFT.", "example": "COBADEFFXXX"},
    },
    W_BANK_NAME: {
        "en": {"question": "What is the name of your bank?", "example": "Commerzbank"},
        "de": {"question": "Wie heißt Ihre Bank?",            "example": "Commerzbank"},
        "fr": {"question": "Quel est le nom de votre banque ?", "example": "Commerzbank"},
        "ar": {"question": "ما هو اسم بنكك؟",                  "example": "Commerzbank"},
        "tr": {"question": "Bankanızın adı nedir?",            "example": "Commerzbank"},
        "sq": {"question": "Cili është emri i bankës suaj?",   "example": "Commerzbank"},
    },
    LOGICAL_BANK_OWNER: {
        "en": {"question": "Who is the holder of the bank account where the Kindergeld should be paid?",
               "help": "Choose 'Antragsteller' if it is your own account; choose 'andere Person' if the account belongs to someone else (you'll then describe that person below)."},
        "de": {"question": "Wer ist der Inhaber des Bankkontos, auf das das Kindergeld überwiesen werden soll?",
               "help": "Wählen Sie 'Antragsteller', wenn es Ihr eigenes Konto ist; wählen Sie 'andere Person', wenn das Konto einer anderen Person gehört (diese Person wird dann unten angegeben)."},
        "fr": {"question": "Qui est le titulaire du compte bancaire sur lequel le Kindergeld doit être versé ?",
               "help": "Choisissez 'Antragsteller' s'il s'agit de votre propre compte ; choisissez 'andere Person' si le compte appartient à quelqu'un d'autre (à décrire ci-dessous)."},
        "ar": {"question": "من هو صاحب الحساب المصرفي الذي يجب أن يُصرف فيه Kindergeld؟",
               "help": "اختر 'Antragsteller' إذا كان حسابك الخاص؛ اختر 'andere Person' إذا كان الحساب يخص شخصًا آخر."},
        "tr": {"question": "Kindergeld'in yatırılacağı banka hesabının sahibi kimdir?",
               "help": "Kendi hesabınızsa 'Antragsteller'i seçin; başka bir kişinin hesabıysa 'andere Person'u seçin."},
        "sq": {"question": "Kush është mbajtësi i llogarisë bankare ku duhet të paguhet Kindergeld?",
               "help": "Zgjidhni 'Antragsteller' nëse është llogaria juaj; zgjidhni 'andere Person' nëse llogaria i përket dikujt tjetër."},
    },
    W_BANK_OWNER_NAME: {
        "en": {"question": "Name of the bank account holder?",
               "help": "Exactly as it appears on the bank statement.", "example": "Anna Müller"},
        "de": {"question": "Name des Kontoinhabers?",
               "help": "Genau wie auf dem Kontoauszug.", "example": "Anna Müller"},
        "fr": {"question": "Nom du titulaire du compte bancaire ?",
               "help": "Exactement comme indiqué sur le relevé.", "example": "Anna Müller"},
        "ar": {"question": "اسم صاحب الحساب المصرفي؟",
               "help": "تمامًا كما يظهر في كشف الحساب.", "example": "Anna Müller"},
        "tr": {"question": "Banka hesap sahibinin adı?",
               "help": "Hesap özetinde göründüğü gibi.", "example": "Anna Müller"},
        "sq": {"question": "Emri i mbajtësit të llogarisë bankare?",
               "help": "Saktësisht siç shfaqet në deklaratën bankare.", "example": "Anna Müller"},
    },

    # ── Punkt 4 — Abweichende Person (only if Punkt 3 said "andere Person") ──
    W_AP_NAME: {
        "en": {"question": "Family name of the alternative account holder?",
               "help": "Only fill this if you chose 'andere Person' for the bank account holder above.", "example": "Schmidt"},
        "de": {"question": "Familienname der abweichenden Person?",
               "help": "Nur ausfüllen, wenn Sie oben 'andere Person' als Kontoinhaber gewählt haben.", "example": "Schmidt"},
        "fr": {"question": "Nom de famille du titulaire du compte alternatif ?",
               "help": "À remplir uniquement si vous avez choisi 'andere Person' ci-dessus.", "example": "Schmidt"},
        "ar": {"question": "اسم عائلة صاحب الحساب البديل؟",
               "help": "املأ هذا فقط إذا اخترت 'andere Person' أعلاه.", "example": "Schmidt"},
        "tr": {"question": "Alternatif hesap sahibinin soyadı?",
               "help": "Yalnızca yukarıda 'andere Person'u seçtiyseniz doldurun.", "example": "Schmidt"},
        "sq": {"question": "Mbiemri i mbajtësit alternativ të llogarisë?",
               "help": "Plotësoni vetëm nëse keni zgjedhur 'andere Person' më lart.", "example": "Schmidt"},
    },
    W_AP_VORNAME: {
        "en": {"question": "First name of the alternative account holder?", "example": "Klaus"},
        "de": {"question": "Vorname der abweichenden Person?",              "example": "Klaus"},
        "fr": {"question": "Prénom du titulaire du compte alternatif ?",    "example": "Klaus"},
        "ar": {"question": "الاسم الأول لصاحب الحساب البديل؟",              "example": "Klaus"},
        "tr": {"question": "Alternatif hesap sahibinin adı?",               "example": "Klaus"},
        "sq": {"question": "Emri i mbajtësit alternativ të llogarisë?",     "example": "Klaus"},
    },
    W_AP_ANSCHRIFT: {
        "en": {"question": "Address of the alternative account holder?",
               "example": "Bahnhofstraße 5, 18055 Rostock"},
        "de": {"question": "Anschrift der abweichenden Person?",
               "example": "Bahnhofstraße 5, 18055 Rostock"},
        "fr": {"question": "Adresse du titulaire du compte alternatif ?",
               "example": "Bahnhofstraße 5, 18055 Rostock"},
        "ar": {"question": "عنوان صاحب الحساب البديل؟",
               "example": "Bahnhofstraße 5, 18055 Rostock"},
        "tr": {"question": "Alternatif hesap sahibinin adresi?",
               "example": "Bahnhofstraße 5, 18055 Rostock"},
        "sq": {"question": "Adresa e mbajtësit alternativ të llogarisë?",
               "example": "Bahnhofstraße 5, 18055 Rostock"},
    },

    # ── Punkt 5 — Tabelle 1 Kinder (5 rows × 4 cols) ─────────────────────────
    # Generated below using _kind_question(); inserted into _KG1_QUESTIONS by _build_table1().

    # ── Unterschrift dates ────────────────────────────────────────────────────
    W_DATUM_1: {
        "en": {"question": "What is today's date for your signature?", "example": "08.05.2026", "format": _DATE_FORMAT["en"]},
        "de": {"question": "Welches Datum tragen Sie bei Ihrer Unterschrift ein?", "example": "08.05.2026", "format": _DATE_FORMAT["de"]},
        "fr": {"question": "Quelle est la date d'aujourd'hui pour votre signature ?", "example": "08.05.2026", "format": _DATE_FORMAT["fr"]},
        "ar": {"question": "ما هو تاريخ اليوم بجانب توقيعك؟", "example": "08.05.2026", "format": _DATE_FORMAT["ar"]},
        "tr": {"question": "İmzanız için bugünün tarihi nedir?", "example": "08.05.2026", "format": _DATE_FORMAT["tr"]},
        "sq": {"question": "Cila është data e sotme për nënshkrimin tuaj?", "example": "08.05.2026", "format": _DATE_FORMAT["sq"]},
    },
    W_DATUM_2: {
        "en": {"question": "Date for the second signature (if applicable, e.g. partner)?",
               "help": "Leave blank if no second signature is required.",
               "example": "08.05.2026", "format": _DATE_FORMAT["en"]},
        "de": {"question": "Datum für die zweite Unterschrift (falls zutreffend, z.B. Partner)?",
               "help": "Leer lassen, wenn keine zweite Unterschrift erforderlich ist.",
               "example": "08.05.2026", "format": _DATE_FORMAT["de"]},
        "fr": {"question": "Date pour la deuxième signature (le cas échéant, par ex. partenaire) ?",
               "help": "Laissez vide si aucune deuxième signature n'est requise.",
               "example": "08.05.2026", "format": _DATE_FORMAT["fr"]},
        "ar": {"question": "تاريخ التوقيع الثاني (إن وجد، مثلاً الشريك)؟",
               "help": "اتركه فارغًا إذا لم يكن مطلوبًا توقيع ثانٍ.",
               "example": "08.05.2026", "format": _DATE_FORMAT["ar"]},
        "tr": {"question": "İkinci imza için tarih (varsa, örn. eş)?",
               "help": "İkinci imza gerekmiyorsa boş bırakın.",
               "example": "08.05.2026", "format": _DATE_FORMAT["tr"]},
        "sq": {"question": "Data për nënshkrimin e dytë (nëse aplikohet, p.sh. partneri)?",
               "help": "Lëreni bosh nëse nuk kërkohet nënshkrim i dytë.",
               "example": "08.05.2026", "format": _DATE_FORMAT["sq"]},
    },
}


# Generate the 20 Tabelle-1 entries programmatically.
for _row in (1, 2, 3, 4, 5):
    _KG1_QUESTIONS[_w_t1(_row, 1)] = _kind_question(_row, "vorname")
    _KG1_QUESTIONS[_w_t1(_row, 2)] = _kind_question(_row, "geburtsdatum")
    _KG1_QUESTIONS[_w_t1(_row, 3)] = _kind_question(_row, "geschlecht")
    _KG1_QUESTIONS[_w_t1(_row, 4)] = _kind_question(_row, "familienkasse")


def _register_kg1_verified_questions() -> None:
    """
    Merge KG1 verified questions into the global VERIFIED_BY_FIELD_ID dict.
    Runs once, at module import time (which happens lazily inside
    `form_templates._all_templates()` — well before validate_template()).
    """
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    VERIFIED_BY_FIELD_ID.update(_KG1_QUESTIONS)


_register_kg1_verified_questions()
