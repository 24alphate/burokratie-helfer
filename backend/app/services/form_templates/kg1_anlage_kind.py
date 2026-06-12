"""
Verified field map for the Familienkasse "Anlage Kind" (KG 1 AnK).

Third Level 1 verified template. One Anlage Kind must be filled per child for
every Kindergeld application, so this is the natural companion to the KG1
template (familienkasse_kg1.py). Uses the same fitz_acroform fill path —
the form comes from the same XFA generator as KG1 (topmostSubform[0]…,
/Btn stubs without /AP).

Source PDF
----------
templates_source/incoming/kg1_anlage_kind.pdf
(official: arbeitsagentur.de/datei/kg1-anlagekind_ba033765.pdf, Stand 09/2025)

Fingerprint
-----------
Required phrases (all): "kg 1 ank" (the page footer — unique to this form),
"anlage kind", "kindschaftsverhältnis". The full KG1 contains the latter two
but never the "KG 1 AnK" footer, and the KiZ Anlage Kind contains none of
the last two — verified empirically against all forms in
templates_source/incoming/.

Field strategy (v1)
-------------------
- Auto-fill (confidence=1.0): 89 logical questions — header (4), child
  data incl. one logical 11-digit Steuer-ID split question (11),
  3 kinship radio questions covering the 15-checkbox matrix (3), other-person
  block (6, gated), adult-child section 3.1–3.3 (gated on the activity
  checkboxes), Fragen 4–7 yes/no blocks with gated detail fields, signature
  date (1).
- Manual (confidence=0.5): 9 widgets — the rarely-used second education rows
  (3.1.1 row 2, sonstige row 2) and the third-job block (weitere
  Erwerbstätigkeit).
- Excluded: 3 pushbuttons (Speichern/Drucken/Alle löschen) — never in the map.

Logical mechanisms
------------------
- SplitField: child Steuer-ID → 4 comb widgets (2/3/3/3 chars, sum 11).
- RadioGroup ×14: 3 kinship rows (5 options each + "keine Angabe" which maps
  to no widget → all boxes stay off) and 11 ja/nein question pairs.
- Conditions: same field_equals / field_in / or schema as KG1; evaluated
  client-side (frontend lib/conditions.ts) and re-applied at fill time.

Every shown field has a verified question in en/de/fr/ar/tr/sq.
weak_questions=0 and ai_calls_made=0 invariants must hold.
"""
from __future__ import annotations

from app.services.form_templates import RadioGroup, SplitField, VerifiedTemplate


# ── Widget name constants (fully-qualified XFA paths; match fitz field_name) ──
# NOTE: several name components contain a literal backslash-dot ("\.") — the
# XFA escape for a dot inside a name part. "\\." in this source = "\." in the
# actual string. Umlauts are real characters in the names.

_P1 = "topmostSubform[0].Page1[0]"
_P2 = "topmostSubform[0].Page2[0]"
_P3 = "topmostSubform[0].Page3[0]"
_P4 = "topmostSubform[0].Page4[0]"

# Header
W_KG_NR      = _P1 + ".Kopfzeile[0].Kopfangaben[0].KG-Nr[0]"
W_NAME_KGB   = _P1 + ".Kopfzeile[0].Kopfangaben[0].Name_Vorname_KGB[0]"
W_ANTRAG_VOM = _P1 + ".Kopfzeile[0].Überschrift[0].zum-Antrag-vom[0]"
W_LFD_NR     = _P1 + ".Kopfzeile[0].Überschrift[0].lfd-Nr[0]"

# Punkt 1 — Angaben zum Kind
W_STEUER_1 = _P1 + ".Frage-1[0].Steuer-ID[0].Steuer-ID-1[0]"
W_STEUER_2 = _P1 + ".Frage-1[0].Steuer-ID[0].Steuer-ID-2[0]"
W_STEUER_3 = _P1 + ".Frage-1[0].Steuer-ID[0].Steuer-ID-3[0]"
W_STEUER_4 = _P1 + ".Frage-1[0].Steuer-ID[0].Steuer-ID-4[0]"
W_CHILD_NAME       = _P1 + ".Frage-1[0].Pkt-1-Zeile-2[0].Familienname-Kind[0]"
W_CHILD_TITEL      = _P1 + ".Frage-1[0].Pkt-1-Zeile-2[0].Titel[0]"
W_CHILD_VORNAME    = _P1 + ".Frage-1[0].Pkt-1-Zeile-3[0].Vorname-Kind[0]"
W_CHILD_GEBNAME    = _P1 + ".Frage-1[0].Pkt-1-Zeile-3[0].Geburtsname-Kind[0]"
W_CHILD_GEBDATUM   = _P1 + ".Frage-1[0].Pkt-1-Zeile-4[0].Geburtsdatum[0]"
W_CHILD_GEBORT     = _P1 + ".Frage-1[0].Pkt-1-Zeile-4[0].Geburtsort-Kind[0]"
W_CHILD_GESCHLECHT = _P1 + ".Frage-1[0].Pkt-1-Zeile-4[0].Geschlecht[0]"
W_CHILD_STAATSANG  = _P1 + ".Frage-1[0].Pkt-1-Zeile-4[0].Staatsangehörigkeit[0]"
W_CHILD_ANSCHRIFT  = _P1 + ".Frage-1[0].Anschrift-Kind[0]"
W_CHILD_ABW_GRUND  = _P1 + ".Frage-1[0].Grund-abw-Anschrift[0]"

# Punkt 2 — Kindschaftsverhältnis matrix (rows × relationship columns).
# Zeile1 = applicant | Zeile2 = spouse/partner | Zeile4 = other person.
# Zelle2..6 = leiblich | Adoptiv | Pflege | Stief | Enkel.
_KV = _P1 + ".Frage-2[0].#area[10].Kindschaftsverhältnis[0]"


def _kv(zeile: int, zelle: int) -> str:
    return f"{_KV}.Zeile{zeile}[0].Zelle{zelle}[0]"


# Punkt 2 — Angaben zur anderen Person
_AP = _P1 + ".Frage-2[0].Angaben-and-Person[0]"
W_AP_NAME      = _AP + ".Name-and-Person[0]"
W_AP_VORNAME   = _AP + ".Vorname-and-Person[0]"
W_AP_GEBDATUM  = _AP + ".Geburtsdatum-and-Person[0]"
W_AP_ANSCHRIFT = _AP + ".Anschrift-and-Person[0]"
W_AP_STAATSANG = _AP + ".Staatsangeh-and-Person[0]"
W_AP_ZUSATZ    = _AP + ".Zusatzang-and-Peson[0]"   # sic — typo is in the PDF

# Punkt 3 — Nachweise
W_NACHW_BEI  = _P2 + ".Nachweise-zu-3[0].beigefügt[0]"
W_NACHW_VOR  = _P2 + ".Nachweise-zu-3[0].liegen-vor[0]"
W_NACHW_NACH = _P2 + ".Nachweise-zu-3[0].werden-nachgereicht[0]"

# Punkt 3.1 — activities of an adult child
_F31 = _P2 + ".Frage-3\\.1[0]"
W_CHK_SCHUL   = _F31 + ".Ausbildung[0].Schulausbildg[0]"
W_SCHUL_BEZ_1 = _F31 + ".Ausbildung[0].Bezeichnung-Ausbild-3\\.1\\.1[0]"
W_SCHUL_VON_1 = _F31 + ".Ausbildung[0].Ausbildung-von-3\\.1\\.1[0]"
W_SCHUL_BIS_1 = _F31 + ".Ausbildung[0].Ausbildung-bis-3\\.1\\.1[0]"
W_SCHUL_BEZ_2 = _F31 + ".Ausbildung[0].Bezeichnung-Ausbild-3\\.1\\.2[0]"
W_SCHUL_VON_2 = _F31 + ".Ausbildung[0].Ausbildung-von-3\\.1\\.2[0]"
W_SCHUL_BIS_2 = _F31 + ".Ausbildung[0].Ausbildung-bis-3\\.1\\.2[0]"
W_CHK_SONST   = _F31 + ".sonstige-Ausbildung[0].sonst-Ausbild[0]"
W_SONST_BEZ_1 = _F31 + ".sonstige-Ausbildung[0].Bezeichnung-sonst\\.Ausbild-1[0]"
W_SONST_VON_1 = _F31 + ".sonstige-Ausbildung[0].sonst-Ausbildung-von-1[0]"
W_SONST_BIS_1 = _F31 + ".sonstige-Ausbildung[0].sonst-Ausbildung-bis-1[0]"
W_SONST_BEZ_2 = _F31 + ".sonstige-Ausbildung[0].Bezeichnung-sonst-Ausbild-2[0]"
W_SONST_VON_2 = _F31 + ".sonstige-Ausbildung[0].sonst-Ausbildung-von-2[0]"
W_SONST_BIS_2 = _F31 + ".sonstige-Ausbildung[0].sonst-Ausbildung-bis-2[0]"
W_CHK_PLATZSUCHE = _F31 + ".Ausbild\\.platzsuche[0].Ausbildungsplatzsuche[0]"
W_SUCHE_VON      = _F31 + ".Ausbild\\.platzsuche[0].Ausbildungssuche-von[0]"
W_SUCHE_BIS      = _F31 + ".Ausbild\\.platzsuche[0].Ausbildungssuche-bis[0]"
W_CHK_FRW        = _F31 + ".Freiwill\\.dienst[0].Freiwilligendienst[0]"
W_FRW_VON        = _F31 + ".Freiwill\\.dienst[0].Freiwilligendienst-von[0]"
W_FRW_BIS        = _F31 + ".Freiwill\\.dienst[0].Freiwilligendienst-bis[0]"
W_CHK_UEBERG     = _F31 + ".Übergangszeit[0].Überg-zeit[0]"
W_UEBERG_VON     = _F31 + ".Übergangszeit[0].Übergangszeit-von[0]"
W_UEBERG_BIS     = _F31 + ".Übergangszeit[0].Übergangszeit-bis[0]"
W_CHK_ARBSUCHE   = _F31 + ".Arbeitssuche[0].Arbeitsplatzsuche[0]"
W_ARBLOS_VON     = _F31 + ".Arbeitssuche[0].arbeitslos-von[0]"
W_ARBLOS_BIS     = _F31 + ".Arbeitssuche[0].arbeitslos-bis[0]"

# Punkt 3.2 — Erwerbstätigkeit
_F32 = _P2 + ".Frage-3\\.2[0]"
W_ABG_JA     = _F32 + ".Frage-3\\.2\\.a[0].Pkt-3\\.2\\.a[0].abgeschlossen-Ja[0]"
W_ABG_NEIN   = _F32 + ".Frage-3\\.2\\.a[0].Pkt-3\\.2\\.a[0].abgeschlossen-Nein[0]"
W_ABSCHLUSS  = _F32 + ".Frage-3\\.2\\.a[0].Fr-3\\.2\\.a-Zeile-2[0].Abschluss[0]"
W_AUSB_ENDE  = _F32 + ".Frage-3\\.2\\.a[0].Fr-3\\.2\\.a-Zeile-2[0].Ausbildungsende[0]"
W_BERUFSZIEL = _F32 + ".Frage-3\\.2\\.a[0].Berufsziel[0]"
W_ERW_JA     = _F32 + ".Pkt-3\\.2\\.b[0].erwerbstät-Ja[0]"
W_ERW_NEIN   = _F32 + ".Pkt-3\\.2\\.b[0].erwerbstät-Nein[0]"
W_CHK_MINIJOB = _F32 + ".Zeile-Minijob[0].Minijob[0]"
W_MINIJOB_VON = _F32 + ".Zeile-Minijob[0].Minijob-von[0]"
W_MINIJOB_BIS = _F32 + ".Zeile-Minijob[0].Minijob-bis[0]"
W_CHK_ANDERE  = _F32 + ".Zeile-and-Erwerbstätigkeit[0].andere-Erwerbstätigkeit[0]"
W_ANDERE_VON  = _F32 + ".Zeile-and-Erwerbstätigkeit[0].andere-Erwerbstät-von[0]"
W_ANDERE_BIS  = _F32 + ".Zeile-and-Erwerbstätigkeit[0].andere-Erwerbstät-bis[0]"
W_ANDERE_AG   = _F32 + ".Arbeitgeber-Pkt-3\\.2-andere-Erwerbstät\\.[0]"
W_WEITERE_VON = _F32 + ".Zeile-weitere-Erwerbstätigkeit[0].weitere-Erwerbstät-von[0]"
W_WEITERE_BIS = _F32 + ".Zeile-weitere-Erwerbstätigkeit[0].weitere-Erwerbstät-bis[0]"
W_WEITERE_AG  = _F32 + ".Arbeitgeber-Pkt-3\\.2-weitere-Erwerbstätigkeit[0]"
W_WAZ         = _F32 + ".Zeile-Arbeitszeit[0].Wochenarbeitszeit[0]"

