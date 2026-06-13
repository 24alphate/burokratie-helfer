"""
Verified field map for the Kinderzuschlag "Anlage Kind" (KiZ 1-AnK).

Fifth Level 1 verified template, filled once per child alongside the KiZ 1
main application. It is mostly a declaration checklist: the child's data +
relationship, then a long list of income and expense categories the family
ticks ("this applies / I attach proof"). XFA-styled (topmostSubform[0]…,
/Btn stubs without /AP) → fill_strategy="fitz_acroform".

Source PDF
----------
templates_source/incoming/kiz1_anlage_kind.pdf
(official: arbeitsagentur.de/datei/kiz1-ank_ba035005.pdf, Stand 01/2025)

Fingerprint
-----------
Required (all): the form-unique footer "kiz 1-ank" + the section heading
"mehrbedarf des kindes". Both appear ONLY on this form — verified against
every PDF in templates_source/incoming/ (the KiZ1 main has "kiz 1 - seite",
the KG Anlage Kind has "kg 1 ank").

Field strategy (v1)
-------------------
- Header (3) + child data (3 text) + two relationship radios + 7 circumstance
  yes/no boxes + Mehrbedarf (gated delivery date) + the Section 3 income
  checklist + the Section 4 expense checklist + signature date.
- Relationship is two logical radios (to me / to partner), each covering two
  /Btn widgets (eigenes / Stief) with a no-widget "keine Angabe" skip option.
- Income/expense categories are independent yes/no checkboxes — the honest
  model of a "tick what applies" official checklist. A few detail text fields
  (holiday-job period, car km / work days) and the employer-certificate box
  are gated on their parent answer.

Every shown field has a verified question in en/de/fr/ar/tr/sq.
weak_questions=0 and ai_calls_made=0 invariants must hold.
"""
from __future__ import annotations

from app.services.form_templates import RadioGroup, VerifiedTemplate

_P1 = "topmostSubform[0].Page1[0]"
_P2 = "topmostSubform[0].Page2[0]"

# ── Header ────────────────────────────────────────────────────────────────────
W_NAME_KGB    = _P1 + ".Kopfzeile[0].Name_Vorname_KGB[0]"
W_KG_NR       = _P1 + ".Kopfzeile[0].KG-Nr[0]"
W_ANTRAGSDAT  = _P1 + ".Kopfzeile[0].Antragsdatum[0]"

# ── Punkt 1 — Angaben zum Kind ────────────────────────────────────────────────
W_CHILD_NAME      = _P1 + ".Punkt-1[0].Angaben-Kind[0].Name_Vorname_Kind[0]"
W_CHILD_STAATSANG = _P1 + ".Punkt-1[0].Angaben-Kind[0].Staatsangehörigkeit[0]"
W_CHILD_GEBDATUM  = _P1 + ".Punkt-1[0].Angaben-Kind[0].Geburtsdatum[0]"

# Verwandtschaftsverhältnis (NOTE: widget folder is misspelled "Verwandschaft")
_VW = _P1 + ".Punkt-1[0].Verwandschaftsverhältnis[0]"
W_REL_EIGEN_ME  = _VW + ".eigenes-A[0]"
W_REL_EIGEN_PRT = _VW + ".eigenes-P[0]"
W_REL_STIEF_ME  = _VW + ".Stief-A[0]"
W_REL_STIEF_PRT = _VW + ".Stief-P[0]"

# Verhältnisse — 7 independent circumstance checkboxes
_VH = _P1 + ".Punkt-1[0].Verhältnisse[0]"
W_VERHEIRATET   = _VH + ".verheiratet[0]"
W_EIGENES_KIND  = _VH + ".eigenes-Kind[0]"
W_ZUSAMMEN      = _VH + ".zusammenlebend[0]"
W_SCHULE        = _VH + ".Schule[0]"
W_WOHNHEIM      = _VH + ".Wohnheim[0]"
W_STATIONAER    = _VH + ".stationäre-Unterbring[0]"
W_KEINE_ANGABE  = _VH + ".keine-Angabe[0]"

# ── Punkt 2 — Mehrbedarf ──────────────────────────────────────────────────────
W_MEHRBEDARF   = _P1 + ".Punkt-2[0].Mehrbedarf-ja[0]"
W_ENTBINDUNG   = _P1 + ".Punkt-2[0].Entbindungstermin[0]"

# ── Punkt 3 — Einnahmen (page 1) ──────────────────────────────────────────────
_P3 = _P1 + ".Punkt-3[0]"
W_LOHN          = _P3 + ".Zeile-Lohn[0].Lohn-Kind[0]"
W_VERDIENSTBESCH = _P3 + ".Zeile-Lohn[0].Verdienstbesch-Kind[0]"
W_FERIENJOB     = _P3 + ".Zeile-Lohn[0].Ferienjob[0]"
W_SELBST        = _P3 + ".Zeile-Selbständige[0].KiZ5a-Kind[0]"
W_FWD           = _P3 + ".Zeile-FWD[0].FWD-Kind[0]"

# ── Punkt 3 continued (page 2) ────────────────────────────────────────────────
_P3F = _P2 + ".Punkt-3-Fortsetzung[0]"
_EK = _P3F + ".Zeile-and-Einkommen[0]"
W_ALG2        = _EK + ".Alg-2-Kind[0]"
W_ALG1        = _EK + ".Alg-1-Kind[0]"
W_KRANKENGELD = _EK + ".Krankengeld-Kind[0]"
W_RENTE       = _EK + ".Rente-Kind[0]"
W_BAFOEG      = _EK + ".Bafög-Kind[0]"
W_STAATL      = _EK + ".staatl-Leist-Kind[0]"
_UH = _P3F + ".Zeile-Unterhalt[0]"
W_UNTERHALT   = _UH + ".UH-Kind[0]"
W_UH_VORSCHUSS = _UH + ".Unterhaltsvorschuss-Kind[0]"
W_KEIN_UH     = _UH + ".KiZ5c-Kind[0]"
W_SONST_EK    = _P3F + ".Zeile-sonst-Einnahmen[0].sonst-EK-Kind[0]"