# Punkt 3.3 / 4 / 5 / 6 (Page 3)
W_BEH_JA   = _P3 + ".Frage-3\\.3[0].Frage-3\\.3-Zeile-1[0].Ja-3\\.3[0]"
W_BEH_NEIN = _P3 + ".Frage-3\\.3[0].Frage-3\\.3-Zeile-1[0].Nein-3\\.3[0]"
W_F4_JA       = _P3 + ".Frage-4[0].Pkt-4-Zeile-1[0].Ja-4[0]"
W_F4_NEIN     = _P3 + ".Frage-4[0].Pkt-4-Zeile-1[0].Nein-4[0]"
W_F4_NAME     = _P3 + ".Frage-4[0].Pkt-4-Zeile-2[0].Name-Pkt-4[0]"
W_F4_GEBDAT   = _P3 + ".Frage-4[0].Pkt-4-Zeile-2[0].Geburtsdatum-Pkt-4[0]"
W_F4_ZEITRAUM = _P3 + ".Frage-4[0].Pkt-4-Zeile-2[0].Zeitraum-Pkt-4[0]"
W_F4_FAMKA    = _P3 + ".Frage-4[0].Pkt-4-Zeile-3[0].FamKa-Pkt-4[0]"
W_F4_KGNR     = _P3 + ".Frage-4[0].Pkt-4-Zeile-3[0].KGNr-Pkt-4[0]"
W_F5_JA    = _P3 + ".Frage-5[0].Frage-5-Zeile-1[0].Ja-5\\.1[0]"
W_F5_NEIN  = _P3 + ".Frage-5[0].Frage-5-Zeile-1[0].Nein-5\\.1[0]"
W_F5A_JA   = _P3 + ".Frage-5[0].Frage-5-Zeile-2[0].Ja-5\\.2[0]"
W_F5A_NEIN = _P3 + ".Frage-5[0].Frage-5-Zeile-2[0].Nein-5\\.2[0]"
W_F5B_JA   = _P3 + ".Frage-5[0].Frage-5-Zeile-3[0].Ja-5\\.3[0]"
W_F5B_NEIN = _P3 + ".Frage-5[0].Frage-5-Zeile-3[0].Nein-5\\.3[0]"
W_F5_NAME   = _P3 + ".Frage-5[0].#area[13].Name-Pkt-5[0]"
W_F5_GEBDAT = _P3 + ".Frage-5[0].#area[13].Geburtsdatum-Pkt-5[0]"
W_F6_JA       = _P3 + ".Frage-6[0].Frage-6-Zeile-1[0].Ja-6[0]"
W_F6_NEIN     = _P3 + ".Frage-6[0].Frage-6-Zeile-1[0].Nein-6[0]"
W_F6_NAME     = _P3 + ".Frage-6[0].Frage-6-Zeile-2[0].Name-Pkt-6[0]"
W_F6_GEBDAT   = _P3 + ".Frage-6[0].Frage-6-Zeile-2[0].Geburtsdatum-Pkt-6[0]"
W_F6_LEISTUNG = _P3 + ".Frage-6[0].Frage-6-Zeile-3[0].Leistung-Pkt-6[0]"
W_F6_BETRAG   = _P3 + ".Frage-6[0].Frage-6-Zeile-3[0].Betrag-Pkt-6[0]"
W_F6_ZEITRAUM = _P3 + ".Frage-6[0].Frage-6-Zeile-3[0].Zeitraum-Pkt-6[0]"
W_F6_STELLE   = _P3 + ".Frage-6[0].Frage-6-Zeile-4[0].Stelle-Pkt-6[0]"
W_F6_AZ       = _P3 + ".Frage-6[0].Frage-6-Zeile-4[0].AZ-Pkt-6[0]"

# Punkt 7 + Erklärung (Page 4)
_F7 = _P4 + ".Frage-7[0]"
W_F7A_JA   = _F7 + ".Pkt-7-Fragen-a-bis-c[0].Zeile-7\\.a[0].Ja-7\\.a[0]"
W_F7A_NEIN = _F7 + ".Pkt-7-Fragen-a-bis-c[0].Zeile-7\\.a[0].Nein-7\\.a[0]"
W_F7B_JA   = _F7 + ".Pkt-7-Fragen-a-bis-c[0].Zeile-7\\.b[0].Ja-7\\.b[0]"
W_F7B_NEIN = _F7 + ".Pkt-7-Fragen-a-bis-c[0].Zeile-7\\.b[0].Nein-7\\.b[0]"
W_F7C_JA   = _F7 + ".Pkt-7-Fragen-a-bis-c[0].Zeile-7\\.c[0].Ja-7\\.c[0]"
W_F7C_NEIN = _F7 + ".Pkt-7-Fragen-a-bis-c[0].Zeile-7\\.c[0].Nein-7\\.c[0]"
W_F7_NAME      = _F7 + ".Frage-7-Angaben[0].Pkt-7-Zeile-5[0].Name-Pkt-7[0]"
W_F7_ZEITRAUM  = _F7 + ".Frage-7-Angaben[0].Pkt-7-Zeile-5[0].Zeitraum-Pkt-7[0]"
W_F7_AG        = _F7 + ".Frage-7-Angaben[0].Arbeitgeber-Pkt-7[0]"
W_F7_ANSCHRIFT = _F7 + ".Frage-7-Angaben[0].Anschrift-Pkt-7[0]"
W_F7_ORT       = _F7 + ".Frage-7-Angaben[0].Arbeitsort-Pkt-7[0]"
W_DATUM = _P4 + ".Erklärung[0].#area[9].Datum-1[0]"


# ── Logical field IDs ─────────────────────────────────────────────────────────

L_STEUER_ID    = "kg1ank_child_steuer_id"
L_REL_APP      = "kg1ank_rel_applicant"
L_REL_PARTNER  = "kg1ank_rel_partner"
L_REL_OTHER    = "kg1ank_rel_other"
L_ABGESCHLOSSEN = "kg1ank_training_completed"
L_ERWERB       = "kg1ank_child_employed"
L_BEHINDERUNG  = "kg1ank_child_disability"
L_PRIOR_KG     = "kg1ank_prior_kindergeld"
L_OEFF_DIENST  = "kg1ank_public_service"
L_DIENST_BUND  = "kg1ank_public_service_federal"
L_DIENST_BA    = "kg1ank_public_service_ba"
L_AUSL_LEISTUNG = "kg1ank_foreign_benefit"
L_7A           = "kg1ank_abroad_employment"
L_7B           = "kg1ank_foreign_agency_in_germany"
L_7C           = "kg1ank_posted_worker"

# Steuer-ID comb widths, verified via fitz text_maxlen (2+3+3+3 = 11 = IdNr).
_STEUER_ID_SLICES = [2, 3, 3, 3]

# Kinship option values (column order Zelle2..Zelle6 on the form).
_REL_OPTIONS = ["leibliches Kind", "Adoptivkind", "Pflegekind",
                "Stiefkind", "Enkelkind"]
# Extra non-widget option so partner / other-person rows can be skipped:
# expand_logical_fields finds no widget for it → every box in the row stays
# unchecked, which is exactly what an empty row on the paper form means.
_REL_NONE = "keine Angabe"

_JA_NEIN = ["ja", "nein"]


# ── Conditional-flow gates ────────────────────────────────────────────────────

def _eq(field_key: str, value: str) -> dict:
    return {"type": "field_equals", "field_key": field_key, "value": value}


_C_REL_OTHER = {"type": "field_in", "field_key": L_REL_OTHER,
                "values": _REL_OPTIONS}   # "keine Angabe" intentionally absent
# Grund der abweichenden Anschrift only when an address was actually given
# ("-" is the authored skip value for the optional address question).
_C_ABW = {"type": "field_not_equals", "field_key": W_CHILD_ANSCHRIFT, "value": "-"}

_ACTIVITY_CHECKBOXES = [
    W_CHK_SCHUL, W_CHK_SONST, W_CHK_PLATZSUCHE,
    W_CHK_FRW, W_CHK_UEBERG, W_CHK_ARBSUCHE,
]
# Adult-child section (3.2/3.3 + Nachweise) applies once any 3.1 activity is
# checked — the closest in-form gate to "the child is (almost) volljährig".
_C_ANY_31 = {"type": "or",
             "conditions": [_eq(c, "yes") for c in _ACTIVITY_CHECKBOXES]}

_C_SCHUL    = _eq(W_CHK_SCHUL, "yes")
_C_SONST    = _eq(W_CHK_SONST, "yes")
_C_SUCHE    = _eq(W_CHK_PLATZSUCHE, "yes")
_C_FRW      = _eq(W_CHK_FRW, "yes")
_C_UEBERG   = _eq(W_CHK_UEBERG, "yes")
_C_ARBSUCHE = _eq(W_CHK_ARBSUCHE, "yes")
_C_ABG_JA   = _eq(L_ABGESCHLOSSEN, "ja")
_C_ERW_JA   = _eq(L_ERWERB, "ja")
_C_MINIJOB  = _eq(W_CHK_MINIJOB, "yes")
_C_ANDERE   = _eq(W_CHK_ANDERE, "yes")
_C_F4_JA    = _eq(L_PRIOR_KG, "ja")
_C_F5_JA    = _eq(L_OEFF_DIENST, "ja")
_C_F6_JA    = _eq(L_AUSL_LEISTUNG, "ja")
_C_F7_ANY   = {"type": "or", "conditions": [
    _eq(L_7A, "ja"), _eq(L_7B, "ja"), _eq(L_7C, "ja"),
]}


# ── Template class ────────────────────────────────────────────────────────────

_REQUIRED = [
    "kg 1 ank",                # page footer — appears ONLY on this form
    "anlage kind",
    "kindschaftsverhältnis",
]