# ── Punkt 4 — Ausgaben (page 2) ───────────────────────────────────────────────
_P4 = _P2 + ".Punkt-4[0]"
_WK = _P4 + ".Zeile-Werbungskosten[0]"
W_FK_OEFFIS  = _WK + ".Fahrtkosten[0].FK-Öffis[0]"
W_FK_KM      = _WK + ".Fahrtkosten[0].FK-KfZ-km-A[0]"
W_FK_TAGE    = _WK + ".Fahrtkosten[0].FK-Tage-A[0]"
W_DOPP_HH    = _WK + ".#area[11].dopp-HH-KInd[0]"
W_VERPFLEG   = _WK + ".#area[12].Verpfleg-Kind[0]"
W_SONST_WK   = _WK + ".#area[13].sonst-WK-Kind[0]"
_VERS = _P4 + ".Zeile-Versicherungen[0]"
W_KFZ_HAFTPFL = _VERS + ".Kfz-Haftpflicht-Kind[0]"
W_ALTERSVORS  = _VERS + ".Altersvorsorge-Kind[0]"
W_SONST_VERS  = _VERS + ".sonst-Versich-Kind[0]"
W_UH_ZAHLUNG = _P4 + ".Zeile-Unterhaltszahlungen[0].Unterhaltszahl-Kind[0]"

# ── Signature ─────────────────────────────────────────────────────────────────
W_DATUM = _P2 + ".Erklärung[0].Unterschriftenzeile[0].Datum\\.Antrag\\.0[0]"

# ── Logical IDs ───────────────────────────────────────────────────────────────
L_REL_ME      = "kizank_rel_me"
L_REL_PARTNER = "kizank_rel_partner"

_REL_OPTIONS = ["eigenes (leibliches) Kind", "Stiefkind"]
_REL_NONE = "keine Angabe"


# ── Conditions ────────────────────────────────────────────────────────────────
def _yes(field_key: str) -> dict:
    return {"type": "field_equals", "field_key": field_key, "value": "yes"}


def _not_skip(field_key: str) -> dict:
    return {"type": "field_not_equals", "field_key": field_key, "value": "-"}


_C_MEHRBEDARF = _yes(W_MEHRBEDARF)
_C_LOHN = _yes(W_LOHN)


_REQUIRED = [
    "kiz 1-ank",            # footer — unique to the KiZ Anlage Kind
    "mehrbedarf des kindes",
]


class Kiz1AnlageKindTemplate(VerifiedTemplate):
    template_id   = "kiz1_anlage_kind_v1"
    name          = "Familienkasse — Anlage Kind zum Antrag auf Kinderzuschlag (KiZ 1-AnK)"
    fill_strategy = "fitz_acroform"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        return all(p in lo for p in _REQUIRED)

    def get_field_map(self) -> list:
        from app.services.pdf_pipeline import FieldMapEntry

        def auto(field_id, label, ftype, page, opts=None, src_text=None,
                 condition=None):
            return FieldMapEntry(
                field_id=field_id, original_label=label, field_type=ftype,
                source_page=page, options=opts or [], current_value="",
                confidence=1.0, source="verified_template",
                source_text=src_text or label, reason="pdf_field",
                condition=condition,
            )

        rel_opts = _REL_OPTIONS + [_REL_NONE]

        return [
            # ── Header ───────────────────────────────────────────────────
            auto(W_NAME_KGB, "Name, Vorname der kindergeldbeziehenden Person",
                 "text", 1, src_text="Familienname und Vorname der kindergeldbeziehenden Person"),
            auto(W_KG_NR, "Kindergeld-Nummer", "text", 1, src_text="Kindergeld-Nr."),
            auto(W_ANTRAGSDAT, "Datum des Kinderzuschlagsantrags", "text", 1,
                 src_text="zum Antrag auf Kinderzuschlag vom"),

            # ── Punkt 1 — Angaben zum Kind ───────────────────────────────
            auto(W_CHILD_NAME, "Familienname, Vorname des Kindes", "text", 1),
            auto(W_CHILD_GEBDATUM, "Geburtsdatum des Kindes", "text", 1),
            auto(W_CHILD_STAATSANG, "Staatsangehörigkeit des Kindes", "text", 1),
            auto(L_REL_ME, "Verwandtschaftsverhältnis des Kindes zu mir",
                 "radio", 1, opts=rel_opts,
                 src_text="Verwandtschaftsverhältnis des Kindes zu mir"),
            auto(L_REL_PARTNER,
                 "Verwandtschaftsverhältnis des Kindes zu meinem/meiner Partner(in)",
                 "radio", 1, opts=rel_opts,
                 src_text="Verwandtschaftsverhältnis des Kindes zum/zur Partner(in)"),

            # Circumstance checkboxes
            auto(W_VERHEIRATET, "Kind ist verheiratet", "checkbox", 1,
                 src_text="Mein Kind ist verheiratet"),
            auto(W_EIGENES_KIND, "Kind hat ein eigenes Kind", "checkbox", 1,
                 src_text="Mein Kind hat ein eigenes Kind"),
            auto(W_ZUSAMMEN, "Kind lebt mit Partner(in) zusammen", "checkbox", 1,
                 src_text="lebt mit seiner Partnerin/seinem Partner zusammen"),
            auto(W_SCHULE, "Kind besucht berufsbildende Schule oder studiert",
                 "checkbox", 1,
                 src_text="besucht eine berufsbildende Schule oder studiert"),
            auto(W_WOHNHEIM,
                 "Kind ist während der Ausbildung auswärts untergebracht",
                 "checkbox", 1,
                 src_text="ist während der Ausbildung in einem Wohnheim, Internat … untergebracht"),
            auto(W_STATIONAER, "Kind befindet sich in stationärer Einrichtung",
                 "checkbox", 1, src_text="befindet sich in einer stationären Einrichtung"),
            auto(W_KEINE_ANGABE, "Keine dieser Angaben trifft zu", "checkbox", 1,
                 src_text="keine der Angaben trifft zu"),

            # ── Punkt 2 — Mehrbedarf ─────────────────────────────────────
            auto(W_MEHRBEDARF, "Kind hat einen Mehrbedarf", "checkbox", 1,
                 src_text="Mein Kind hat einen Mehrbedarf"),
            auto(W_ENTBINDUNG, "Voraussichtlicher Entbindungstermin", "text", 1,
                 src_text="voraussichtlicher Entbindungstermin", condition=_C_MEHRBEDARF),

            # ── Punkt 3 — Einnahmen ──────────────────────────────────────
            auto(W_LOHN, "Ausbildungsvergütung / Arbeitslohn / Gehalt",
                 "checkbox", 1,
                 src_text="Ausbildungsvergütung / Arbeitslohn / Gehalt"),
            auto(W_VERDIENSTBESCH,
                 "Verdienstbescheinigung des Arbeitgebers wird beigefügt",
                 "checkbox", 1,
                 src_text="Vordruck Verdienstbescheinigung des Arbeitgebers",
                 condition=_C_LOHN),
            auto(W_FERIENJOB, "Zeitraum des Ferienjobs", "text", 1,
                 src_text="Zeitraum des Ferienjobs", condition=_C_LOHN),
            auto(W_SELBST, "Einkommen aus selbständiger Tätigkeit", "checkbox", 1,
                 src_text="Einkommen aus selbständiger Tätigkeit"),
            auto(W_FWD,
                 "Einkommen aus Freiwilligendienst / ehrenamtlicher Tätigkeit",
                 "checkbox", 1,
                 src_text="Einkommen aus Bundesfreiwilligendienst oder gemeinnütziger Tätigkeit"),
            auto(W_ALG2, "Bürgergeld / Sozialhilfe / Asylbewerberleistungen",
                 "checkbox", 2,
                 src_text="Bürgergeld / Sozialhilfe / Leistungen für Asylbewerber"),
            auto(W_ALG1, "Arbeitslosengeld", "checkbox", 2),
            auto(W_KRANKENGELD, "Krankengeld / Verletztengeld / Übergangsgeld",
                 "checkbox", 2),
            auto(W_RENTE, "Rente / Halbwaisenrente", "checkbox", 2),
            auto(W_BAFOEG, "BAföG / Stipendium / Berufsausbildungsbeihilfe",
                 "checkbox", 2),
            auto(W_STAATL, "Sonstige staatliche Leistungen", "checkbox", 2),
            auto(W_UNTERHALT, "Unterhalt", "checkbox", 2),
            auto(W_UH_VORSCHUSS, "Unterhaltsvorschuss", "checkbox", 2),
            auto(W_KEIN_UH, "Kein Unterhalt und/oder Unterhaltsvorschuss",
                 "checkbox", 2,
                 src_text="keinen Unterhalt und/oder Unterhaltsvorschuss"),
            auto(W_SONST_EK,
                 "Sonstige Einnahmen (z. B. Zinsen, Steuerrückerstattung)",
                 "checkbox", 2, src_text="Sonstige Einnahmen"),

            # ── Punkt 4 — Ausgaben ───────────────────────────────────────
            auto(W_FK_OEFFIS, "Fahrtkosten mit öffentlichen Verkehrsmitteln",
                 "checkbox", 2,
                 src_text="Fahrkarten für öffentliche Verkehrsmittel"),
            auto(W_FK_KM, "Einfache Wegstrecke zur Arbeit in km (bei KfZ)",
                 "text", 2, src_text="einfache Wegstrecke (Hinfahrt) zur Arbeitsstätte in km"),
            auto(W_FK_TAGE, "Arbeitstage pro Woche", "text", 2,
                 src_text="Arbeitstage pro Woche", condition=_not_skip(W_FK_KM)),
            auto(W_DOPP_HH, "Aufwendungen bei doppelter Haushaltsführung",
                 "checkbox", 2,
                 src_text="Aufwendungen bei doppelter Haushaltsführung"),
            auto(W_VERPFLEG, "Verpflegungsmehraufwendungen", "checkbox", 2),
            auto(W_SONST_WK,
                 "Sonstige Werbungskosten (z. B. Gewerkschaftsbeitrag)",
                 "checkbox", 2, src_text="Sonstige Werbungskosten"),
            auto(W_KFZ_HAFTPFL, "Kfz-Haftpflichtversicherung", "checkbox", 2,
                 src_text="Kfz-Haftpflichtversicherung (ohne Voll-/Teilkasko)"),
            auto(W_ALTERSVORS, "Altersvorsorgebeiträge (z. B. Riester)",
                 "checkbox", 2, src_text="Altersvorsorgebeiträge"),
            auto(W_SONST_VERS,
                 "Beiträge zur Kranken-/Pflegeversicherung oder Altersvorsorge",
                 "checkbox", 2,
                 src_text="Beiträge zur Kranken-/Pflegeversicherung; Altersvorsorge"),
            auto(W_UH_ZAHLUNG, "Unterhaltszahlungen", "checkbox", 2,
                 src_text="Unterhaltszahlungen"),

            # ── Signature ────────────────────────────────────────────────
            auto(W_DATUM, "Datum (Unterschrift)", "text", 2,
                 src_text="Datum / Unterschrift"),
        ]

    def get_radio_groups(self) -> list[RadioGroup]:
        def _rel(field_id, w_eigen, w_stief):
            return RadioGroup(
                field_id=field_id,
                widget_names=[w_eigen, w_stief],
                options=[(_REL_OPTIONS[0], w_eigen), (_REL_OPTIONS[1], w_stief)],
            )
        return [
            _rel(L_REL_ME, W_REL_EIGEN_ME, W_REL_STIEF_ME),
            _rel(L_REL_PARTNER, W_REL_EIGEN_PRT, W_REL_STIEF_PRT),
        ]


# ── Verified questions (en/de/fr/ar/tr/sq) ────────────────────────────────────

_LOCALES = ("en", "de", "fr", "ar", "tr", "sq")
_DATE_FMT = {
    "en": "DD.MM.YYYY", "de": "TT.MM.JJJJ", "fr": "JJ.MM.AAAA",
    "ar": "DD.MM.YYYY", "tr": "GG.AA.YYYY", "sq": "DD.MM.VVVV",
}


def _Q(qs, helps=None, ex=None, fmt=None):
    out = {}
    for i, loc in enumerate(_LOCALES):
        d = {"question": qs[i]}
        if helps:
            d["help"] = helps[i]
        if ex is not None:
            d["example"] = ex if isinstance(ex, str) else ex[i]
        if fmt == "date":
            d["format"] = _DATE_FMT[loc]
        out[loc] = d
    return out