class Kg1AnlageKindTemplate(VerifiedTemplate):
    template_id   = "kg1_anlage_kind_v1"
    name          = "Familienkasse — Anlage Kind zum Antrag auf Kindergeld (KG 1 AnK)"
    fill_strategy = "fitz_acroform"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        return all(p in lo for p in _REQUIRED)

    def get_field_map(self) -> list:
        from app.services.pdf_pipeline import FieldMapEntry

        def auto(field_id, label, ftype, page, opts=None, src_text=None,
                 condition=None):
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
                condition=condition,
            )

        def manual(field_id, label, page):
            return FieldMapEntry(
                field_id=field_id,
                original_label=label,
                field_type="text",
                source_page=page,
                options=[],
                current_value="",
                confidence=0.5,           # show_question=False via the gate
                source="verified_template",
                source_text=label,
                reason="pdf_field",
            )

        rel_opts = _REL_OPTIONS + [_REL_NONE]

        return [
            # ── Header (Page 1) ──────────────────────────────────────────
            auto(W_NAME_KGB,   "Name, Vorname der antragstellenden Person", "text", 1),
            auto(W_KG_NR,      "Kindergeld-Nummer", "text", 1,
                 src_text="Kindergeld-Nr."),
            auto(W_ANTRAG_VOM, "Datum des Kindergeldantrags", "text", 1,
                 src_text="zum Antrag auf Kindergeld vom"),
            auto(W_LFD_NR,     "Laufende Nummer der Anlage", "text", 1,
                 src_text="Lfd. Nr."),

            # ── Punkt 1 — Angaben zum Kind ───────────────────────────────
            auto(L_STEUER_ID, "Steuer-Identifikationsnummer des Kindes",
                 "text", 1, src_text="Steuerliche Identifikationsnummer des Kindes"),
            auto(W_CHILD_NAME,    "Familienname des Kindes",  "text", 1),
            auto(W_CHILD_VORNAME, "Vorname des Kindes",       "text", 1),
            auto(W_CHILD_TITEL,   "Titel des Kindes",         "text", 1,
                 src_text="Titel (optional)"),
            auto(W_CHILD_GEBNAME, "Geburtsname des Kindes",   "text", 1,
                 src_text="Geburtsname (falls abweichend)"),
            auto(W_CHILD_GEBDATUM, "Geburtsdatum des Kindes", "text", 1),
            auto(W_CHILD_GEBORT,   "Geburtsort des Kindes",   "text", 1),
            auto(W_CHILD_GESCHLECHT, "Geschlecht des Kindes", "select", 1,
                 opts=["m", "w", "d"]),
            auto(W_CHILD_STAATSANG, "Staatsangehörigkeit des Kindes", "text", 1),
            auto(W_CHILD_ANSCHRIFT, "Abweichende Anschrift des Kindes", "text", 1,
                 src_text="Anschrift, wenn abweichend von antragstellender Person"),
            auto(W_CHILD_ABW_GRUND, "Grund der abweichenden Anschrift", "text", 1,
                 condition=_C_ABW),

            # ── Punkt 2 — Kindschaftsverhältnis (3 logical radios) ──────
            auto(L_REL_APP, "Kindschaftsverhältnis zur antragstellenden Person",
                 "radio", 1, opts=_REL_OPTIONS,
                 src_text="Kindschaftsverhältnis zur antragstellenden Person"),
            auto(L_REL_PARTNER,
                 "Kindschaftsverhältnis zum Ehe-/Lebenspartner",
                 "radio", 1, opts=rel_opts,
                 src_text="zum/zur Ehepartner(in) bzw. eingetragenen Lebenspartner(in)"),
            auto(L_REL_OTHER, "Kindschaftsverhältnis zu einer anderen Person",
                 "radio", 1, opts=rel_opts,
                 src_text="zu einer anderen Person"),

            # Angaben zur anderen Person (gated on a real selection above)
            auto(W_AP_NAME,    "Familienname der anderen Person", "text", 1,
                 condition=_C_REL_OTHER),
            auto(W_AP_VORNAME, "Vorname der anderen Person", "text", 1,
                 condition=_C_REL_OTHER),
            auto(W_AP_GEBDATUM, "Geburtsdatum der anderen Person", "text", 1,
                 condition=_C_REL_OTHER),
            auto(W_AP_ANSCHRIFT, "Letzte bekannte Anschrift der anderen Person",
                 "text", 1, condition=_C_REL_OTHER),
            auto(W_AP_STAATSANG, "Staatsangehörigkeit der anderen Person",
                 "text", 1, condition=_C_REL_OTHER),
            auto(W_AP_ZUSATZ, "Zusatzangaben zur anderen Person", "text", 1,
                 src_text="ggf. Zusatzangaben (z. B. verstorben, Vaterschaft nicht festgestellt)",
                 condition=_C_REL_OTHER),

            # ── Punkt 3.1 — volljähriges Kind: Tätigkeiten ───────────────
            auto(W_CHK_SCHUL, "Schul-, Hochschul- oder Berufsausbildung",
                 "checkbox", 2,
                 src_text="absolviert(e) folgende Schul-, Hochschul- oder Berufsausbildung"),
            auto(W_SCHUL_BEZ_1, "Bezeichnung der Ausbildung", "text", 2,
                 condition=_C_SCHUL),
            auto(W_SCHUL_VON_1, "Ausbildung von", "text", 2, condition=_C_SCHUL),
            auto(W_SCHUL_BIS_1, "Ausbildung bis", "text", 2, condition=_C_SCHUL),
            manual(W_SCHUL_BEZ_2, "Bezeichnung der 2. Ausbildung", 2),
            manual(W_SCHUL_VON_2, "2. Ausbildung von", 2),
            manual(W_SCHUL_BIS_2, "2. Ausbildung bis", 2),

            auto(W_CHK_SONST, "Sonstige Ausbildungsmaßnahme",
                 "checkbox", 2,
                 src_text="absolviert(e) folgende sonstige Ausbildungsmaßname"),
            auto(W_SONST_BEZ_1, "Bezeichnung der sonstigen Ausbildung", "text", 2,
                 condition=_C_SONST),
            auto(W_SONST_VON_1, "Sonstige Ausbildung von", "text", 2,
                 condition=_C_SONST),
            auto(W_SONST_BIS_1, "Sonstige Ausbildung bis", "text", 2,
                 condition=_C_SONST),
            manual(W_SONST_BEZ_2, "Bezeichnung der 2. sonstigen Ausbildung", 2),
            manual(W_SONST_VON_2, "2. sonstige Ausbildung von", 2),
            manual(W_SONST_BIS_2, "2. sonstige Ausbildung bis", 2),

            auto(W_CHK_PLATZSUCHE, "Ausbildungsplatzsuche", "checkbox", 2,
                 src_text="konnte/kann eine Berufsausbildung mangels Ausbildungsplatz nicht beginnen"),
            auto(W_SUCHE_VON, "Ausbildungsplatzsuche von", "text", 2,
                 condition=_C_SUCHE),
            auto(W_SUCHE_BIS, "Ausbildungsplatzsuche bis", "text", 2,
                 condition=_C_SUCHE),

            auto(W_CHK_FRW, "Freiwilligendienst", "checkbox", 2,
                 src_text="absolviert(e) einen der folgenden freiwilligen Dienste"),
            auto(W_FRW_VON, "Freiwilligendienst von", "text", 2, condition=_C_FRW),
            auto(W_FRW_BIS, "Freiwilligendienst bis", "text", 2, condition=_C_FRW),

            auto(W_CHK_UEBERG, "Übergangszeit", "checkbox", 2,
                 src_text="befand/befindet sich in einer Übergangszeit von höchstens vier Monaten"),
            auto(W_UEBERG_VON, "Übergangszeit von", "text", 2, condition=_C_UEBERG),
            auto(W_UEBERG_BIS, "Übergangszeit bis", "text", 2, condition=_C_UEBERG),

            auto(W_CHK_ARBSUCHE, "Ohne Beschäftigung / arbeitsuchend gemeldet",
                 "checkbox", 2,
                 src_text="war/ist ohne Beschäftigung und als arbeitsuchend gemeldet"),
            auto(W_ARBLOS_VON, "Arbeitsuchend von", "text", 2,
                 condition=_C_ARBSUCHE),
            auto(W_ARBLOS_BIS, "Arbeitsuchend bis", "text", 2,
                 condition=_C_ARBSUCHE),

            # ── Punkt 3.2 — Erwerbstätigkeit ─────────────────────────────
            auto(L_ABGESCHLOSSEN,
                 "Berufsausbildung oder Studium abgeschlossen", "radio", 2,
                 opts=_JA_NEIN, condition=_C_ANY_31,
                 src_text="Das Kind hat bereits eine Berufsausbildung oder ein Studium abgeschlossen"),
            auto(W_ABSCHLUSS, "Berufsabschluss/Studienabschluss", "text", 2,
                 condition=_C_ABG_JA),
            auto(W_AUSB_ENDE, "Ausbildungsende", "text", 2, condition=_C_ABG_JA),
            auto(W_BERUFSZIEL, "Berufsziel", "text", 2, condition=_C_ABG_JA),

            auto(L_ERWERB, "Erwerbstätigkeit des Kindes", "radio", 2,
                 opts=_JA_NEIN, condition=_C_ANY_31,
                 src_text="Das Kind war/ist erwerbstätig bzw. wird erwerbstätig sein"),
            auto(W_CHK_MINIJOB, "Geringfügige Beschäftigung (Minijob)",
                 "checkbox", 2, condition=_C_ERW_JA,
                 src_text="eine oder mehrere geringfügige Beschäftigung(en)"),
            auto(W_MINIJOB_VON, "Minijob von", "text", 2, condition=_C_MINIJOB),
            auto(W_MINIJOB_BIS, "Minijob bis", "text", 2, condition=_C_MINIJOB),
            auto(W_CHK_ANDERE, "Andere Erwerbstätigkeit", "checkbox", 2,
                 condition=_C_ERW_JA),
            auto(W_ANDERE_VON, "Andere Erwerbstätigkeit von", "text", 2,
                 condition=_C_ANDERE),
            auto(W_ANDERE_BIS, "Andere Erwerbstätigkeit bis", "text", 2,
                 condition=_C_ANDERE),
            auto(W_ANDERE_AG, "Arbeitgeber (Name, Anschrift)", "text", 2,
                 condition=_C_ANDERE),
            manual(W_WEITERE_VON, "Weitere Erwerbstätigkeit von", 2),
            manual(W_WEITERE_BIS, "Weitere Erwerbstätigkeit bis", 2),
            manual(W_WEITERE_AG, "Arbeitgeber der weiteren Erwerbstätigkeit", 2),
            auto(W_WAZ, "Wöchentliche Arbeitszeit", "text", 2,
                 condition=_C_ERW_JA,
                 src_text="Insgesamt (vereinbarte) Wochenarbeitszeit"),

            # Nachweise zu Punkt 3 (asked after the 3.x answers exist)
            auto(W_NACHW_BEI, "Nachweise sind beigefügt", "checkbox", 2,
                 condition=_C_ANY_31, src_text="Nachweise: sind beigefügt"),
            auto(W_NACHW_VOR, "Nachweise liegen bereits vor", "checkbox", 2,
                 condition=_C_ANY_31, src_text="Nachweise: liegen bereits vor"),
            auto(W_NACHW_NACH, "Nachweise werden nachgereicht", "checkbox", 2,
                 condition=_C_ANY_31, src_text="Nachweise: werden nachgereicht"),

            # ── Punkt 3.3 — Behinderung (adult children only) ────────────
            auto(L_BEHINDERUNG, "Behinderung des Kindes", "radio", 3,
                 opts=_JA_NEIN, condition=_C_ANY_31,
                 src_text="Liegt bei dem Kind eine Behinderung vor"),

            # ── Punkt 4 — bereits Kindergeld beantragt/erhalten ──────────
            auto(L_PRIOR_KG, "Kindergeld bereits beantragt oder erhalten",
                 "radio", 3, opts=_JA_NEIN,
                 src_text="für dieses Kind bereits Kindergeld beantragt oder erhalten"),
            auto(W_F4_NAME, "Name, Vorname der kindergeldbeziehenden Person",
                 "text", 3, condition=_C_F4_JA),
            auto(W_F4_GEBDAT, "Geburtsdatum dieser Person", "text", 3,
                 condition=_C_F4_JA),
            auto(W_F4_ZEITRAUM, "Zeitraum des Bezugs", "text", 3,
                 condition=_C_F4_JA),
            auto(W_F4_FAMKA, "Familienkasse (Name, Anschrift)", "text", 3,
                 condition=_C_F4_JA),
            auto(W_F4_KGNR, "Kindergeldnummer des früheren Bezugs", "text", 3,
                 condition=_C_F4_JA),

            # ── Punkt 5 — öffentlicher Dienst ────────────────────────────
            auto(L_OEFF_DIENST, "Tätigkeit im öffentlichen Dienst", "radio", 3,
                 opts=_JA_NEIN,
                 src_text="im öffentlichen Dienst tätig"),
            auto(L_DIENST_BUND, "Beschäftigung bei einer Einrichtung des Bundes",
                 "radio", 3, opts=_JA_NEIN, condition=_C_F5_JA,
                 src_text="Wird die Beschäftigung in einer Einrichtung des Bundes ausgeübt"),
            auto(L_DIENST_BA,
                 "Beschäftigung bei der Bundesagentur für Arbeit oder einem Jobcenter",
                 "radio", 3, opts=_JA_NEIN, condition=_C_F5_JA),
            auto(W_F5_NAME, "Name, Vorname der Person im öffentlichen Dienst",
                 "text", 3, condition=_C_F5_JA),
            auto(W_F5_GEBDAT, "Geburtsdatum dieser Person", "text", 3,
                 condition=_C_F5_JA),

            # ── Punkt 6 — ausländische kindbezogene Leistung ─────────────
            auto(L_AUSL_LEISTUNG, "Kindbezogene Leistung aus dem Ausland",
                 "radio", 3, opts=_JA_NEIN,
                 src_text="Anspruch auf eine kindbezogene Geldleistung von einer Stelle außerhalb Deutschlands"),
            auto(W_F6_NAME, "Name, Vorname der beziehenden Person", "text", 3,
                 condition=_C_F6_JA),
            auto(W_F6_GEBDAT, "Geburtsdatum der beziehenden Person", "text", 3,
                 condition=_C_F6_JA),
            auto(W_F6_LEISTUNG, "Bezeichnung der Leistung", "text", 3,
                 condition=_C_F6_JA),
            auto(W_F6_BETRAG, "Monatlicher Betrag (Euro)", "text", 3,
                 condition=_C_F6_JA),
            auto(W_F6_ZEITRAUM, "Zeitraum der Leistung", "text", 3,
                 condition=_C_F6_JA),
            auto(W_F6_STELLE, "Leistende Stelle (Name, Anschrift)", "text", 3,
                 condition=_C_F6_JA),
            auto(W_F6_AZ, "Aktenzeichen der leistenden Stelle", "text", 3,
                 condition=_C_F6_JA),

            # ── Punkt 7 — Auslandsbezug der letzten 5 Jahre ──────────────
            auto(L_7A, "Tätigkeit außerhalb Deutschlands", "radio", 4,
                 opts=_JA_NEIN,
                 src_text="außerhalb Deutschlands als Arbeitnehmer(in), Selbständige(r), Entwicklungshelfer(in) tätig"),
            auto(L_7B,
                 "Tätigkeit bei einer Einrichtung eines anderen Staates / NATO",
                 "radio", 4, opts=_JA_NEIN,
                 src_text="bei einer Dienststelle oder Einrichtung eines anderen Staates oder als Angehörige(r) der NATO-Streitkräfte"),
            auto(L_7C, "Entsandt von einem Arbeitgeber im Ausland", "radio", 4,
                 opts=_JA_NEIN,
                 src_text="auf Veranlassung eines Arbeitgebers mit Sitz außerhalb Deutschlands beschäftigt"),
            auto(W_F7_NAME, "Name, Vorname der beschäftigten Person", "text", 4,
                 condition=_C_F7_ANY),
            auto(W_F7_ZEITRAUM, "Zeitraum dieser Tätigkeit", "text", 4,
                 condition=_C_F7_ANY),
            auto(W_F7_AG, "Dienstherr/Arbeitgeber (Name, ggf. Personalnummer)",
                 "text", 4, condition=_C_F7_ANY),
            auto(W_F7_ANSCHRIFT, "Anschrift des Dienstherrn/Arbeitgebers",
                 "text", 4, condition=_C_F7_ANY),
            auto(W_F7_ORT, "Ort/Land der Erwerbstätigkeit", "text", 4,
                 condition=_C_F7_ANY),

            # ── Erklärung ────────────────────────────────────────────────
            auto(W_DATUM, "Datum (Unterschrift)", "text", 4,
                 src_text="Datum / Unterschrift der antragstellenden Person"),
        ]

    def get_radio_groups(self) -> list[RadioGroup]:
        def _rel_group(field_id: str, zeile: int) -> RadioGroup:
            widgets = [_kv(zeile, z) for z in (2, 3, 4, 5, 6)]
            return RadioGroup(
                field_id=field_id,
                widget_names=widgets,
                options=list(zip(_REL_OPTIONS, widgets)),
            )

        def _ja_nein(field_id: str, w_ja: str, w_nein: str) -> RadioGroup:
            return RadioGroup(
                field_id=field_id,
                widget_names=[w_ja, w_nein],
                options=[("ja", w_ja), ("nein", w_nein)],
            )

        return [
            _rel_group(L_REL_APP, 1),
            _rel_group(L_REL_PARTNER, 2),
            _rel_group(L_REL_OTHER, 4),
            _ja_nein(L_ABGESCHLOSSEN, W_ABG_JA, W_ABG_NEIN),
            _ja_nein(L_ERWERB, W_ERW_JA, W_ERW_NEIN),
            _ja_nein(L_BEHINDERUNG, W_BEH_JA, W_BEH_NEIN),
            _ja_nein(L_PRIOR_KG, W_F4_JA, W_F4_NEIN),
            _ja_nein(L_OEFF_DIENST, W_F5_JA, W_F5_NEIN),
            _ja_nein(L_DIENST_BUND, W_F5A_JA, W_F5A_NEIN),
            _ja_nein(L_DIENST_BA, W_F5B_JA, W_F5B_NEIN),
            _ja_nein(L_AUSL_LEISTUNG, W_F6_JA, W_F6_NEIN),
            _ja_nein(L_7A, W_F7A_JA, W_F7A_NEIN),
            _ja_nein(L_7B, W_F7B_JA, W_F7B_NEIN),
            _ja_nein(L_7C, W_F7C_JA, W_F7C_NEIN),
        ]

    def get_split_fields(self) -> list[SplitField]:
        return [
            SplitField(
                field_id=L_STEUER_ID,
                widget_names=[W_STEUER_1, W_STEUER_2, W_STEUER_3, W_STEUER_4],
                slices=_STEUER_ID_SLICES,
            ),
        ]