# Helper for the income/expense "did the child have X in the last 6 months?"
# yes/no boxes — keeps the long checklist consistent and DRY.
def _had(noun6, attach6=None):
    qs = (
        f"In the last 6 months, did your child have {noun6[0]}?",
        f"Hatte Ihr Kind in den letzten 6 Monaten {noun6[1]}?",
        f"Au cours des 6 derniers mois, votre enfant a-t-il eu {noun6[2]} ?",
        f"خلال الأشهر الستة الماضية، هل حصل طفلك على {noun6[3]}؟",
        f"Son 6 ayda çocuğunuzun {noun6[4]} oldu mu?",
        f"Në 6 muajt e fundit, a pati fëmija juaj {noun6[5]}?",
    )
    helps = None
    if attach6:
        helps = (
            f"If yes, attach: {attach6[0]}.",
            f"Falls ja, fügen Sie bei: {attach6[1]}.",
            f"Si oui, joignez : {attach6[2]}.",
            f"إذا نعم، أرفق: {attach6[3]}.",
            f"Evetse ekleyin: {attach6[4]}.",
            f"Nëse po, bashkëngjisni: {attach6[5]}.",
        )
    return _Q(qs, helps=helps)


def _expense(noun6, attach6=None):
    qs = (
        f"In the last 6 months, did your child have expenses for {noun6[0]}?",
        f"Hatte Ihr Kind in den letzten 6 Monaten Ausgaben für {noun6[1]}?",
        f"Au cours des 6 derniers mois, votre enfant a-t-il eu des dépenses pour {noun6[2]} ?",
        f"خلال الأشهر الستة الماضية، هل كان لطفلك نفقات على {noun6[3]}؟",
        f"Son 6 ayda çocuğunuzun {noun6[4]} için gideri oldu mu?",
        f"Në 6 muajt e fundit, a pati fëmija juaj shpenzime për {noun6[5]}?",
    )
    helps = None
    if attach6:
        helps = (
            f"If yes, attach: {attach6[0]}.",
            f"Falls ja, fügen Sie bei: {attach6[1]}.",
            f"Si oui, joignez : {attach6[2]}.",
            f"إذا نعم، أرفق: {attach6[3]}.",
            f"Evetse ekleyin: {attach6[4]}.",
            f"Nëse po, bashkëngjisni: {attach6[5]}.",
        )
    return _Q(qs, helps=helps)


_REL_HELP = (
    "eigenes (leibliches) Kind = your own biological child, Stiefkind = stepchild. "
    "Choose 'keine Angabe' if it does not apply.",
    "eigenes (leibliches) Kind oder Stiefkind. 'keine Angabe', wenn nicht zutreffend.",
    "eigenes (leibliches) Kind = enfant biologique, Stiefkind = bel-enfant. "
    "« keine Angabe » si sans objet.",
    "eigenes Kind = طفل بيولوجي، Stiefkind = ابن الزوج/الزوجة. 'keine Angabe' إذا لم ينطبق.",
    "eigenes Kind = öz çocuk, Stiefkind = üvey çocuk. Uygun değilse 'keine Angabe'.",
    "eigenes Kind = fëmijë biologjik, Stiefkind = thjeshtër. 'keine Angabe' nëse nuk aplikohet.",
)

_QUESTIONS: dict = {
    # ── Header ───────────────────────────────────────────────────────────
    W_NAME_KGB: _Q((
        "What is the family name and first name of the person who receives Kindergeld?",
        "Wie lauten Familienname und Vorname der kindergeldbeziehenden Person?",
        "Quels sont le nom et le prénom de la personne qui perçoit le Kindergeld ?",
        "ما اسم العائلة والاسم الشخصي للشخص الذي يتلقى Kindergeld؟",
        "Kindergeld alan kişinin soyadı ve adı nedir?",
        "Cili është mbiemri dhe emri i personit që merr Kindergeld?",
    ), ex="Diallo, Aminata"),
    W_KG_NR: _Q((
        "What is your Kindergeld number? Write - if you do not have one yet.",
        "Wie lautet Ihre Kindergeld-Nummer? Schreiben Sie -, wenn noch keine.",
        "Quel est votre numéro Kindergeld ? Écrivez - si vous n'en avez pas encore.",
        "ما هو رقم Kindergeld الخاص بك؟ اكتب - إذا لم يكن لديك بعد.",
        "Kindergeld numaranız nedir? Henüz yoksa - yazın.",
        "Cili është numri juaj i Kindergeld? Shkruani - nëse nuk e keni ende.",
    ), ex="115FK154720"),
    W_ANTRAGSDAT: _Q((
        "What is the date of the Kinderzuschlag application this child attachment belongs to?",
        "Vom welchem Datum ist der Kinderzuschlagsantrag, zu dem diese Anlage gehört?",
        "Quelle est la date de la demande de Kinderzuschlag à laquelle appartient cette annexe ?",
        "ما تاريخ طلب Kinderzuschlag الذي تتبع له هذه الملحقة؟",
        "Bu çocuk ekinin ait olduğu Kinderzuschlag başvurusunun tarihi nedir?",
        "Cila është data e aplikimit për Kinderzuschlag të cilit i përket kjo shtojcë?",
    ), ex="13.06.2026", fmt="date"),

    # ── Child ────────────────────────────────────────────────────────────
    W_CHILD_NAME: _Q((
        "What is the child's family name and first name?",
        "Wie lauten Familienname und Vorname des Kindes?",
        "Quels sont le nom et le prénom de l'enfant ?",
        "ما اسم عائلة الطفل واسمه الشخصي؟",
        "Çocuğun soyadı ve adı nedir?",
        "Cili është mbiemri dhe emri i fëmijës?",
    ), ex="Diallo, Ibrahim"),
    W_CHILD_GEBDATUM: _Q((
        "What is the child's date of birth?",
        "Wann wurde das Kind geboren?",
        "Quelle est la date de naissance de l'enfant ?",
        "ما تاريخ ميلاد الطفل؟",
        "Çocuğun doğum tarihi nedir?",
        "Cila është data e lindjes së fëmijës?",
    ), ex="15.03.2019", fmt="date"),
    W_CHILD_STAATSANG: _Q((
        "What is the child's nationality?",
        "Welche Staatsangehörigkeit hat das Kind?",
        "Quelle est la nationalité de l'enfant ?",
        "ما جنسية الطفل؟",
        "Çocuğun uyruğu nedir?",
        "Cila është shtetësia e fëmijës?",
    ), ex=("Guinean", "guineisch", "guinéenne", "غينية", "Gineli", "guineane")),
    L_REL_ME: _Q((
        "What is the child's relationship to YOU?",
        "In welchem Verwandtschaftsverhältnis steht das Kind zu IHNEN?",
        "Quel est le lien de parenté de l'enfant avec VOUS ?",
        "ما صلة قرابة الطفل بك أنت؟",
        "Çocuğun SİZE akrabalık ilişkisi nedir?",
        "Cila është lidhja farefisnore e fëmijës me JU?",
    ), helps=_REL_HELP),
    L_REL_PARTNER: _Q((
        "What is the child's relationship to your PARTNER? Choose 'keine Angabe' if you have no partner.",
        "In welchem Verwandtschaftsverhältnis steht das Kind zu Ihrem/Ihrer PARTNER(IN)? 'keine Angabe', wenn kein(e) Partner(in).",
        "Quel est le lien de l'enfant avec votre PARTENAIRE ? « keine Angabe » si vous n'avez pas de partenaire.",
        "ما صلة قرابة الطفل بشريكك؟ اختر 'keine Angabe' إذا لم يكن لديك شريك.",
        "Çocuğun PARTNERİNİZE akrabalık ilişkisi nedir? Partneriniz yoksa 'keine Angabe' seçin.",
        "Cila është lidhja e fëmijës me PARTNERIN tuaj? 'keine Angabe' nëse nuk keni partner.",
    ), helps=_REL_HELP),

    # ── Circumstance checkboxes ──────────────────────────────────────────
    W_VERHEIRATET: _Q((
        "Is your child married?",
        "Ist Ihr Kind verheiratet?",
        "Votre enfant est-il marié ?",
        "هل طفلك متزوج؟",
        "Çocuğunuz evli mi?",
        "A është fëmija juaj i martuar?",
    )),
    W_EIGENES_KIND: _Q((
        "Does your child have a child of their own?",
        "Hat Ihr Kind ein eigenes Kind?",
        "Votre enfant a-t-il son propre enfant ?",
        "هل لطفلك طفل خاص به؟",
        "Çocuğunuzun kendi çocuğu var mı?",
        "A ka fëmija juaj një fëmijë të vetin?",
    )),
    W_ZUSAMMEN: _Q((
        "Does your child live together with a partner?",
        "Lebt Ihr Kind mit einer Partnerin / einem Partner zusammen?",
        "Votre enfant vit-il avec un(e) partenaire ?",
        "هل يعيش طفلك مع شريك؟",
        "Çocuğunuz bir partnerle birlikte mi yaşıyor?",
        "A jeton fëmija juaj me një partner?",
    )),
    W_SCHULE: _Q((
        "Does your child attend a vocational school or study at university?",
        "Besucht Ihr Kind eine berufsbildende Schule oder studiert es?",
        "Votre enfant fréquente-t-il une école professionnelle ou fait-il des études ?",
        "هل يرتاد طفلك مدرسة مهنية أو يدرس في الجامعة؟",
        "Çocuğunuz meslek okuluna mı gidiyor veya üniversitede mi okuyor?",
        "A ndjek fëmija juaj një shkollë profesionale ose studion?",
    ), helps=(
        "If yes, please attach current proof (e.g. school/enrolment certificate).",
        "Falls ja, legen Sie bitte aktuelle Nachweise vor (z. B. Schulbescheinigung).",
        "Si oui, joignez un justificatif actuel (par ex. certificat de scolarité).",
        "إذا نعم، أرفق إثباتًا حديثًا (مثل شهادة مدرسية).",
        "Evetse güncel bir belge ekleyin (örn. okul belgesi).",
        "Nëse po, bashkëngjisni një vërtetim aktual (p.sh. vërtetim shkollor).",
    )),
    W_WOHNHEIM: _Q((
        "During training, is your child housed away from home (dormitory, boarding school, special facility, or with the employer with full board)?",
        "Ist Ihr Kind während der Ausbildung auswärts untergebracht (Wohnheim, Internat, besondere Einrichtung oder beim Ausbilder mit voller Verpflegung)?",
        "Pendant sa formation, votre enfant est-il logé ailleurs (foyer, internat, établissement spécialisé, ou chez l'employeur avec pension complète) ?",
        "أثناء التدريب، هل يقيم طفلك خارج المنزل (سكن، مدرسة داخلية، مؤسسة خاصة، أو لدى رب العمل بإقامة كاملة)؟",
        "Eğitim sırasında çocuğunuz dışarıda mı kalıyor (yurt, yatılı okul, özel kurum veya tam pansiyonla işverende)?",
        "Gjatë formimit, a është fëmija juaj i strehuar jashtë shtëpisë (konvikt, internat, institucion i veçantë, ose te punëdhënësi me ushqim të plotë)?",
    ), helps=(
        "If yes, please attach current proof.",
        "Falls ja, legen Sie bitte aktuelle Nachweise vor.",
        "Si oui, joignez un justificatif actuel.",
        "إذا نعم، أرفق إثباتًا حديثًا.",
        "Evetse güncel bir belge ekleyin.",
        "Nëse po, bashkëngjisni një vërtetim aktual.",
    )),
    W_STATIONAER: _Q((
        "Is your child in a residential (inpatient) institution?",
        "Befindet sich Ihr Kind in einer stationären Einrichtung?",
        "Votre enfant se trouve-t-il dans un établissement avec hébergement (stationnaire) ?",
        "هل طفلك في مؤسسة إقامة داخلية؟",
        "Çocuğunuz yatılı (kurum içi) bir kuruluşta mı?",
        "A ndodhet fëmija juaj në një institucion me qëndrim (stacionar)?",
    )),
    W_KEINE_ANGABE: _Q((
        "Do none of the statements above apply to your child?",
        "Trifft keine der obigen Angaben auf Ihr Kind zu?",
        "Aucune des affirmations ci-dessus ne s'applique-t-elle à votre enfant ?",
        "هل لا ينطبق أيٌّ مما سبق على طفلك؟",
        "Yukarıdaki ifadelerin hiçbiri çocuğunuza uymuyor mu?",
        "A nuk vlen asnjë nga pohimet e mësipërme për fëmijën tuaj?",
    ), helps=(
        "Tick this only if none of the six statements above are true.",
        "Nur ankreuzen, wenn keine der sechs obigen Angaben zutrifft.",
        "Cochez seulement si aucune des six affirmations ci-dessus n'est vraie.",
        "ضع علامة فقط إذا لم تكن أيٌّ من العبارات الست أعلاه صحيحة.",
        "Yalnızca yukarıdaki altı ifadeden hiçbiri doğru değilse işaretleyin.",
        "Shënoni vetëm nëse asnjë nga gjashtë pohimet e mësipërme nuk është e vërtetë.",
    )),

    # ── Mehrbedarf ───────────────────────────────────────────────────────
    W_MEHRBEDARF: _Q((
        "Does your child have an additional need (e.g. pregnancy, severe disability, costly diet)?",
        "Hat Ihr Kind einen Mehrbedarf (z. B. Schwangerschaft, Schwerbehinderung, kostenaufwändige Ernährung)?",
        "Votre enfant a-t-il un besoin supplémentaire (par ex. grossesse, handicap lourd, alimentation coûteuse) ?",
        "هل لطفلك حاجة إضافية (مثل حمل، إعاقة شديدة، تغذية مكلفة)؟",
        "Çocuğunuzun ek bir ihtiyacı var mı (örn. hamilelik, ağır engellilik, masraflı beslenme)?",
        "A ka fëmija juaj një nevojë shtesë (p.sh. shtatzëni, paaftësi e rëndë, ushqim i kushtueshëm)?",
    ), helps=(
        "This is voluntary — only fill in if you want the extra need considered. Attach suitable proof.",
        "Freiwillig — nur ausfüllen, wenn ein Mehrbedarf berücksichtigt werden soll. Geeignete Nachweise beifügen.",
        "Facultatif — à remplir seulement si vous voulez que ce besoin soit pris en compte. Joignez un justificatif.",
        "اختياري — املأ فقط إذا أردت أخذ الحاجة الإضافية بعين الاعتبار. أرفق إثباتًا مناسبًا.",
        "İsteğe bağlı — yalnızca ek ihtiyacın dikkate alınmasını istiyorsanız doldurun. Uygun belge ekleyin.",
        "Vullnetare — plotësojeni vetëm nëse doni që nevoja shtesë të merret parasysh. Bashkëngjisni dëshmi.",
    )),
    W_ENTBINDUNG: _Q((
        "If pregnant: what is the expected delivery date?",
        "Bei Schwangerschaft: Wie lautet der voraussichtliche Entbindungstermin?",
        "En cas de grossesse : quelle est la date prévue de l'accouchement ?",
        "في حالة الحمل: ما هو تاريخ الولادة المتوقع؟",
        "Hamilelik durumunda: tahmini doğum tarihi nedir?",
        "Në rast shtatzënie: cila është data e pritshme e lindjes?",
    ), ex="01.11.2026", fmt="date"),

    # ── Section 3 — income ──────────────────────────────────────────────
    W_LOHN: _had((
        "training pay, wages or salary",
        "Ausbildungsvergütung, Arbeitslohn oder Gehalt",
        "une rémunération d'apprentissage, un salaire ou un traitement",
        "أجر تدريب أو راتب أو مرتب",
        "eğitim ücreti, maaş veya ücret",
        "pagesë formimi, rrogë ose pagë",
    ), attach6=(
        "payslips (also for a mini/side job)",
        "Lohn-/Gehaltsabrechnungen (auch für Mini-/Nebenjob)",
        "des fiches de paie (aussi pour un mini-job)",
        "كشوف الرواتب (وأيضًا لوظيفة صغيرة)",
        "maaş bordroları (mini iş için de)",
        "fletëpagesat (edhe për një mini-punë)",
    )),
    W_VERDIENSTBESCH: _Q((
        "Are you attaching the employer's income certificate (Verdienstbescheinigung) instead of payslips?",
        "Fügen Sie statt Lohnabrechnungen die Verdienstbescheinigung des Arbeitgebers bei?",
        "Joignez-vous l'attestation de revenu de l'employeur (Verdienstbescheinigung) au lieu des fiches de paie ?",
        "هل ترفق شهادة دخل من صاحب العمل بدلاً من كشوف الرواتب؟",
        "Maaş bordroları yerine işverenin gelir belgesini (Verdienstbescheinigung) mi ekliyorsunuz?",
        "A po bashkëngjisni vërtetimin e të ardhurave nga punëdhënësi në vend të fletëpagesave?",
    )),
    W_FERIENJOB: _Q((
        "If the income was earned in a holiday job during school, what was the period of the holiday job?",
        "Wenn das Einkommen in einem Ferienjob während der Schulausbildung verdient wurde: Zeitraum des Ferienjobs?",
        "Si le revenu provient d'un job de vacances pendant la scolarité, quelle était la période du job de vacances ?",
        "إذا كُسب الدخل من وظيفة عطلة أثناء الدراسة: ما فترة وظيفة العطلة؟",
        "Gelir, okul döneminde bir tatil işinden kazanıldıysa: tatil işinin dönemi neydi?",
        "Nëse të ardhurat u fituan nga një punë pushimi gjatë shkollës: cila ishte periudha e punës së pushimit?",
    ), ex="07.2025 - 08.2025"),
    W_SELBST: _had((
        "income from self-employment",
        "Einkommen aus selbständiger Tätigkeit",
        "des revenus d'une activité indépendante",
        "دخل من عمل حر",
        "serbest meslekten gelir",
        "të ardhura nga veprimtaria e pavarur",
    ), attach6=(
        "the 'Anlage zum Einkommen aus selbständiger Tätigkeit'",
        "die 'Anlage zum Einkommen aus selbständiger Tätigkeit'",
        "l'« Anlage zum Einkommen aus selbständiger Tätigkeit »",
        "ملحق الدخل من العمل الحر",
        "'Anlage zum Einkommen aus selbständiger Tätigkeit' formunu",
        "'Anlage zum Einkommen aus selbständiger Tätigkeit'",
    )),
    W_FWD: _had((
        "income from a federal volunteer service or charitable/honorary work",
        "Einkommen aus Bundesfreiwilligendienst oder gemeinnütziger/ehrenamtlicher Tätigkeit",
        "des revenus d'un service volontaire fédéral ou d'une activité bénévole",
        "دخل من خدمة تطوعية اتحادية أو عمل خيري/تطوعي",
        "federal gönüllü hizmet veya hayır/gönüllü işten gelir",
        "të ardhura nga shërbimi vullnetar federal ose punë bamirëse/vullnetare",
    )),
    W_ALG2: _had((
        "Bürgergeld, social assistance or asylum-seeker benefits",
        "Bürgergeld, Sozialhilfe oder Leistungen für Asylbewerber",
        "le Bürgergeld, l'aide sociale ou des prestations pour demandeurs d'asile",
        "Bürgergeld أو مساعدة اجتماعية أو إعانات طالبي اللجوء",
        "Bürgergeld, sosyal yardım veya sığınmacı yardımları",
        "Bürgergeld, ndihmë sociale ose përfitime për azilkërkues",
    ), attach6=("the decision letter (Bescheid)", "den Bescheid",
                "la notification (Bescheid)", "خطاب القرار (Bescheid)",
                "karar yazısını (Bescheid)", "vendimin (Bescheid)")),
    W_ALG1: _had((
        "unemployment benefit (Arbeitslosengeld)",
        "Arbeitslosengeld",
        "des allocations chômage (Arbeitslosengeld)",
        "إعانة بطالة (Arbeitslosengeld)",
        "işsizlik ödeneği (Arbeitslosengeld)",
        "pagesë papunësie (Arbeitslosengeld)",
    ), attach6=("the decision letter (Bescheid)", "den Bescheid",
                "la notification (Bescheid)", "خطاب القرار (Bescheid)",
                "karar yazısını (Bescheid)", "vendimin (Bescheid)")),
    W_KRANKENGELD: _had((
        "sickness, injury or transitional benefit",
        "Krankengeld, Verletztengeld oder Übergangsgeld",
        "des indemnités de maladie, d'accident ou de transition",
        "بدل مرض أو إصابة أو انتقال",
        "hastalık, kaza veya geçiş ödeneği",
        "pagesë sëmundjeje, lëndimi ose kalimtare",
    )),
    W_RENTE: _had((
        "a pension or orphan's pension",
        "Rente oder Halbwaisenrente",
        "une pension ou une pension d'orphelin",
        "معاش تقاعدي أو معاش يتيم",
        "emekli maaşı veya yetim aylığı",
        "pension ose pension jetimi",
    )),
    W_BAFOEG: _had((
        "BAföG, a scholarship or vocational training assistance",
        "BAföG, Stipendium oder Berufsausbildungsbeihilfe",
        "le BAföG, une bourse ou une aide à la formation professionnelle",
        "BAföG أو منحة أو مساعدة تدريب مهني",
        "BAföG, burs veya mesleki eğitim yardımı",
        "BAföG, bursë ose ndihmë për formim profesional",
    )),
    W_STAATL: _had((
        "other state benefits",
        "sonstige staatliche Leistungen",
        "d'autres prestations de l'État",
        "إعانات حكومية أخرى",
        "diğer devlet yardımları",
        "përfitime të tjera shtetërore",
    )),
    W_UNTERHALT: _had((
        "maintenance payments (Unterhalt)",
        "Unterhalt",
        "une pension alimentaire (Unterhalt)",
        "نفقة (Unterhalt)",
        "nafaka (Unterhalt)",
        "ushqim (Unterhalt)",
    ), attach6=(
        "proof of the maintenance received (bank statements)",
        "Nachweis über erhaltene Unterhaltszahlungen (Kontoauszüge)",
        "une preuve de la pension reçue (relevés bancaires)",
        "إثبات النفقة المستلمة (كشوف حساب)",
        "alınan nafakanın kanıtı (hesap dökümleri)",
        "dëshmi të ushqimit të marrë (nxjerrje llogarie)",
    )),
    W_UH_VORSCHUSS: _had((
        "an advance maintenance payment (Unterhaltsvorschuss)",
        "Unterhaltsvorschuss",
        "une avance sur pension alimentaire (Unterhaltsvorschuss)",
        "سلفة نفقة (Unterhaltsvorschuss)",
        "nafaka avansı (Unterhaltsvorschuss)",
        "paradhënie ushqimi (Unterhaltsvorschuss)",
    ), attach6=(
        "the approval notice for the advance maintenance",
        "den Bewilligungsbescheid über Unterhaltsvorschuss",
        "la notification d'octroi de l'avance",
        "خطاب الموافقة على سلفة النفقة",
        "nafaka avansı onay yazısını",
        "vendimin e miratimit për paradhënien",
    )),
    W_KEIN_UH: _Q((
        "Did your child receive NO maintenance and no advance maintenance at all?",
        "Hat Ihr Kind gar keinen Unterhalt und keinen Unterhaltsvorschuss erhalten?",
        "Votre enfant n'a-t-il reçu AUCUNE pension ni avance sur pension alimentaire ?",
        "هل لم يتلقَّ طفلك أي نفقة ولا سلفة نفقة على الإطلاق؟",
        "Çocuğunuz hiç nafaka ve nafaka avansı almadı mı?",
        "A nuk mori fëmija juaj fare ushqim dhe asnjë paradhënie ushqimi?",
    ), helps=(
        "If you live apart from the other biological parent, also fill in the 'Anlage zu Unterhalt und Unterhaltsvorschuss'.",
        "Wenn Sie vom anderen leiblichen Elternteil getrennt leben, füllen Sie auch die 'Anlage zu Unterhalt und Unterhaltsvorschuss' aus.",
        "Si vous vivez séparé de l'autre parent biologique, remplissez aussi l'« Anlage zu Unterhalt und Unterhaltsvorschuss ».",
        "إذا كنت تعيش منفصلاً عن الوالد البيولوجي الآخر، املأ أيضًا ملحق النفقة.",
        "Diğer biyolojik ebeveynden ayrı yaşıyorsanız 'Anlage zu Unterhalt und Unterhaltsvorschuss' formunu da doldurun.",
        "Nëse jetoni ndarë nga prindi tjetër biologjik, plotësoni edhe 'Anlage zu Unterhalt und Unterhaltsvorschuss'.",
    )),
    W_SONST_EK: _had((
        "other income (e.g. interest, tax refunds, severance pay, tips)",
        "sonstige Einnahmen (z. B. Zinsen, Steuerrückerstattungen, Abfindungen, Trinkgelder)",
        "d'autres revenus (par ex. intérêts, remboursements d'impôt, indemnités, pourboires)",
        "إيرادات أخرى (مثل فوائد، استرداد ضرائب، تعويضات، إكراميات)",
        "diğer gelirler (örn. faiz, vergi iadesi, kıdem tazminatı, bahşiş)",
        "të ardhura të tjera (p.sh. interesa, rimbursime tatimi, kompensime, bakshishe)",
    )),

    # ── Section 4 — expenses ────────────────────────────────────────────
    W_FK_OEFFIS: _expense((
        "public transport tickets to work",
        "Fahrkarten für öffentliche Verkehrsmittel zur Arbeit",
        "des titres de transport public pour aller au travail",
        "تذاكر مواصلات عامة للعمل",
        "işe gidiş için toplu taşıma biletleri",
        "bileta transporti publik për në punë",
    )),
    W_FK_KM: _Q((
        "If your child drove a car to work, what is the one-way distance in km? Write - if not applicable.",
        "Wenn Ihr Kind mit dem Auto zur Arbeit fuhr: einfache Wegstrecke in km? Schreiben Sie -, wenn nicht zutreffend.",
        "Si votre enfant allait au travail en voiture : distance aller simple en km ? Écrivez - sinon.",
        "إذا ذهب طفلك إلى العمل بالسيارة: المسافة باتجاه واحد بالكيلومتر؟ اكتب - إذا لم ينطبق.",
        "Çocuğunuz işe arabayla gittiyse: tek yön mesafe km olarak? Uygun değilse - yazın.",
        "Nëse fëmija juaj shkonte në punë me makinë: distanca një drejtim në km? Shkruani - nëse jo.",
    ), ex="15"),
    W_FK_TAGE: _Q((
        "How many days per week did your child travel to work?",
        "An wie vielen Tagen pro Woche fuhr Ihr Kind zur Arbeit?",
        "Combien de jours par semaine votre enfant se rendait-il au travail ?",
        "كم يومًا في الأسبوع ذهب طفلك إلى العمل؟",
        "Çocuğunuz haftada kaç gün işe gitti?",
        "Sa ditë në javë udhëtonte fëmija juaj për në punë?",
    ), ex="5"),
    W_DOPP_HH: _expense((
        "a second household (doppelte Haushaltsführung)",
        "doppelte Haushaltsführung",
        "une double résidence (doppelte Haushaltsführung)",
        "إدارة منزلين (doppelte Haushaltsführung)",
        "çifte ev geçimi (doppelte Haushaltsführung)",
        "mbajtje të dyfishtë shtëpie (doppelte Haushaltsführung)",
    )),
    W_VERPFLEG: _expense((
        "extra meal costs (Verpflegungsmehraufwendungen)",
        "Verpflegungsmehraufwendungen",
        "des frais de repas supplémentaires",
        "نفقات إعاشة إضافية",
        "ek yemek masrafları",
        "shpenzime shtesë ushqimi",
    )),
    W_SONST_WK: _expense((
        "other work-related costs (e.g. a union fee)",
        "sonstige Werbungskosten (z. B. Gewerkschaftsbeitrag)",
        "d'autres frais professionnels (par ex. cotisation syndicale)",
        "نفقات مهنية أخرى (مثل اشتراك نقابي)",
        "diğer iş giderleri (örn. sendika aidatı)",
        "shpenzime të tjera pune (p.sh. tarifë sindikate)",
    )),
    W_KFZ_HAFTPFL: _expense((
        "car liability insurance (without comprehensive cover)",
        "Kfz-Haftpflichtversicherung (ohne Voll-/Teilkasko)",
        "une assurance responsabilité civile auto (sans tous risques)",
        "تأمين مسؤولية السيارة (بدون تأمين شامل)",
        "araç zorunlu sigortası (kasko hariç)",
        "sigurim përgjegjësie të makinës (pa kasko)",
    )),
    W_ALTERSVORS: _expense((
        "private pension contributions (e.g. Riester)",
        "Altersvorsorgebeiträge (z. B. Riester-Rente)",
        "des cotisations de retraite privée (par ex. Riester)",
        "اشتراكات تقاعد خاص (مثل Riester)",
        "özel emeklilik katkıları (örn. Riester)",
        "kontribute private pensioni (p.sh. Riester)",
    )),
    W_SONST_VERS: _expense((
        "health/care insurance, or pension contributions if not compulsorily insured",
        "Kranken-/Pflegeversicherung oder Altersvorsorge, wenn nicht gesetzlich pflichtversichert",
        "une assurance maladie/dépendance, ou des cotisations retraite si non affilié obligatoire",
        "تأمين صحي/رعاية أو تقاعد إذا لم يكن مؤمَّنًا إجباريًا",
        "sağlık/bakım sigortası veya zorunlu sigortalı değilse emeklilik",
        "sigurim shëndetësor/kujdesi ose pensioni nëse jo i siguruar me ligj",
    )),
    W_UH_ZAHLUNG: _expense((
        "maintenance the child PAID to someone",
        "vom Kind gezahlte Unterhaltszahlungen",
        "une pension alimentaire que l'enfant a VERSÉE",
        "نفقة دفعها الطفل لشخص ما",
        "çocuğun BİRİNE ÖDEDİĞİ nafaka",
        "ushqim që fëmija i PAGUAJTI dikujt",
    ), attach6=(
        "the maintenance order and bank statements",
        "Unterhaltstitel und Kontoauszüge",
        "le titre alimentaire et les relevés bancaires",
        "سند النفقة وكشوف الحساب",
        "nafaka belgesi ve hesap dökümleri",
        "titullin e ushqimit dhe nxjerrjet e llogarisë",
    )),

    # ── Signature ────────────────────────────────────────────────────────
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
    ), ex="13.06.2026", fmt="date"),
}


def _register_kizank_verified_questions() -> None:
    """Merge KiZ Anlage Kind verified questions into VERIFIED_BY_FIELD_ID.
    Runs once at module import (lazily via form_templates._all_templates())."""
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    VERIFIED_BY_FIELD_ID.update(_QUESTIONS)


_register_kizank_verified_questions()