# ── Verified questions (en/de/fr/ar/tr/sq) ────────────────────────────────────

_LOCALES = ("en", "de", "fr", "ar", "tr", "sq")

_DATE_FMT = {
    "en": "DD.MM.YYYY", "de": "TT.MM.JJJJ", "fr": "JJ.MM.AAAA",
    "ar": "DD.MM.YYYY", "tr": "GG.AA.YYYY", "sq": "DD.MM.VVVV",
}
_PERIOD_FMT = {
    "en": "MM.YYYY - MM.YYYY", "de": "MM.JJJJ - MM.JJJJ",
    "fr": "MM.AAAA - MM.AAAA", "ar": "MM.YYYY - MM.YYYY",
    "tr": "AA.YYYY - AA.YYYY", "sq": "MM.VVVV - MM.VVVV",
}


def _Q(qs, helps=None, ex=None, fmt=None):
    """Build a {locale: {question, help, example, format}} entry from tuples
    ordered en/de/fr/ar/tr/sq. `ex` may be a single string (same for all) or a
    6-tuple. `fmt` is None | "date" | "period"."""
    out = {}
    for i, loc in enumerate(_LOCALES):
        d = {"question": qs[i]}
        if helps:
            d["help"] = helps[i]
        if ex is not None:
            d["example"] = ex if isinstance(ex, str) else ex[i]
        if fmt == "date":
            d["format"] = _DATE_FMT[loc]
        elif fmt == "period":
            d["format"] = _PERIOD_FMT[loc]
        out[loc] = d
    return out


def _von_q(act):
    """'When did/does <activity> start?' in 6 locales; act is a 6-tuple."""
    return _Q((
        f"When did or does {act[0]} start?",
        f"Wann begann/beginnt {act[1]}?",
        f"Quand commence ou a commencé {act[2]} ?",
        f"متى بدأ/يبدأ {act[3]}؟",
        f"{act[4]} ne zaman başladı/başlayacak?",
        f"Kur filloi/fillon {act[5]}?",
    ), ex="01.08.2025", fmt="date")


def _bis_q(act):
    """'When did/will <activity> end?' in 6 locales, with ongoing hint."""
    return _Q((
        f"When did or will {act[0]} end? Write - if it is still ongoing.",
        f"Wann endete/endet {act[1]}? Schreiben Sie -, wenn noch laufend.",
        f"Quand se termine ou s'est terminée {act[2]} ? Écrivez - si en cours.",
        f"متى انتهى/ينتهي {act[3]}؟ اكتب - إذا كان مستمرًا.",
        f"{act[4]} ne zaman bitti/bitecek? Devam ediyorsa - yazın.",
        f"Kur përfundoi/përfundon {act[5]}? Shkruani - nëse vazhdon.",
    ), ex="31.07.2026", fmt="date")


_ACT_SCHUL = (
    "this school, university or vocational training",
    "diese Schul-, Hochschul- oder Berufsausbildung",
    "cette formation scolaire, universitaire ou professionnelle",
    "هذا التعليم المدرسي أو الجامعي أو المهني",
    "bu okul, üniversite veya meslek eğitimi",
    "ky arsim shkollor, universitar ose profesional",
)
_ACT_SONST = (
    "this other training measure",
    "diese sonstige Ausbildungsmaßnahme",
    "cette autre mesure de formation",
    "هذا التدريب الآخر",
    "bu diğer eğitim programı",
    "kjo masë tjetër formimi",
)
_ACT_SUCHE = (
    "the search for a training place",
    "die Ausbildungsplatzsuche",
    "la recherche d'une place de formation",
    "البحث عن مكان تدريب",
    "eğitim yeri arayışı",
    "kërkimi i një vendi formimi",
)
_ACT_FRW = (
    "the voluntary service",
    "der Freiwilligendienst",
    "le service volontaire",
    "الخدمة التطوعية",
    "gönüllü hizmet",
    "shërbimi vullnetar",
)
_ACT_UEBERG = (
    "the transition period",
    "die Übergangszeit",
    "la période de transition",
    "الفترة الانتقالية",
    "geçiş dönemi",
    "periudha kalimtare",
)
_ACT_ARBSUCHE = (
    "the period without employment (registered as job-seeking)",
    "die Zeit ohne Beschäftigung (arbeitsuchend gemeldet)",
    "la période sans emploi (inscrit comme demandeur d'emploi)",
    "فترة عدم العمل (مسجل كباحث عن عمل)",
    "işsiz (iş arayan olarak kayıtlı) olduğu dönem",
    "periudha pa punë (i regjistruar si punëkërkues)",
)
_ACT_MINIJOB = (
    "the Minijob",
    "der Minijob",
    "le Minijob",
    "الميني جوب (عمل بسيط)",
    "Minijob",
    "Minijob-i",
)
_ACT_ANDERE = (
    "this job",
    "diese Erwerbstätigkeit",
    "cet emploi",
    "هذا العمل",
    "bu iş",
    "kjo punë",
)

_REL_HELP = (
    "leibliches Kind = biological child, Adoptivkind = adopted child, "
    "Pflegekind = foster child, Stiefkind = stepchild, Enkelkind = grandchild.",
    "leibliches Kind, Adoptivkind, Pflegekind, Stiefkind oder Enkelkind.",
    "leibliches Kind = enfant biologique, Adoptivkind = enfant adopté, "
    "Pflegekind = enfant placé, Stiefkind = bel-enfant, Enkelkind = petit-enfant.",
    "leibliches Kind = طفل بيولوجي، Adoptivkind = طفل متبنى، Pflegekind = طفل في الكفالة، "
    "Stiefkind = ابن الزوج/الزوجة، Enkelkind = حفيد.",
    "leibliches Kind = öz çocuk, Adoptivkind = evlat edinilmiş, Pflegekind = koruyucu "
    "aile çocuğu, Stiefkind = üvey çocuk, Enkelkind = torun.",
    "leibliches Kind = fëmijë biologjik, Adoptivkind = i adoptuar, Pflegekind = "
    "në kujdestari, Stiefkind = thjeshtër, Enkelkind = nip/mbesë.",
)

_QUESTIONS: dict = {
    # ── Header ───────────────────────────────────────────────────────────
    W_NAME_KGB: _Q((
        "What is the family name and first name of the applicant?",
        "Wie lauten Familienname und Vorname der antragstellenden Person?",
        "Quels sont le nom et le prénom de la personne qui fait la demande ?",
        "ما اسم العائلة والاسم الشخصي لمقدم الطلب؟",
        "Başvuru sahibinin soyadı ve adı nedir?",
        "Cili është mbiemri dhe emri i personit që aplikon?",
    ), helps=(
        "Exactly as on the main Kindergeld application (KG1).",
        "Genau wie auf dem Hauptantrag (KG1).",
        "Exactement comme sur la demande principale (KG1).",
        "تمامًا كما في الطلب الرئيسي (KG1).",
        "Ana başvurudaki (KG1) ile aynı şekilde.",
        "Saktësisht si në aplikimin kryesor (KG1).",
    ), ex="Diallo, Aminata"),
    W_KG_NR: _Q((
        "What is your Kindergeld number, if you already have one? Write - if none.",
        "Wie lautet Ihre Kindergeld-Nummer, falls vorhanden? Schreiben Sie -, wenn keine.",
        "Quel est votre numéro Kindergeld, si vous en avez déjà un ? Écrivez - sinon.",
        "ما هو رقم Kindergeld الخاص بك إن وُجد؟ اكتب - إذا لم يكن لديك.",
        "Varsa Kindergeld numaranız nedir? Yoksa - yazın.",
        "Cili është numri juaj i Kindergeld, nëse e keni? Shkruani - nëse jo.",
    ), ex="115FK154720"),
    W_ANTRAG_VOM: _Q((
        "What is the date of the Kindergeld application this attachment belongs to?",
        "Vom welchem Datum ist der Kindergeldantrag, zu dem diese Anlage gehört?",
        "Quelle est la date de la demande de Kindergeld à laquelle appartient cette annexe ?",
        "ما تاريخ طلب Kindergeld الذي تتبع له هذه الملحقة؟",
        "Bu ekin ait olduğu Kindergeld başvurusunun tarihi nedir?",
        "Cila është data e aplikimit për Kindergeld të cilit i përket kjo shtojcë?",
    ), ex="06.05.2026", fmt="date"),
    W_LFD_NR: _Q((
        "Which number is this child attachment (1 for the first child, 2 for the second, …)?",
        "Welche laufende Nummer hat diese Anlage Kind (1 für das erste Kind, 2 für das zweite, …)?",
        "Quel est le numéro de cette annexe enfant (1 pour le premier enfant, 2 pour le deuxième…) ?",
        "ما رقم هذه الملحقة (1 للطفل الأول، 2 للثاني، ...)؟",
        "Bu çocuk ekinin sıra numarası nedir (ilk çocuk için 1, ikinci için 2…)?",
        "Cili është numri rendor i kësaj shtojce (1 për fëmijën e parë, 2 për të dytin…)?",
    ), ex="1"),

    # ── Child ────────────────────────────────────────────────────────────
    L_STEUER_ID: _Q((
        "What is the child's tax identification number (11 digits)?",
        "Wie lautet die steuerliche Identifikationsnummer des Kindes (11 Ziffern)?",
        "Quel est le numéro d'identification fiscale de l'enfant (11 chiffres) ?",
        "ما هو رقم التعريف الضريبي للطفل (11 رقمًا)؟",
        "Çocuğun vergi kimlik numarası nedir (11 hane)?",
        "Cili është numri i identifikimit tatimor i fëmijës (11 shifra)?",
    ), helps=(
        "On the letter from the Bundeszentralamt für Steuern sent after birth/registration. Mandatory if already assigned.",
        "Steht im Brief des Bundeszentralamts für Steuern. Zwingend, soweit bereits vergeben.",
        "Sur la lettre du Bundeszentralamt für Steuern. Obligatoire si déjà attribué.",
        "موجود في رسالة Bundeszentralamt für Steuern. إلزامي إذا كان قد صدر.",
        "Bundeszentralamt für Steuern'in mektubunda yazar. Verilmişse zorunludur.",
        "Gjendet në letrën e Bundeszentralamt für Steuern. I detyrueshëm nëse është lëshuar.",
    ), ex="12345678901"),
    W_CHILD_NAME: _Q((
        "What is the child's family name?",
        "Wie lautet der Familienname des Kindes?",
        "Quel est le nom de famille de l'enfant ?",
        "ما اسم عائلة الطفل؟",
        "Çocuğun soyadı nedir?",
        "Cili është mbiemri i fëmijës?",
    ), ex="Diallo"),
    W_CHILD_VORNAME: _Q((
        "What is the child's first name?",
        "Wie lautet der Vorname des Kindes?",
        "Quel est le prénom de l'enfant ?",
        "ما الاسم الشخصي للطفل؟",
        "Çocuğun adı nedir?",
        "Cili është emri i fëmijës?",
    ), ex="Ibrahim"),
    W_CHILD_TITEL: _Q((
        "Does the child have an academic title? Write - if none.",
        "Hat das Kind einen Titel? Schreiben Sie -, wenn keiner.",
        "L'enfant a-t-il un titre ? Écrivez - sinon.",
        "هل لدى الطفل لقب أكاديمي؟ اكتب - إذا لا.",
        "Çocuğun bir unvanı var mı? Yoksa - yazın.",
        "A ka fëmija ndonjë titull? Shkruani - nëse jo.",
    ), ex="-"),
    W_CHILD_GEBNAME: _Q((
        "What is the child's birth name, if different? Write - if the same.",
        "Wie lautet der Geburtsname des Kindes, falls abweichend? Schreiben Sie -, wenn gleich.",
        "Quel est le nom de naissance de l'enfant, s'il est différent ? Écrivez - sinon.",
        "ما اسم الميلاد للطفل إذا كان مختلفًا؟ اكتب - إذا كان نفسه.",
        "Farklıysa çocuğun doğum adı nedir? Aynıysa - yazın.",
        "Cili është mbiemri i lindjes së fëmijës nëse ndryshon? Shkruani - nëse është i njëjtë.",
    ), ex="-"),
    W_CHILD_GEBDATUM: _Q((
        "What is the child's date of birth?",
        "Wann wurde das Kind geboren?",
        "Quelle est la date de naissance de l'enfant ?",
        "ما تاريخ ميلاد الطفل؟",
        "Çocuğun doğum tarihi nedir?",
        "Cila është data e lindjes së fëmijës?",
    ), ex="15.03.2019", fmt="date"),
    W_CHILD_GEBORT: _Q((
        "Where was the child born (city)?",
        "Wo wurde das Kind geboren (Ort)?",
        "Où l'enfant est-il né (ville) ?",
        "أين وُلد الطفل (المدينة)؟",
        "Çocuk nerede doğdu (şehir)?",
        "Ku ka lindur fëmija (qyteti)?",
    ), ex="Rostock"),
    W_CHILD_GESCHLECHT: _Q((
        "What is the child's gender as in official documents?",
        "Welches Geschlecht hat das Kind laut offiziellen Dokumenten?",
        "Quel est le genre de l'enfant selon les documents officiels ?",
        "ما جنس الطفل كما في الوثائق الرسمية؟",
        "Resmi belgelere göre çocuğun cinsiyeti nedir?",
        "Cila është gjinia e fëmijës sipas dokumenteve zyrtare?",
    ), helps=(
        "Choose m (male), w (female) or d (diverse).",
        "Wählen Sie m (männlich), w (weiblich) oder d (divers).",
        "Choisissez m (masculin), w (féminin) ou d (divers).",
        "اختر m (ذكر) أو w (أنثى) أو d (آخر).",
        "m (erkek), w (kadın) veya d (diğer) seçin.",
        "Zgjidhni m (mashkull), w (femër) ose d (tjetër).",
    )),
    W_CHILD_STAATSANG: _Q((
        "What is the child's nationality?",
        "Welche Staatsangehörigkeit hat das Kind?",
        "Quelle est la nationalité de l'enfant ?",
        "ما جنسية الطفل؟",
        "Çocuğun uyruğu nedir?",
        "Cila është shtetësia e fëmijës?",
    ), ex=("Guinean", "guineisch", "guinéenne", "غينية", "Gineli", "guineane")),
    W_CHILD_ANSCHRIFT: _Q((
        "Does the child live at a different address than you? If yes, enter street, number, postal code, city, country. Write - if the child lives with you.",
        "Wohnt das Kind an einer anderen Anschrift als Sie? Wenn ja: Straße, Hausnummer, PLZ, Ort, Staat. Schreiben Sie -, wenn das Kind bei Ihnen wohnt.",
        "L'enfant vit-il à une autre adresse que vous ? Si oui : rue, numéro, code postal, ville, pays. Écrivez - s'il vit avec vous.",
        "هل يسكن الطفل في عنوان مختلف عنك؟ إذا نعم: الشارع، الرقم، الرمز البريدي، المدينة، الدولة. اكتب - إذا كان يسكن معك.",
        "Çocuk sizden farklı bir adreste mi yaşıyor? Evetse: sokak, numara, posta kodu, şehir, ülke. Sizinle yaşıyorsa - yazın.",
        "A jeton fëmija në një adresë tjetër nga ju? Nëse po: rruga, numri, kodi postar, qyteti, shteti. Shkruani - nëse jeton me ju.",
    ), ex="-"),
    W_CHILD_ABW_GRUND: _Q((
        "Why does the child live at a different address (e.g. with grandparents, foster care, boarding school)?",
        "Warum wohnt das Kind an einer anderen Anschrift (z. B. bei Großeltern, Pflegestelle, Internat)?",
        "Pourquoi l'enfant vit-il à une autre adresse (par ex. grands-parents, famille d'accueil, internat) ?",
        "لماذا يسكن الطفل في عنوان مختلف (مثلاً عند الأجداد، أسرة كافلة، مدرسة داخلية)؟",
        "Çocuk neden farklı bir adreste yaşıyor (örn. büyükanne/büyükbaba, koruyucu aile, yatılı okul)?",
        "Pse jeton fëmija në një adresë tjetër (p.sh. te gjyshërit, kujdestaria, konvikti)?",
    )),

    # ── Kinship ──────────────────────────────────────────────────────────
    L_REL_APP: _Q((
        "What is the child's relationship to you (the applicant)?",
        "In welchem Kindschaftsverhältnis steht das Kind zu Ihnen (antragstellende Person)?",
        "Quel est le lien de parenté de l'enfant avec vous (personne qui fait la demande) ?",
        "ما علاقة الطفل بك (مقدم الطلب)؟",
        "Çocuğun sizinle (başvuru sahibi) ilişkisi nedir?",
        "Cila është lidhja e fëmijës me ju (personi që aplikon)?",
    ), helps=_REL_HELP),
    L_REL_PARTNER: _Q((
        "What is the child's relationship to your spouse or registered partner? Choose 'keine Angabe' if you have no partner or it does not apply.",
        "In welchem Kindschaftsverhältnis steht das Kind zu Ihrem Ehe- oder eingetragenen Lebenspartner? Wählen Sie 'keine Angabe', wenn nicht zutreffend.",
        "Quel est le lien de l'enfant avec votre conjoint(e) ou partenaire enregistré(e) ? Choisissez « keine Angabe » si sans objet.",
        "ما علاقة الطفل بزوجك/زوجتك أو شريكك المسجل؟ اختر 'keine Angabe' إذا لم ينطبق.",
        "Çocuğun eşiniz veya kayıtlı partnerinizle ilişkisi nedir? Geçerli değilse 'keine Angabe' seçin.",
        "Cila është lidhja e fëmijës me bashkëshortin ose partnerin tuaj të regjistruar? Zgjidhni 'keine Angabe' nëse nuk aplikohet.",
    ), helps=_REL_HELP),
    L_REL_OTHER: _Q((
        "Is the child also the child of another person (e.g. the other parent)? Choose the relationship, or 'keine Angabe'.",
        "Steht das Kind in einem Kindschaftsverhältnis zu einer anderen Person (z. B. anderer Elternteil)? Wählen Sie das Verhältnis oder 'keine Angabe'.",
        "L'enfant est-il aussi l'enfant d'une autre personne (par ex. l'autre parent) ? Choisissez le lien, ou « keine Angabe ».",
        "هل الطفل أيضًا طفل لشخص آخر (مثلاً الوالد الآخر)؟ اختر العلاقة أو 'keine Angabe'.",
        "Çocuk başka bir kişinin de çocuğu mu (örn. diğer ebeveyn)? İlişkiyi seçin veya 'keine Angabe'.",
        "A është fëmija edhe fëmijë i një personi tjetër (p.sh. prindi tjetër)? Zgjidhni lidhjen ose 'keine Angabe'.",
    ), helps=_REL_HELP),
    W_AP_NAME: _Q((
        "What is the family name of this other person?",
        "Wie lautet der Familienname dieser anderen Person?",
        "Quel est le nom de famille de cette autre personne ?",
        "ما اسم عائلة هذا الشخص الآخر؟",
        "Bu diğer kişinin soyadı nedir?",
        "Cili është mbiemri i këtij personi tjetër?",
    )),
    W_AP_VORNAME: _Q((
        "What is the first name of this other person?",
        "Wie lautet der Vorname dieser anderen Person?",
        "Quel est le prénom de cette autre personne ?",
        "ما الاسم الشخصي لهذا الشخص الآخر؟",
        "Bu diğer kişinin adı nedir?",
        "Cili është emri i këtij personi tjetër?",
    )),
    W_AP_GEBDATUM: _Q((
        "What is the date of birth of this other person? Write - if unknown.",
        "Wann wurde diese andere Person geboren? Schreiben Sie -, wenn unbekannt.",
        "Quelle est la date de naissance de cette autre personne ? Écrivez - si inconnue.",
        "ما تاريخ ميلاد هذا الشخص الآخر؟ اكتب - إذا كان مجهولاً.",
        "Bu diğer kişinin doğum tarihi nedir? Bilinmiyorsa - yazın.",
        "Cila është data e lindjes së këtij personi? Shkruani - nëse nuk dihet.",
    ), ex="20.07.1990", fmt="date"),
    W_AP_ANSCHRIFT: _Q((
        "What is the last known address of this other person? Write - if unknown.",
        "Wie lautet die letzte bekannte Anschrift dieser Person? Schreiben Sie -, wenn unbekannt.",
        "Quelle est la dernière adresse connue de cette personne ? Écrivez - si inconnue.",
        "ما آخر عنوان معروف لهذا الشخص؟ اكتب - إذا كان مجهولاً.",
        "Bu kişinin bilinen son adresi nedir? Bilinmiyorsa - yazın.",
        "Cila është adresa e fundit e njohur e këtij personi? Shkruani - nëse nuk dihet.",
    )),
    W_AP_STAATSANG: _Q((
        "What is the nationality of this other person? Write - if unknown.",
        "Welche Staatsangehörigkeit hat diese Person? Schreiben Sie -, wenn unbekannt.",
        "Quelle est la nationalité de cette personne ? Écrivez - si inconnue.",
        "ما جنسية هذا الشخص؟ اكتب - إذا كانت مجهولة.",
        "Bu kişinin uyruğu nedir? Bilinmiyorsa - yazın.",
        "Cila është shtetësia e këtij personi? Shkruani - nëse nuk dihet.",
    )),
    W_AP_ZUSATZ: _Q((
        "Any additional notes about this person (e.g. deceased, paternity not established, unknown)? Write - if none.",
        "Zusatzangaben zu dieser Person (z. B. verstorben, Vaterschaft nicht festgestellt, unbekannt)? Schreiben Sie -, wenn keine.",
        "Remarques supplémentaires sur cette personne (par ex. décédée, paternité non établie, inconnue) ? Écrivez - sinon.",
        "ملاحظات إضافية عن هذا الشخص (مثلاً متوفى، الأبوة غير مثبتة، مجهول)؟ اكتب - إذا لا.",
        "Bu kişi hakkında ek bilgi (örn. vefat etti, babalık tespit edilmedi, bilinmiyor)? Yoksa - yazın.",
        "Shënime shtesë për këtë person (p.sh. i ndjerë, atësia e papërcaktuar, i panjohur)? Shkruani - nëse jo.",
    ), ex="-"),

    # ── 3.1 activity checkboxes + details ───────────────────────────────
    W_CHK_SCHUL: _Q((
        "Is the child (18 or almost 18) in school, university or vocational training?",
        "Besucht das Kind (volljährig oder bald 18) eine Schule, Hochschule oder Berufsausbildung?",
        "L'enfant (majeur ou presque 18 ans) suit-il une formation scolaire, universitaire ou professionnelle ?",
        "هل الطفل (بالغ أو قارب 18) في مدرسة أو جامعة أو تدريب مهني؟",
        "Çocuk (18 yaşında veya yakında 18) okula, üniversiteye veya meslek eğitimine gidiyor mu?",
        "A ndjek fëmija (madhor ose së shpejti 18) shkollë, universitet ose formim profesional?",
    ), helps=(
        "Only answer the questions in this section for a child who is 18 or will soon turn 18. For younger children answer no.",
        "Diesen Abschnitt nur für ein volljähriges (oder bald volljähriges) Kind ausfüllen. Für jüngere Kinder: nein.",
        "Ne remplissez cette section que pour un enfant majeur (ou bientôt majeur). Pour les plus jeunes : non.",
        "أجب عن هذا القسم فقط لطفل بالغ أو سيبلغ 18 قريبًا. لطفل أصغر: لا.",
        "Bu bölümü yalnızca 18 yaşındaki (veya yakında 18 olacak) çocuk için doldurun. Daha küçükse: hayır.",
        "Plotësojeni këtë seksion vetëm për fëmijë madhor (ose së shpejti 18). Për më të vegjlit: jo.",
    )),
    W_SCHUL_BEZ_1: _Q((
        "What is the name/type of this education (e.g. Gymnasium, Bachelor Informatik, Ausbildung zur Pflegefachkraft)?",
        "Wie lautet die Bezeichnung der Ausbildung (z. B. Gymnasium, Bachelor Informatik, Ausbildung zur Pflegefachkraft)?",
        "Quelle est la désignation de cette formation (par ex. Gymnasium, licence d'informatique, formation d'infirmier) ?",
        "ما اسم/نوع هذا التعليم (مثلاً Gymnasium، بكالوريوس معلوماتية، تدريب تمريض)؟",
        "Bu eğitimin adı/türü nedir (örn. lise, bilgisayar lisansı, hemşirelik eğitimi)?",
        "Cili është emërtimi i këtij arsimi (p.sh. gjimnaz, bachelor informatikë, formim infermierie)?",
    )),
    W_SCHUL_VON_1: _von_q(_ACT_SCHUL),
    W_SCHUL_BIS_1: _bis_q(_ACT_SCHUL),
    W_CHK_SONST: _Q((
        "Is the child doing another training measure (e.g. internship, au-pair with language course, basic military training)?",
        "Absolviert das Kind eine sonstige Ausbildungsmaßnahme (z. B. Praktikum, Au-pair mit Sprachunterricht, Grundausbildung)?",
        "L'enfant suit-il une autre mesure de formation (par ex. stage, au pair avec cours de langue, formation militaire de base) ?",
        "هل يقوم الطفل بتدريب آخر (مثلاً تدريب عملي، أو-بير مع دروس لغة، تدريب أساسي)؟",
        "Çocuk başka bir eğitim programına mı katılıyor (örn. staj, dil kurslu au-pair, temel askerlik eğitimi)?",
        "A po ndjek fëmija ndonjë masë tjetër formimi (p.sh. praktikë, au-pair me kurs gjuhe, stërvitje bazë)?",
    )),
    W_SONST_BEZ_1: _Q((
        "What is the name of this other training measure?",
        "Wie lautet die Bezeichnung dieser sonstigen Ausbildung?",
        "Quelle est la désignation de cette autre formation ?",
        "ما اسم هذا التدريب الآخر؟",
        "Bu diğer eğitimin adı nedir?",
        "Cili është emërtimi i këtij formimi tjetër?",
    )),
    W_SONST_VON_1: _von_q(_ACT_SONST),
    W_SONST_BIS_1: _bis_q(_ACT_SONST),
    W_CHK_PLATZSUCHE: _Q((
        "Could the child not start or continue vocational training because no training place was available?",
        "Konnte/kann das Kind eine Berufsausbildung mangels Ausbildungsplatz nicht beginnen oder fortsetzen?",
        "L'enfant n'a-t-il pas pu commencer ou poursuivre une formation faute de place ?",
        "هل لم يستطع الطفل بدء أو مواصلة تدريب مهني لعدم توفر مكان؟",
        "Çocuk, eğitim yeri bulunamadığı için meslek eğitimine başlayamadı veya devam edemedi mi?",
        "A nuk mundi fëmija të fillojë ose vazhdojë formimin profesional për mungesë vendi?",
    )),
    W_SUCHE_VON: _von_q(_ACT_SUCHE),
    W_SUCHE_BIS: _bis_q(_ACT_SUCHE),
    W_CHK_FRW: _Q((
        "Is the child doing a recognised voluntary service (e.g. FSJ, FÖJ, Bundesfreiwilligendienst)?",
        "Absolviert das Kind einen anerkannten Freiwilligendienst (z. B. FSJ, FÖJ, Bundesfreiwilligendienst)?",
        "L'enfant effectue-t-il un service volontaire reconnu (par ex. FSJ, FÖJ, Bundesfreiwilligendienst) ?",
        "هل يؤدي الطفل خدمة تطوعية معترفًا بها (مثل FSJ أو BFD)؟",
        "Çocuk tanınan bir gönüllü hizmet mi yapıyor (örn. FSJ, FÖJ, Bundesfreiwilligendienst)?",
        "A po kryen fëmija një shërbim vullnetar të njohur (p.sh. FSJ, FÖJ, Bundesfreiwilligendienst)?",
    )),
    W_FRW_VON: _von_q(_ACT_FRW),
    W_FRW_BIS: _bis_q(_ACT_FRW),
    W_CHK_UEBERG: _Q((
        "Is the child in a transition period of at most 4 months (e.g. between school and training)?",
        "Befindet sich das Kind in einer Übergangszeit von höchstens vier Monaten (z. B. zwischen Schule und Ausbildung)?",
        "L'enfant est-il dans une période de transition de quatre mois au plus (par ex. entre l'école et la formation) ?",
        "هل الطفل في فترة انتقالية لا تتجاوز 4 أشهر (مثلاً بين المدرسة والتدريب)؟",
        "Çocuk en fazla 4 aylık bir geçiş döneminde mi (örn. okul ile eğitim arasında)?",
        "A është fëmija në një periudhë kalimtare prej më së shumti 4 muajsh (p.sh. mes shkollës dhe formimit)?",
    )),
    W_UEBERG_VON: _von_q(_ACT_UEBERG),
    W_UEBERG_BIS: _bis_q(_ACT_UEBERG),
    W_CHK_ARBSUCHE: _Q((
        "Is the child without employment and registered as job-seeking at the Agentur für Arbeit or Jobcenter?",
        "Ist das Kind ohne Beschäftigung und bei einer Agentur für Arbeit oder einem Jobcenter arbeitsuchend gemeldet?",
        "L'enfant est-il sans emploi et inscrit comme demandeur d'emploi à l'Agentur für Arbeit ou au Jobcenter ?",
        "هل الطفل بلا عمل ومسجل كباحث عن عمل لدى وكالة العمل أو الجوب سنتر؟",
        "Çocuk işsiz ve Agentur für Arbeit veya Jobcenter'da iş arayan olarak kayıtlı mı?",
        "A është fëmija pa punë dhe i regjistruar si punëkërkues në Agentur für Arbeit ose Jobcenter?",
    )),
    W_ARBLOS_VON: _von_q(_ACT_ARBSUCHE),
    W_ARBLOS_BIS: _bis_q(_ACT_ARBSUCHE),

    # ── 3.2 ──────────────────────────────────────────────────────────────
    L_ABGESCHLOSSEN: _Q((
        "Has the child already completed (or will soon complete) a vocational training or university degree?",
        "Hat das Kind bereits eine Berufsausbildung oder ein Studium abgeschlossen bzw. schließt es diese(s) in Kürze ab?",
        "L'enfant a-t-il déjà terminé (ou terminera-t-il bientôt) une formation professionnelle ou des études ?",
        "هل أنهى الطفل (أو سينهي قريبًا) تدريبًا مهنيًا أو دراسة جامعية؟",
        "Çocuk bir meslek eğitimini veya üniversiteyi tamamladı mı (veya yakında tamamlayacak mı)?",
        "A e ka përfunduar fëmija (ose do ta përfundojë së shpejti) një formim profesional ose studime?",
    )),
    W_ABSCHLUSS: _Q((
        "Which degree or vocational qualification did the child complete (with subject)?",
        "Welchen Berufs-/Studienabschluss hat das Kind (mit Angabe des Fachs)?",
        "Quel diplôme ou qualification l'enfant a-t-il obtenu (avec la matière) ?",
        "ما الشهادة أو المؤهل الذي حصل عليه الطفل (مع التخصص)؟",
        "Çocuk hangi diplomayı/mesleki yeterliliği aldı (alanıyla birlikte)?",
        "Çfarë diplome ose kualifikimi mori fëmija (me lëndën)?",
    ), ex=("Bachelor of Science, Informatik",) * 6),
    W_AUSB_ENDE: _Q((
        "When did or will this training end?",
        "Wann endete/endet diese Ausbildung?",
        "Quand cette formation s'est-elle terminée ou se terminera-t-elle ?",
        "متى انتهى/ينتهي هذا التدريب؟",
        "Bu eğitim ne zaman bitti/bitecek?",
        "Kur përfundoi/përfundon ky formim?",
    ), ex="30.06.2026", fmt="date"),
    W_BERUFSZIEL: _Q((
        "What is the child's career goal, if different from the completed degree? Write - if the same.",
        "Welches Berufsziel hat das Kind, falls es vom Abschluss abweicht? Schreiben Sie -, wenn gleich.",
        "Quel est l'objectif professionnel de l'enfant, s'il diffère du diplôme ? Écrivez - sinon.",
        "ما الهدف المهني للطفل إذا كان مختلفًا عن الشهادة؟ اكتب - إذا كان نفسه.",
        "Aldığı diplomadan farklıysa çocuğun kariyer hedefi nedir? Aynıysa - yazın.",
        "Cili është synimi profesional i fëmijës nëse ndryshon nga diploma? Shkruani - nëse i njëjtë.",
    ), ex="-"),
    L_ERWERB: _Q((
        "Is or was the child working (employed), or will the child start working?",
        "War/ist das Kind erwerbstätig bzw. wird es erwerbstätig sein?",
        "L'enfant travaille-t-il, a-t-il travaillé ou va-t-il travailler ?",
        "هل يعمل الطفل أو عمل أو سيعمل؟",
        "Çocuk çalışıyor mu, çalıştı mı veya çalışacak mı?",
        "A punon, ka punuar ose do të punojë fëmija?",
    )),
    W_CHK_MINIJOB: _Q((
        "Is or was it one or more Minijobs (geringfügige Beschäftigung)?",
        "Handelt(e) es sich um eine oder mehrere geringfügige Beschäftigungen (Minijob)?",
        "S'agit-il d'un ou plusieurs Minijobs (emploi à faible revenu) ?",
        "هل هو ميني جوب (عمل بسيط) واحد أو أكثر؟",
        "Bir veya birden fazla Minijob mu (düşük gelirli iş)?",
        "A bëhet fjalë për një ose më shumë Minijob (punësim i vogël)?",
    )),
    W_MINIJOB_VON: _von_q(_ACT_MINIJOB),
    W_MINIJOB_BIS: _bis_q(_ACT_MINIJOB),
    W_CHK_ANDERE: _Q((
        "Does or did the child have another job (not a Minijob)?",
        "Hat(te) das Kind eine andere Erwerbstätigkeit (kein Minijob)?",
        "L'enfant a-t-il un autre emploi (pas un Minijob) ?",
        "هل لدى الطفل عمل آخر (ليس ميني جوب)؟",
        "Çocuğun başka bir işi var mı (Minijob değil)?",
        "A ka fëmija një punë tjetër (jo Minijob)?",
    )),
    W_ANDERE_VON: _von_q(_ACT_ANDERE),
    W_ANDERE_BIS: _bis_q(_ACT_ANDERE),
    W_ANDERE_AG: _Q((
        "Who is the employer for this job (name and address)?",
        "Wer ist der Dienstherr bzw. Arbeitgeber (Name, Anschrift)?",
        "Quel est l'employeur pour cet emploi (nom et adresse) ?",
        "من هو صاحب العمل (الاسم والعنوان)؟",
        "Bu işin işvereni kim (ad ve adres)?",
        "Kush është punëdhënësi për këtë punë (emri dhe adresa)?",
    )),
    W_WAZ: _Q((
        "How many hours per week does the child work in total (as agreed in the contract)?",
        "Wie hoch ist die insgesamt vereinbarte Wochenarbeitszeit des Kindes?",
        "Combien d'heures par semaine l'enfant travaille-t-il au total (selon le contrat) ?",
        "كم عدد ساعات عمل الطفل في الأسبوع إجمالاً (حسب العقد)؟",
        "Çocuk sözleşmeye göre haftada toplam kaç saat çalışıyor?",
        "Sa orë në javë punon fëmija gjithsej (sipas kontratës)?",
    ), ex="20"),
    W_NACHW_BEI: _Q((
        "Are the proof documents (certificates) attached to this application?",
        "Sind die Nachweise (Bescheinigungen) diesem Antrag beigefügt?",
        "Les justificatifs (attestations) sont-ils joints à cette demande ?",
        "هل المستندات الثبوتية مرفقة بهذا الطلب؟",
        "Kanıt belgeleri bu başvuruya eklendi mi?",
        "A janë dëshmitë (vërtetimet) bashkëngjitur këtij aplikimi?",
    )),
    W_NACHW_VOR: _Q((
        "Has the Familienkasse already received these proofs earlier?",
        "Liegen die Nachweise der Familienkasse bereits vor?",
        "La Familienkasse possède-t-elle déjà ces justificatifs ?",
        "هل لدى Familienkasse هذه المستندات بالفعل؟",
        "Familienkasse bu belgelere zaten sahip mi?",
        "A i ka Familienkasse tashmë këto dëshmi?",
    )),
    W_NACHW_NACH: _Q((
        "Will you submit the proofs later?",
        "Werden die Nachweise nachgereicht?",
        "Allez-vous fournir les justificatifs plus tard ?",
        "هل سترسل المستندات لاحقًا؟",
        "Belgeleri daha sonra mı göndereceksiniz?",
        "A do t'i dorëzoni dëshmitë më vonë?",
    )),

    # ── 3.3 ──────────────────────────────────────────────────────────────
    L_BEHINDERUNG: _Q((
        "Does the child have a disability that occurred before the age of 25?",
        "Liegt bei dem Kind eine Behinderung vor, die vor Vollendung des 25. Lebensjahres eingetreten ist?",
        "L'enfant a-t-il un handicap survenu avant l'âge de 25 ans ?",
        "هل لدى الطفل إعاقة حدثت قبل بلوغ 25 عامًا؟",
        "Çocuğun 25 yaşından önce ortaya çıkmış bir engeli var mı?",
        "A ka fëmija një aftësi të kufizuar të shfaqur para moshës 25 vjeç?",
    )),

    # ── Punkt 4 ──────────────────────────────────────────────────────────
    L_PRIOR_KG: _Q((
        "Have you or a person named in section 2 already applied for or received Kindergeld for this child?",
        "Haben Sie oder eine unter Punkt 2 genannte Person für dieses Kind bereits Kindergeld beantragt oder erhalten?",
        "Vous ou une personne citée au point 2 avez-vous déjà demandé ou reçu le Kindergeld pour cet enfant ?",
        "هل سبق أن طلبت أنت أو شخص مذكور في النقطة 2 Kindergeld لهذا الطفل أو حصل عليه؟",
        "Siz veya 2. bölümde adı geçen bir kişi bu çocuk için daha önce Kindergeld başvurusu yaptı mı veya aldı mı?",
        "A keni aplikuar ju ose një person i përmendur në pikën 2 më parë për Kindergeld për këtë fëmijë, ose e keni marrë?",
    )),
    W_F4_NAME: _Q((
        "What is the name of the person who applied for / received that Kindergeld?",
        "Wie heißt die Person, die das Kindergeld beantragt oder bezogen hat (Familienname, Vorname)?",
        "Quel est le nom de la personne qui a demandé / reçu ce Kindergeld ?",
        "ما اسم الشخص الذي طلب أو حصل على ذلك الـ Kindergeld؟",
        "O Kindergeld'i başvuran/alan kişinin adı nedir?",
        "Si quhet personi që e aplikoi / mori atë Kindergeld?",
    )),
    W_F4_GEBDAT: _Q((
        "What is that person's date of birth?",
        "Wann wurde diese Person geboren?",
        "Quelle est la date de naissance de cette personne ?",
        "ما تاريخ ميلاد ذلك الشخص؟",
        "Bu kişinin doğum tarihi nedir?",
        "Cila është data e lindjes së këtij personi?",
    ), ex="01.01.1985", fmt="date"),
    W_F4_ZEITRAUM: _Q((
        "For which period was that Kindergeld received?",
        "Für welchen Zeitraum wurde das Kindergeld bezogen (ab/von - bis)?",
        "Pour quelle période ce Kindergeld a-t-il été perçu ?",
        "لأي فترة تم استلام ذلك الـ Kindergeld؟",
        "O Kindergeld hangi dönem için alındı?",
        "Për cilën periudhë është marrë ai Kindergeld?",
    ), ex="01.2020 - 12.2023", fmt="period"),
    W_F4_FAMKA: _Q((
        "Which Familienkasse paid it (name and address)?",
        "Welche Familienkasse hat gezahlt (Name, Anschrift)?",
        "Quelle Familienkasse l'a versé (nom et adresse) ?",
        "أي Familienkasse دفعتها (الاسم والعنوان)؟",
        "Hangi Familienkasse ödedi (ad ve adres)?",
        "Cila Familienkasse e pagoi (emri dhe adresa)?",
    )),
    W_F4_KGNR: _Q((
        "What was the Kindergeld number of that earlier claim? Write - if unknown.",
        "Wie lautete die Kindergeldnummer des früheren Bezugs? Schreiben Sie -, wenn unbekannt.",
        "Quel était le numéro Kindergeld de cette demande antérieure ? Écrivez - si inconnu.",
        "ما رقم Kindergeld لذلك الطلب السابق؟ اكتب - إذا كان مجهولاً.",
        "Önceki başvurunun Kindergeld numarası neydi? Bilinmiyorsa - yazın.",
        "Cili ishte numri i Kindergeld i asaj kërkese të mëparshme? Shkruani - nëse nuk dihet.",
    )),

    # ── Punkt 5 ──────────────────────────────────────────────────────────
    L_OEFF_DIENST: _Q((
        "Are you (or a person from section 2 related to the child) employed in the German public service (öffentlicher Dienst)?",
        "Sind Sie oder eine unter Punkt 2 genannte Person im öffentlichen Dienst tätig?",
        "Vous ou une personne du point 2 travaillez-vous dans la fonction publique allemande (öffentlicher Dienst) ?",
        "هل تعمل أنت (أو شخص من النقطة 2) في الخدمة العامة الألمانية؟",
        "Siz (veya 2. bölümdeki bir kişi) Alman kamu hizmetinde mi çalışıyorsunuz?",
        "A punoni ju (ose një person nga pika 2) në shërbimin publik gjerman?",
    )),
    L_DIENST_BUND: _Q((
        "Is this employment at a federal institution (Einrichtung des Bundes)?",
        "Wird die Beschäftigung in einer Einrichtung des Bundes ausgeübt?",
        "Cet emploi est-il exercé dans une institution fédérale (Einrichtung des Bundes) ?",
        "هل هذا العمل في مؤسسة اتحادية؟",
        "Bu iş federal bir kurumda mı yürütülüyor?",
        "A ushtrohet kjo punë në një institucion federal?",
    )),
    L_DIENST_BA: _Q((
        "Is it at the Bundesagentur für Arbeit or a Jobcenter?",
        "Wird die Beschäftigung bei der Bundesagentur für Arbeit oder einem Jobcenter ausgeübt?",
        "Est-ce à la Bundesagentur für Arbeit ou dans un Jobcenter ?",
        "هل هو لدى وكالة العمل الاتحادية أو جوب سنتر؟",
        "Bundesagentur für Arbeit'te veya bir Jobcenter'da mı?",
        "A është te Bundesagentur für Arbeit ose në një Jobcenter?",
    )),
    W_F5_NAME: _Q((
        "What is the name of the person working in the public service?",
        "Wie heißt die betreffende Person im öffentlichen Dienst (Familienname, Vorname)?",
        "Quel est le nom de la personne travaillant dans la fonction publique ?",
        "ما اسم الشخص العامل في الخدمة العامة؟",
        "Kamu hizmetinde çalışan kişinin adı nedir?",
        "Si quhet personi që punon në shërbimin publik?",
    )),
    W_F5_GEBDAT: _Q((
        "What is that person's date of birth?",
        "Wann wurde diese Person geboren?",
        "Quelle est la date de naissance de cette personne ?",
        "ما تاريخ ميلاد ذلك الشخص؟",
        "Bu kişinin doğum tarihi nedir?",
        "Cila është data e lindjes së këtij personi?",
    ), ex="01.01.1985", fmt="date"),

    # ── Punkt 6 ──────────────────────────────────────────────────────────
    L_AUSL_LEISTUNG: _Q((
        "In the last 5 years, did you or a person from section 2 have a claim to a child benefit from outside Germany or from an international organisation?",
        "Bestand in den letzten 5 Jahren für Sie oder eine unter Punkt 2 genannte Person ein Anspruch auf eine kindbezogene Geldleistung aus dem Ausland oder von einer über-/zwischenstaatlichen Einrichtung?",
        "Au cours des 5 dernières années, vous ou une personne du point 2 aviez-vous droit à une prestation pour enfant d'un organisme hors d'Allemagne ou international ?",
        "خلال السنوات الخمس الماضية، هل كان لك أو لشخص من النقطة 2 حق في إعانة طفل من جهة خارج ألمانيا أو منظمة دولية؟",
        "Son 5 yılda siz veya 2. bölümdeki bir kişi, Almanya dışından veya uluslararası bir kuruluştan çocuk yardımı hakkına sahip oldunuz mu?",
        "Në 5 vitet e fundit, a keni pasur ju ose një person nga pika 2 të drejtë për një përfitim fëmije nga jashtë Gjermanisë ose nga një organizatë ndërkombëtare?",
    )),
    W_F6_NAME: _Q((
        "What is the name of the person receiving that benefit?",
        "Wie heißt die beziehende Person (Familienname, Vorname)?",
        "Quel est le nom de la personne qui reçoit cette prestation ?",
        "ما اسم الشخص الذي يتلقى تلك الإعانة؟",
        "O yardımı alan kişinin adı nedir?",
        "Si quhet personi që merr atë përfitim?",
    )),
    W_F6_GEBDAT: _Q((
        "What is that person's date of birth?",
        "Wann wurde diese Person geboren?",
        "Quelle est la date de naissance de cette personne ?",
        "ما تاريخ ميلاد ذلك الشخص؟",
        "Bu kişinin doğum tarihi nedir?",
        "Cila është data e lindjes së këtij personi?",
    ), ex="01.01.1985", fmt="date"),
    W_F6_LEISTUNG: _Q((
        "What is the name of the benefit (e.g. allocations familiales, child benefit)?",
        "Wie heißt die Leistung (z. B. allocations familiales, child benefit)?",
        "Quel est le nom de la prestation (par ex. allocations familiales) ?",
        "ما اسم الإعانة (مثلاً allocations familiales)؟",
        "Yardımın adı nedir (örn. allocations familiales, child benefit)?",
        "Si quhet përfitimi (p.sh. allocations familiales, child benefit)?",
    )),
    W_F6_BETRAG: _Q((
        "What is the monthly amount in euros?",
        "Wie hoch ist der monatliche Betrag in Euro?",
        "Quel est le montant mensuel en euros ?",
        "كم المبلغ الشهري باليورو؟",
        "Aylık tutar kaç euro?",
        "Sa është shuma mujore në euro?",
    ), ex="120"),
    W_F6_ZEITRAUM: _Q((
        "For which period is/was the benefit received?",
        "Für welchen Zeitraum wird/wurde die Leistung bezogen (ab/von - bis)?",
        "Pour quelle période la prestation est/était-elle perçue ?",
        "لأي فترة تُستلم/استُلمت الإعانة؟",
        "Yardım hangi dönemde alınıyor/alındı?",
        "Për cilën periudhë merret/u mor përfitimi?",
    ), ex="01.2022 - 12.2025", fmt="period"),
    W_F6_STELLE: _Q((
        "Which authority pays it (name and address)?",
        "Welche Stelle leistet (Name, Anschrift)?",
        "Quel organisme la verse (nom et adresse) ?",
        "أي جهة تدفعها (الاسم والعنوان)؟",
        "Hangi kurum ödüyor (ad ve adres)?",
        "Cili institucion e paguan (emri dhe adresa)?",
    )),
    W_F6_AZ: _Q((
        "What is the file number (Aktenzeichen) at that authority? Write - if unknown.",
        "Wie lautet das Aktenzeichen bei dieser Stelle? Schreiben Sie -, wenn unbekannt.",
        "Quel est le numéro de dossier auprès de cet organisme ? Écrivez - si inconnu.",
        "ما رقم الملف لدى تلك الجهة؟ اكتب - إذا كان مجهولاً.",
        "O kurumdaki dosya numarası nedir? Bilinmiyorsa - yazın.",
        "Cili është numri i dosjes në atë institucion? Shkruani - nëse nuk dihet.",
    ), ex="-"),

    # ── Punkt 7 ──────────────────────────────────────────────────────────
    L_7A: _Q((
        "In the last 5 years, were you or a person from section 2 employed, self-employed or a development worker outside Germany?",
        "Waren Sie oder eine unter Punkt 2 genannte Person in den letzten 5 Jahren außerhalb Deutschlands als Arbeitnehmer(in), Selbständige(r) oder Entwicklungshelfer(in) tätig?",
        "Au cours des 5 dernières années, vous ou une personne du point 2 avez-vous travaillé hors d'Allemagne (salarié, indépendant, coopérant) ?",
        "خلال السنوات الخمس الماضية، هل عملت أنت أو شخص من النقطة 2 خارج ألمانيا (موظفًا، مستقلاً، عامل تنمية)؟",
        "Son 5 yılda siz veya 2. bölümdeki bir kişi Almanya dışında çalıştınız mı (işçi, serbest, kalkınma görevlisi)?",
        "Në 5 vitet e fundit, a keni punuar ju ose një person nga pika 2 jashtë Gjermanisë (i punësuar, i vetëpunësuar, ndihmës zhvillimi)?",
    )),
    L_7B: _Q((
        "Were you or that person employed in Germany at an agency of another state or as a member of the NATO forces?",
        "Waren Sie oder diese Person in Deutschland bei einer Dienststelle eines anderen Staates oder als Angehörige(r) der NATO-Streitkräfte tätig?",
        "Vous ou cette personne avez-vous travaillé en Allemagne pour un organisme d'un autre État ou comme membre des forces de l'OTAN ?",
        "هل عملت أنت أو ذلك الشخص في ألمانيا لدى جهة تابعة لدولة أخرى أو ضمن قوات الناتو؟",
        "Siz veya o kişi Almanya'da başka bir devletin kurumunda veya NATO kuvvetleri mensubu olarak çalıştınız mı?",
        "A keni punuar ju ose ai person në Gjermani për një institucion të një shteti tjetër ose si pjesëtar i forcave të NATO-s?",
    )),
    L_7C: _Q((
        "Were you or that person employed in Germany but sent by an employer based outside Germany (posted worker)?",
        "Waren Sie oder diese Person in Deutschland auf Veranlassung eines Arbeitgebers mit Sitz im Ausland beschäftigt (entsandte Person)?",
        "Vous ou cette personne avez-vous travaillé en Allemagne pour un employeur établi à l'étranger (travailleur détaché) ?",
        "هل عملت أنت أو ذلك الشخص في ألمانيا بتكليف من صاحب عمل مقره خارج ألمانيا (موظف موفد)؟",
        "Siz veya o kişi, merkezi yurt dışında olan bir işveren tarafından Almanya'da mı çalıştırıldınız (görevlendirilmiş çalışan)?",
        "A keni punuar ju ose ai person në Gjermani i dërguar nga një punëdhënës me seli jashtë vendit (punonjës i deleguar)?",
    )),
    W_F7_NAME: _Q((
        "What is the name of the person with this employment?",
        "Wie heißt die beschäftigte Person (Familienname, Vorname)?",
        "Quel est le nom de la personne concernée par cet emploi ?",
        "ما اسم الشخص صاحب هذا العمل؟",
        "Bu işte çalışan kişinin adı nedir?",
        "Si quhet personi me këtë punësim?",
    )),
    W_F7_ZEITRAUM: _Q((
        "For which period (from - to)?",
        "Für welchen Zeitraum (ab/von - bis)?",
        "Pour quelle période (de - à) ?",
        "لأي فترة (من - إلى)؟",
        "Hangi dönem için (başlangıç - bitiş)?",
        "Për cilën periudhë (nga - deri)?",
    ), ex="01.2023 - 12.2024", fmt="period"),
    W_F7_AG: _Q((
        "What is the name of the employer / institution (with personnel number if any)?",
        "Wie heißt der Dienstherr/Arbeitgeber bzw. das Unternehmen (ggf. mit Personalnummer)?",
        "Quel est le nom de l'employeur / de l'institution (avec numéro de personnel le cas échéant) ?",
        "ما اسم صاحب العمل / المؤسسة (مع الرقم الوظيفي إن وجد)؟",
        "İşverenin/kurumun adı nedir (varsa personel numarasıyla)?",
        "Si quhet punëdhënësi / institucioni (me numër personeli nëse ka)?",
    )),
    W_F7_ANSCHRIFT: _Q((
        "What is the address of this employer / institution?",
        "Wie lautet die Anschrift dieses Arbeitgebers / dieser Einrichtung?",
        "Quelle est l'adresse de cet employeur / cette institution ?",
        "ما عنوان صاحب العمل / المؤسسة؟",
        "Bu işverenin/kurumun adresi nedir?",
        "Cila është adresa e këtij punëdhënësi / institucioni?",
    )),
    W_F7_ORT: _Q((
        "In which place/country was the work performed?",
        "In welchem Ort/Land wurde die Tätigkeit ausgeübt?",
        "Dans quel lieu/pays le travail a-t-il été exercé ?",
        "في أي مكان/بلد تم العمل؟",
        "İş hangi yerde/ülkede yapıldı?",
        "Në cilin vend/shtet u krye puna?",
    ), ex=("Paris, France", "Paris, Frankreich", "Paris, France",
           "باريس، فرنسا", "Paris, Fransa", "Paris, Francë")),

    # ── Erklärung ────────────────────────────────────────────────────────
    W_DATUM: _Q((
        "What is today's date (date of signature)?",
        "Welches Datum hat heute (Datum der Unterschrift)?",
        "Quelle est la date d'aujourd'hui (date de signature) ?",
        "ما تاريخ اليوم (تاريخ التوقيع)؟",
        "Bugünün tarihi nedir (imza tarihi)?",
        "Cila është data e sotme (data e nënshkrimit)?",
    ), helps=(
        "You sign the printed form by hand.",
        "Die Unterschrift leisten Sie von Hand auf dem ausgedruckten Formular.",
        "Vous signez le formulaire imprimé à la main.",
        "توقع على النموذج المطبوع بخط اليد.",
        "Yazdırılan formu elle imzalarsınız.",
        "Formularin e printuar e nënshkruani me dorë.",
    ), ex="12.06.2026", fmt="date"),
}


def _register_kg1ank_verified_questions() -> None:
    """Merge Anlage Kind verified questions into VERIFIED_BY_FIELD_ID.
    Runs once at module import (lazily via form_templates._all_templates())."""
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    VERIFIED_BY_FIELD_ID.update(_QUESTIONS)


_register_kg1ank_verified_questions()
