"""
Verified field map for the Kinderzuschlag "Anlage Antragsteller(in) und
Partner(in)" (KiZ 1-AnA).

Sixth Level 1 verified template — the adult income/expense + housing-cost
declaration that completes the Kinderzuschlag journey (KiZ 1 main + Anlage
Kind + this). XFA-styled → fill_strategy="fitz_acroform".

Source PDF
----------
templates_source/incoming/kiz1_anlage_antragsteller.pdf
(official: arbeitsagentur.de/datei/kiz1-ana_ba034980.pdf, Stand 02/2024)

Fingerprint
-----------
Required (all): the form-unique footer "kiz 1-ana" + "anlage antragsteller".
The footer appears ONLY on this form (the KiZ1 main has "kiz 1 - seite", the
KiZ Anlage Kind has "kiz 1-ank") — verified against all PDFs in
templates_source/incoming/.

Partner gating
--------------
Most of the form is applicant/partner (-A / -P) pairs. A synthetic logical
question L_HAS_PARTNER ("Do you have a partner in your household?") gates every
-P field, so a single parent never sees the partner columns. L_HAS_PARTNER has
no PDF widget — it is a pure flow-control question; the fill engine simply
ignores it (every real -A/-P box it gates is a normal widget). Housing sub-
items are gated on the rent/own choice; the holiday/car detail texts on their
parent answer.

Every shown field has a verified question in en/de/fr/ar/tr/sq.
weak_questions=0 and ai_calls_made=0 invariants must hold.
"""
from __future__ import annotations

from app.services.form_templates import RadioGroup, VerifiedTemplate

_P1 = "topmostSubform[0].Page1[0]"
_P2 = "topmostSubform[0].Page2[0]"
_P3 = "topmostSubform[0].Page3[0]"

# ── Header ────────────────────────────────────────────────────────────────────
W_NAME_KGB   = _P1 + ".Kopfzeile[0].Name_Vorname_KGB[0]"
W_KG_NR      = _P1 + ".Kopfzeile[0].KG-Nr[0]"
W_ANTRAGSDAT = _P1 + ".Kopfzeile[0].Antragsdatum[0]"

# ── Frage 1 — circumstances (A/P) ─────────────────────────────────────────────
_F1 = _P1 + ".Frage-1[0]"
W_AUSB_A    = _F1 + ".Ausbildung-Antragsteller[0]"
W_AUSB_P    = _F1 + ".Ausbildung-Partner[0]"
W_STAT_A    = _F1 + ".stationäre-Unterbring-Antragsteller[0]"
W_STAT_P    = _F1 + ".stationäre-Unterbring-Partner[0]"
W_FOREIGN_A = _F1 + ".öffentl-Dienst-Antragsteller[0]"   # name misleading: foreign benefit
W_FOREIGN_P = _F1 + ".öffentl-Dienst-Partner[0]"

# ── Frage 2 — housing ─────────────────────────────────────────────────────────
_F2 = _P1 + ".Frage-2[0]"
W_MIETE        = _F2 + ".Miete[0]"
W_MIETVERTRAG  = _F2 + ".Mietvertrag[0]"
W_KONTOAUSZUG  = _F2 + ".Kontoauszug[0]"
W_HEIZ_MIETE   = _F2 + ".Heizkosten-Miete[0]"
W_BETRIEBSK    = _F2 + ".Betriebskosten[0]"
W_WG_MIETE     = _F2 + ".Wohngeldbescheid-Miete[0]"
W_MIETZUSCHUSS = _F2 + ".#area[3].Mietzuschuss[0]"
W_EIGENHEIM    = _F2 + ".Eigenheim[0]"
W_SCHULDZINSEN = _F2 + ".Schuldzinsen[0]"
W_GRUNDSTEUER  = _F2 + ".Grundsteuer[0]"
W_HEIZ_EIGEN   = _F2 + ".Heizkosten-Eigenheim[0]"
W_NEBENKOSTEN  = _F2 + ".Nebenkosten[0]"
W_WG_EIGEN     = _F2 + ".Wohngeldbescheid-Eigenheim[0]"
W_EINZUGSDATUM = _F2 + ".#area[4].Einzugsdatum[0]"
W_WW_ZENTRAL   = _F2 + ".WW-Erzeugung[0].zentral[0]"
W_WW_DEZENTRAL = _F2 + ".WW-Erzeugung[0].dezentral[0]"

# ── Frage 3 — Vermögen (ja/nein) ──────────────────────────────────────────────
W_VERMOEGEN_JA   = _P2 + ".Frage-3[0].Vermögen-ja[0]"
W_VERMOEGEN_NEIN = _P2 + ".Frage-3[0].Vermögen-nein[0]"

# ── Frage 4 — Mehrbedarf ──────────────────────────────────────────────────────
W_MEHRBEDARF = _P2 + ".Frage-4[0].Mehrbedarf-ja[0]"
W_ENTBINDUNG = _P2 + ".Frage-4[0].Entbindungstermin[0]"

# ── Frage 5 — income (A/P pairs) ──────────────────────────────────────────────
_F5 = _P2 + ".Frage-5[0]"
W_LOHN_A = _F5 + ".Zeile-Lohn[0].Lohn-A[0]"
W_LOHN_P = _F5 + ".Zeile-Lohn[0].Lohn-P[0]"
W_VERDIENST_A = _F5 + ".Zeile-Lohn[0].Verdienstbesch-A[0]"
W_VERDIENST_P = _F5 + ".Zeile-Lohn[0].Verdienstbesch-P[0]"
_SELB = _F5 + ".Zeile-Einkommen-Selbständ[0]"
W_SELBST_A = _SELB + ".KiZ5a-A[0]"
W_SELBST_P = _SELB + ".KiZ5a-P[0]"
W_SELBST_NACHW_A = _SELB + ".selbst-a-Nachw-A[0]"
W_SELBST_NACHW_P = _SELB + ".selbst-a-Nachw-P[0]"
W_FWD_A = _F5 + ".Zeile-FWD[0].FWD-Nachw-A[0]"
W_FWD_P = _F5 + ".Zeile-FWD[0].FWD-Nachw-P[0]"
_EK = _F5 + ".Zeile-and-EK[0]"
W_ALG1_A = _EK + ".Alg-1-A[0]"
W_ALG1_P = _EK + ".Alg-1-P[0]"
W_ALG2_A = _EK + ".Alg-2-A[0]"
W_ALG2_P = _EK + ".Alg-2-P[0]"
W_KRANK_A = _EK + ".Krankengeld-A[0]"
W_KRANK_P = _EK + ".Krankengeld-P[0]"
W_RENTE_A = _EK + ".Rente-A[0]"
W_RENTE_P = _EK + ".Rente-P[0]"
W_ELTERN_A = _EK + ".Elterngeld-Antragst[0]"
W_ELTERN_P = _EK + ".Elterngeld-Partner[0]"
W_BAFOEG_A = _EK + ".Bafög-A[0]"
W_BAFOEG_P = _EK + ".Bafög-P[0]"
W_STAATL_A = _EK + ".Leist-staatl-A[0]"
W_STAATL_P = _EK + ".Leist-staatl-P[0]"
W_UH_A = _F5 + ".Zeile-Unterhalt[0].UH-A[0]"
W_UH_P = _F5 + ".Zeile-Unterhalt[0].UH-P[0]"
W_MIETEINN_A = _F5 + ".Zeile-Mieteinnahmen[0].Mieteinnahmen-A[0]"
W_MIETEINN_P = _F5 + ".Zeile-Mieteinnahmen[0].Mieteinnahmen-P[0]"
W_SONST_EK_A = _F5 + ".Zeile-sonst-Einnahmen[0].sonst-Einn-A[0]"
W_SONST_EK_P = _F5 + ".Zeile-sonst-Einnahmen[0].sonst-Einn-P[0]"

# ── Frage 6 — expenses (A/P pairs) ────────────────────────────────────────────
_F6 = _P3 + ".Frage-6[0]"
_WK = _F6 + ".Zeile-Werbungskosten[0]"
W_FK_OEFFIS_A = _WK + ".#area[4].FK-Öffis-A[0]"
W_FK_OEFFIS_P = _WK + ".#area[4].FK-Öffis-P[0]"
W_FK_KM_A = _WK + ".#area[5].FK-KfZ-km-A[0]"
W_FK_KM_P = _WK + ".#area[5].FK-KfZ-km-P[0]"
W_FK_TAGE_A = _WK + ".#area[6].FK-Tage-A[0]"
W_FK_TAGE_P = _WK + ".#area[6].FK-Tage-P[0]"
W_DOPP_HH_A = _WK + ".#area[7].doppelte-HH-A[0]"
W_DOPP_HH_P = _WK + ".#area[7].doppelte-HH-P[0]"
W_VERPFLEG_A = _WK + ".#area[8].Verpfleg-A[0]"
W_VERPFLEG_P = _WK + ".#area[8].Verpfleg-P[0]"
W_SONST_WK_A = _WK + ".#area[9].sonst-WK-A[0]"
W_SONST_WK_P = _WK + ".#area[9].sonst-WK-P[0]"
_VERS = _F6 + ".Zeile-Versicherungen[0]"
W_KFZ_A = _VERS + ".Kfz-Versich-A[0]"
W_KFZ_P = _VERS + ".Kfz-Versich-P[0]"
W_RIESTER_A = _VERS + ".Riester-A[0]"
W_RIESTER_P = _VERS + ".Riester-P[0]"
W_SONST_VERS_A = _VERS + ".sonst-Versich-A[0]"
W_SONST_VERS_P = _VERS + ".sonst-Versich-P[0]"
W_UHZAHL_A = _F6 + ".Zeile-Unterhaltszahlungen[0].Unterhaltszahl-A[0]"
W_UHZAHL_P = _F6 + ".Zeile-Unterhaltszahlungen[0].Unterhaltszahl-P[0]"
W_BETR_A = _F6 + ".Zeile-Kinderbetr-kosten[0].Betr-kosten-A[0]"
W_BETR_P = _F6 + ".Zeile-Kinderbetr-kosten[0].Betr-kosten-P[0]"

# ── Signature ─────────────────────────────────────────────────────────────────
W_DATUM = _P3 + ".Erklärung[0].Unterschriftenzeile[0].Datum\\.Antrag\\.0[0]"

# ── Logical IDs ───────────────────────────────────────────────────────────────
L_HAS_PARTNER = "kizana_has_partner"     # synthetic gate, no widget
L_VERMOEGEN   = "kizana_vermoegen"       # ja/nein over 2 widgets
L_WARMWASSER  = "kizana_warmwasser"      # zentral/dezentral over 2 widgets

_WW_OPTIONS = ["zentral", "dezentral"]


# ── Conditions ────────────────────────────────────────────────────────────────
def _yes(field_key: str) -> dict:
    return {"type": "field_equals", "field_key": field_key, "value": "yes"}


def _not_skip(field_key: str) -> dict:
    return {"type": "field_not_equals", "field_key": field_key, "value": "-"}


_C_PARTNER = _yes(L_HAS_PARTNER)
_C_MIETE = _yes(W_MIETE)
_C_EIGEN = _yes(W_EIGENHEIM)
_C_MEHRBEDARF = _yes(W_MEHRBEDARF)


# ── Income / expense pair tables ──────────────────────────────────────────────
# (base_id, a_widget, p_widget, noun6, attach6 | None)
_INCOME = [
    ("lohn", W_LOHN_A, W_LOHN_P, (
        "wages or salary (incl. training pay)",
        "Arbeitslohn oder Gehalt (auch Ausbildungsvergütung)",
        "un salaire (y compris rémunération d'apprentissage)",
        "أجرًا أو راتبًا (بما في ذلك أجر التدريب)",
        "ücret veya maaş (eğitim ücreti dahil)",
        "rrogë ose pagë (përfshirë pagesën e formimit)",
    ), (
        "payslips (also for a mini/side job)",
        "Lohn-/Gehaltsabrechnungen (auch für Mini-/Nebenjob)",
        "des fiches de paie (aussi pour un mini-job)",
        "كشوف الرواتب (وأيضًا لوظيفة صغيرة)",
        "maaş bordroları (mini iş için de)",
        "fletëpagesat (edhe për një mini-punë)",
    )),
    ("selbst", W_SELBST_A, W_SELBST_P, (
        "income from self-employment",
        "Einkommen aus selbständiger Arbeit",
        "des revenus d'une activité indépendante",
        "دخلًا من عمل حر",
        "serbest meslekten gelir",
        "të ardhura nga veprimtaria e pavarur",
    ), (
        "the 'Anlage zum Einkommen aus selbständiger Tätigkeit'",
        "die 'Anlage zum Einkommen aus selbständiger Tätigkeit'",
        "l'« Anlage zum Einkommen aus selbständiger Tätigkeit »",
        "ملحق الدخل من العمل الحر",
        "'Anlage zum Einkommen aus selbständiger Tätigkeit' formunu",
        "'Anlage zum Einkommen aus selbständiger Tätigkeit'",
    )),
    ("fwd", W_FWD_A, W_FWD_P, (
        "income from a federal volunteer service or charitable/honorary work",
        "Einkommen aus Bundesfreiwilligendienst oder gemeinnütziger/ehrenamtlicher Tätigkeit",
        "des revenus d'un service volontaire fédéral ou d'une activité bénévole",
        "دخلًا من خدمة تطوعية اتحادية أو عمل خيري/تطوعي",
        "federal gönüllü hizmet veya hayır/gönüllü işten gelir",
        "të ardhura nga shërbimi vullnetar federal ose punë bamirëse",
    ), None),
    ("alg1", W_ALG1_A, W_ALG1_P, (
        "unemployment benefit (Arbeitslosengeld)",
        "Arbeitslosengeld",
        "des allocations chômage (Arbeitslosengeld)",
        "إعانة بطالة (Arbeitslosengeld)",
        "işsizlik ödeneği (Arbeitslosengeld)",
        "pagesë papunësie (Arbeitslosengeld)",
    ), None),
    ("alg2", W_ALG2_A, W_ALG2_P, (
        "Bürgergeld, social assistance or asylum-seeker benefits",
        "Bürgergeld, Sozialhilfe oder Leistungen für Asylbewerber",
        "le Bürgergeld, l'aide sociale ou des prestations pour demandeurs d'asile",
        "Bürgergeld أو مساعدة اجتماعية أو إعانات طالبي اللجوء",
        "Bürgergeld, sosyal yardım veya sığınmacı yardımları",
        "Bürgergeld, ndihmë sociale ose përfitime për azilkërkues",
    ), None),
    ("krank", W_KRANK_A, W_KRANK_P, (
        "sickness, injury or transitional benefit",
        "Krankengeld, Verletztengeld oder Übergangsgeld",
        "des indemnités de maladie, d'accident ou de transition",
        "بدل مرض أو إصابة أو انتقال",
        "hastalık, kaza veya geçiş ödeneği",
        "pagesë sëmundjeje, lëndimi ose kalimtare",
    ), None),
    ("rente", W_RENTE_A, W_RENTE_P, (
        "a pension or orphan's pension",
        "Rente oder Halbwaisenrente",
        "une pension ou une pension d'orphelin",
        "معاشًا تقاعديًا أو معاش يتيم",
        "emekli maaşı veya yetim aylığı",
        "pension ose pension jetimi",
    ), None),
    ("eltern", W_ELTERN_A, W_ELTERN_P, (
        "parental allowance (Elterngeld)",
        "Elterngeld",
        "une allocation parentale (Elterngeld)",
        "علاوة الوالدين (Elterngeld)",
        "ebeveyn ödeneği (Elterngeld)",
        "pagesë prindërore (Elterngeld)",
    ), None),
    ("bafoeg", W_BAFOEG_A, W_BAFOEG_P, (
        "BAföG, a scholarship or training assistance",
        "BAföG, Stipendium oder Berufsausbildungsbeihilfe",
        "le BAföG, une bourse ou une aide à la formation",
        "BAföG أو منحة أو مساعدة تدريب مهني",
        "BAföG, burs veya mesleki eğitim yardımı",
        "BAföG, bursë ose ndihmë për formim profesional",
    ), None),
    ("staatl", W_STAATL_A, W_STAATL_P, (
        "other state benefits",
        "sonstige staatliche Leistungen",
        "d'autres prestations de l'État",
        "إعانات حكومية أخرى",
        "diğer devlet yardımları",
        "përfitime të tjera shtetërore",
    ), None),
    ("unterhalt", W_UH_A, W_UH_P, (
        "maintenance for yourself (not the maintenance for your children)",
        "Unterhalt für sich selbst (nicht den Unterhalt für Ihre Kinder)",
        "une pension alimentaire pour vous-même (pas celle pour vos enfants)",
        "نفقة لك أنت (وليست نفقة أطفالك)",
        "kendiniz için nafaka (çocuklarınız için olan değil)",
        "ushqim për veten (jo ushqimin për fëmijët tuaj)",
    ), None),
    ("mieteinn", W_MIETEINN_A, W_MIETEINN_P, (
        "income from renting or leasing out property",
        "Einnahmen aus Vermietung oder Verpachtung",
        "des revenus de location ou de bail",
        "دخلًا من تأجير عقار",
        "kira veya kiralama geliri",
        "të ardhura nga qiradhënia",
    ), None),
    ("sonst", W_SONST_EK_A, W_SONST_EK_P, (
        "other income (e.g. interest, tax refunds, severance pay, tips)",
        "sonstige Einnahmen (z. B. Zinsen, Steuerrückerstattungen, Abfindungen, Trinkgelder)",
        "d'autres revenus (par ex. intérêts, remboursements d'impôt, indemnités, pourboires)",
        "إيرادات أخرى (مثل فوائد، استرداد ضرائب، تعويضات، إكراميات)",
        "diğer gelirler (örn. faiz, vergi iadesi, kıdem tazminatı, bahşiş)",
        "të ardhura të tjera (p.sh. interesa, rimbursime, kompensime, bakshishe)",
    ), None),
]

_EXPENSE = [
    ("dopp_hh", W_DOPP_HH_A, W_DOPP_HH_P, (
        "a second household (doppelte Haushaltsführung)",
        "doppelte Haushaltsführung",
        "une double résidence (doppelte Haushaltsführung)",
        "إدارة منزلين (doppelte Haushaltsführung)",
        "çifte ev geçimi (doppelte Haushaltsführung)",
        "mbajtje të dyfishtë shtëpie (doppelte Haushaltsführung)",
    ), None),
    ("verpfleg", W_VERPFLEG_A, W_VERPFLEG_P, (
        "extra meal costs (Verpflegungsmehraufwendungen)",
        "Verpflegungsmehraufwendungen",
        "des frais de repas supplémentaires",
        "نفقات إعاشة إضافية",
        "ek yemek masrafları",
        "shpenzime shtesë ushqimi",
    ), None),
    ("sonst_wk", W_SONST_WK_A, W_SONST_WK_P, (
        "other work-related costs (e.g. a union fee)",
        "sonstige Werbungskosten (z. B. Gewerkschaftsbeitrag)",
        "d'autres frais professionnels (par ex. cotisation syndicale)",
        "نفقات مهنية أخرى (مثل اشتراك نقابي)",
        "diğer iş giderleri (örn. sendika aidatı)",
        "shpenzime të tjera pune (p.sh. tarifë sindikate)",
    ), None),
    ("kfz", W_KFZ_A, W_KFZ_P, (
        "car liability insurance (without comprehensive cover)",
        "Kfz-Haftpflichtversicherung (ohne Voll-/Teilkasko)",
        "une assurance responsabilité civile auto (sans tous risques)",
        "تأمين مسؤولية السيارة (بدون تأمين شامل)",
        "araç zorunlu sigortası (kasko hariç)",
        "sigurim përgjegjësie të makinës (pa kasko)",
    ), None),
    ("riester", W_RIESTER_A, W_RIESTER_P, (
        "private pension contributions (e.g. Riester)",
        "Altersvorsorgebeiträge (z. B. Riester-Rente)",
        "des cotisations de retraite privée (par ex. Riester)",
        "اشتراكات تقاعد خاص (مثل Riester)",
        "özel emeklilik katkıları (örn. Riester)",
        "kontribute private pensioni (p.sh. Riester)",
    ), None),
    ("sonst_vers", W_SONST_VERS_A, W_SONST_VERS_P, (
        "health/care insurance, or pension if not compulsorily insured",
        "Kranken-/Pflegeversicherung oder Altersvorsorge, wenn nicht gesetzlich pflichtversichert",
        "une assurance maladie/dépendance, ou retraite si non affilié obligatoire",
        "تأمينًا صحيًا/رعاية أو تقاعدًا إذا لم يكن مؤمَّنًا إجباريًا",
        "sağlık/bakım sigortası veya zorunlu sigortalı değilse emeklilik",
        "sigurim shëndetësor/kujdesi ose pension nëse jo i siguruar me ligj",
    ), None),
    ("uhzahl", W_UHZAHL_A, W_UHZAHL_P, (
        "maintenance that was PAID to someone",
        "gezahlte Unterhaltszahlungen",
        "une pension alimentaire VERSÉE",
        "نفقة دُفعت لشخص ما",
        "BİRİNE ÖDENEN nafaka",
        "ushqim që u PAGUA dikujt",
    ), (
        "the maintenance order and bank statements",
        "Unterhaltstitel und Kontoauszüge",
        "le titre alimentaire et les relevés bancaires",
        "سند النفقة وكشوف الحساب",
        "nafaka belgesi ve hesap dökümleri",
        "titullin e ushqimit dhe nxjerrjet e llogarisë",
    )),
    ("betr", W_BETR_A, W_BETR_P, (
        "childcare costs (e.g. Kita, daycare)",
        "Kinderbetreuungskosten (z. B. Kita, Tagespflege)",
        "des frais de garde d'enfants (par ex. crèche)",
        "تكاليف رعاية الأطفال (مثل حضانة)",
        "çocuk bakım masrafları (örn. kreş)",
        "shpenzime për kujdesin e fëmijëve (p.sh. çerdhe)",
    ), (
        "the contract or fee notice",
        "Vertrag oder Gebührenbescheid",
        "le contrat ou l'avis de frais",
        "العقد أو إشعار الرسوم",
        "sözleşme veya ücret bildirimi",
        "kontratën ose njoftimin e tarifës",
    )),
]


class Kiz1AnlageAntragstellerTemplate(VerifiedTemplate):
    template_id   = "kiz1_anlage_antragsteller_v1"
    name          = "Familienkasse — Anlage Antragsteller(in)/Partner(in) zum Kinderzuschlag (KiZ 1-AnA)"
    fill_strategy = "fitz_acroform"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        return "kiz 1-ana" in lo and "anlage antragsteller" in lo

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

        fields = [
            # ── Header ───────────────────────────────────────────────────
            auto(W_NAME_KGB, "Name, Vorname der kindergeldbeziehenden Person",
                 "text", 1, src_text="Familienname und Vorname der kindergeldbeziehenden Person"),
            auto(W_KG_NR, "Kindergeld-Nummer", "text", 1, src_text="Kindergeld-Nr."),
            auto(W_ANTRAGSDAT, "Datum des Kinderzuschlagsantrags", "text", 1,
                 src_text="zum Antrag auf Kinderzuschlag vom"),

            # ── Partner gate ─────────────────────────────────────────────
            auto(L_HAS_PARTNER, "Partner im Haushalt", "checkbox", 1,
                 src_text="Mein(e) Partner(in)"),

            # ── Frage 1 — circumstances ──────────────────────────────────
            auto(W_AUSB_A, "Ich: in Schul-/Berufsausbildung oder Studium",
                 "checkbox", 1, src_text="befinde mich derzeit in einer Schul- oder Berufsausbildung"),
            auto(W_AUSB_P, "Partner(in): in Schul-/Berufsausbildung oder Studium",
                 "checkbox", 1, condition=_C_PARTNER),
            auto(W_STAT_A, "Ich: in stationärer Einrichtung", "checkbox", 1,
                 src_text="befinde mich derzeit in einer stationären Einrichtung"),
            auto(W_STAT_P, "Partner(in): in stationärer Einrichtung", "checkbox", 1,
                 condition=_C_PARTNER),
            auto(W_FOREIGN_A,
                 "Ich: Geldleistung für Kind(er) aus dem Ausland (statt Kindergeld)",
                 "checkbox", 1,
                 src_text="erhalte für mein(e) Kind(er) anstatt Kindergeld eine Geldleistung von einer Stelle außerhalb von Deutschland"),
            auto(W_FOREIGN_P,
                 "Partner(in): Geldleistung für Kind(er) aus dem Ausland (statt Kindergeld)",
                 "checkbox", 1, condition=_C_PARTNER),

            # ── Frage 2 — housing ────────────────────────────────────────
            auto(W_MIETE, "Wir wohnen zur Miete", "checkbox", 1,
                 src_text="zur Miete"),
            auto(W_MIETVERTRAG, "Mietvertrag / Mietbescheinigung wird beigefügt",
                 "checkbox", 1, condition=_C_MIETE),
            auto(W_KONTOAUSZUG,
                 "Kontoauszug wird beigefügt (Mietvertrag älter als ein Jahr)",
                 "checkbox", 1, condition=_C_MIETE),
            auto(W_HEIZ_MIETE, "Belege über Heizkosten werden beigefügt",
                 "checkbox", 1, condition=_C_MIETE),
            auto(W_BETRIEBSK, "Belege über Nebenkosten werden beigefügt",
                 "checkbox", 1, condition=_C_MIETE),
            auto(W_WG_MIETE, "Wohngeldbescheid wird beigefügt", "checkbox", 1,
                 condition=_C_MIETE),
            auto(W_MIETZUSCHUSS,
                 "Bescheid über kommunalen Mietzuschuss wird beigefügt",
                 "checkbox", 1, condition=_C_MIETE),
            auto(W_EIGENHEIM, "Wir wohnen im Eigenheim", "checkbox", 1,
                 src_text="in einem Eigenheim"),
            auto(W_SCHULDZINSEN, "Nachweis über Schuldzinsen wird beigefügt",
                 "checkbox", 1, condition=_C_EIGEN),
            auto(W_GRUNDSTEUER,
                 "Nachweis über Grundsteuer und Gebäudeversicherung wird beigefügt",
                 "checkbox", 1, condition=_C_EIGEN),
            auto(W_HEIZ_EIGEN, "Belege über Heizkosten werden beigefügt (Eigenheim)",
                 "checkbox", 1, condition=_C_EIGEN),
            auto(W_NEBENKOSTEN, "Belege über Nebenkosten werden beigefügt (Eigenheim)",
                 "checkbox", 1, condition=_C_EIGEN),
            auto(W_WG_EIGEN, "Wohngeldbescheid (Lastenzuschuss) wird beigefügt",
                 "checkbox", 1, condition=_C_EIGEN),
            auto(W_EINZUGSDATUM, "Einzugsdatum (falls in diesem/letztem Jahr eingezogen)",
                 "text", 1, src_text="Einzugsdatum"),
            auto(L_WARMWASSER, "Art der Warmwassererzeugung", "radio", 1,
                 opts=_WW_OPTIONS, src_text="Das Warmwasser wird wie folgt erzeugt"),

            # ── Frage 3 — Vermögen ───────────────────────────────────────
            auto(L_VERMOEGEN, "Erhebliches Vermögen", "radio", 2,
                 opts=["ja", "nein"],
                 src_text="erhebliches Vermögen"),

            # ── Frage 4 — Mehrbedarf ─────────────────────────────────────
            auto(W_MEHRBEDARF, "Mehrbedarf (z. B. Schwangerschaft, Behinderung)",
                 "checkbox", 2, src_text="einen oder mehrere Mehrbedarfe"),
            auto(W_ENTBINDUNG, "Voraussichtlicher Entbindungstermin", "text", 2,
                 src_text="voraussichtlicher Entbindungstermin", condition=_C_MEHRBEDARF),
        ]

        # ── Frage 5 — income pairs ───────────────────────────────────────
        for base, wa, wp, _noun, _att in _INCOME:
            fields.append(auto(wa, f"income_{base}_A", "checkbox", 2))
            fields.append(auto(wp, f"income_{base}_P", "checkbox", 2,
                               condition=_C_PARTNER))
        # secondary proof boxes (gated on the primary)
        fields.append(auto(W_VERDIENST_A,
                           "Verdienstbescheinigung des Arbeitgebers (statt Lohnabrechnung)",
                           "checkbox", 2, condition=_yes(W_LOHN_A)))
        fields.append(auto(W_VERDIENST_P,
                           "Verdienstbescheinigung des Arbeitgebers, Partner(in)",
                           "checkbox", 2,
                           condition={"type": "and", "conditions": [_C_PARTNER, _yes(W_LOHN_P)]}))
        fields.append(auto(W_SELBST_NACHW_A,
                           "Andere Nachweise zur selbständigen Tätigkeit (statt Anlage)",
                           "checkbox", 2, condition=_yes(W_SELBST_A)))
        fields.append(auto(W_SELBST_NACHW_P,
                           "Andere Nachweise zur selbständigen Tätigkeit, Partner(in)",
                           "checkbox", 2,
                           condition={"type": "and", "conditions": [_C_PARTNER, _yes(W_SELBST_P)]}))

        # ── Frage 6 — Fahrtkosten (special: öffis + km/days) ─────────────
        fields.append(auto(W_FK_OEFFIS_A, "fk_oeffis_A", "checkbox", 3))
        fields.append(auto(W_FK_OEFFIS_P, "fk_oeffis_P", "checkbox", 3,
                           condition=_C_PARTNER))
        fields.append(auto(W_FK_KM_A, "fk_km_A", "text", 3))
        fields.append(auto(W_FK_TAGE_A, "fk_tage_A", "text", 3,
                           condition=_not_skip(W_FK_KM_A)))
        fields.append(auto(W_FK_KM_P, "fk_km_P", "text", 3, condition=_C_PARTNER))
        fields.append(auto(W_FK_TAGE_P, "fk_tage_P", "text", 3,
                           condition={"type": "and", "conditions": [_C_PARTNER, _not_skip(W_FK_KM_P)]}))

        # ── Frage 6 — remaining expense pairs ────────────────────────────
        for base, wa, wp, _noun, _att in _EXPENSE:
            fields.append(auto(wa, f"expense_{base}_A", "checkbox", 3))
            fields.append(auto(wp, f"expense_{base}_P", "checkbox", 3,
                               condition=_C_PARTNER))

        # ── Signature ────────────────────────────────────────────────────
        fields.append(auto(W_DATUM, "Datum (Unterschrift)", "text", 3,
                           src_text="Datum / Unterschrift"))

        return fields

    def get_radio_groups(self) -> list[RadioGroup]:
        return [
            RadioGroup(
                field_id=L_VERMOEGEN,
                widget_names=[W_VERMOEGEN_JA, W_VERMOEGEN_NEIN],
                options=[("ja", W_VERMOEGEN_JA), ("nein", W_VERMOEGEN_NEIN)],
            ),
            RadioGroup(
                field_id=L_WARMWASSER,
                widget_names=[W_WW_ZENTRAL, W_WW_DEZENTRAL],
                options=[("zentral", W_WW_ZENTRAL), ("dezentral", W_WW_DEZENTRAL)],
            ),
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


# "you" vs "your partner" phrasings, per locale (lead 6-tuple per person).
_SUBJ = {
    "A": ("you", "Sie", "vous", "أنت", "siz", "ju"),
    "P": ("your partner", "Ihr(e) Partner(in)", "votre partenaire",
          "شريكك", "partneriniz", "partneri juaj"),
}


def _money_q(noun6, who, attach6, kind):
    """kind = 'income' | 'expense'. who = 'A' | 'P'."""
    s = _SUBJ[who]
    if kind == "income":
        qs = (
            f"In the last 6 months, did {s[0]} have {noun6[0]}?",
            f"Hatte {s[1] if who=='P' else 'ich'} in den letzten 6 Monaten {noun6[1]}? (Sie selbst)" if False else
            f"Hatten {s[1]} in den letzten 6 Monaten {noun6[1]}?",
            f"Au cours des 6 derniers mois, {s[2]} avez-vous eu {noun6[2]} ?" if who == "A"
            else f"Au cours des 6 derniers mois, {s[2]} a-t-il/elle eu {noun6[2]} ?",
            f"خلال الأشهر الستة الماضية، هل حصل {s[3]} على {noun6[3]}؟",
            f"Son 6 ayda {s[4]} {noun6[4]} oldu mu?",
            f"Në 6 muajt e fundit, a pati {s[5]} {noun6[5]}?",
        )
    else:
        qs = (
            f"In the last 6 months, did {s[0]} have expenses for {noun6[0]}?",
            f"Hatten {s[1]} in den letzten 6 Monaten Ausgaben für {noun6[1]}?",
            f"Au cours des 6 derniers mois, {s[2]} avez-vous eu des dépenses pour {noun6[2]} ?" if who == "A"
            else f"Au cours des 6 derniers mois, {s[2]} a-t-il/elle eu des dépenses pour {noun6[2]} ?",
            f"خلال الأشهر الستة الماضية، هل كان لدى {s[3]} نفقات على {noun6[3]}؟",
            f"Son 6 ayda {s[4]} {noun6[4]} için gideri oldu mu?",
            f"Në 6 muajt e fundit, a pati {s[5]} shpenzime për {noun6[5]}?",
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
        "What is the date of the Kinderzuschlag application this attachment belongs to?",
        "Vom welchem Datum ist der Kinderzuschlagsantrag, zu dem diese Anlage gehört?",
        "Quelle est la date de la demande de Kinderzuschlag à laquelle appartient cette annexe ?",
        "ما تاريخ طلب Kinderzuschlag الذي تتبع له هذه الملحقة؟",
        "Bu ekin ait olduğu Kinderzuschlag başvurusunun tarihi nedir?",
        "Cila është data e aplikimit për Kinderzuschlag të cilit i përket kjo shtojcë?",
    ), ex="13.06.2026", fmt="date"),

    # ── Partner gate ─────────────────────────────────────────────────────
    L_HAS_PARTNER: _Q((
        "Do you have a partner living in your household?",
        "Lebt ein(e) Partner(in) in Ihrem Haushalt?",
        "Avez-vous un(e) partenaire vivant dans votre foyer ?",
        "هل لديك شريك يعيش في منزلك؟",
        "Hanenizde yaşayan bir partneriniz var mı?",
        "A keni një partner që jeton në shtëpinë tuaj?",
    ), helps=(
        "If yes, we will also ask the questions about your partner. If no, you only answer for yourself.",
        "Falls ja, stellen wir auch die Fragen zu Ihrem/Ihrer Partner(in). Falls nein, antworten Sie nur für sich selbst.",
        "Si oui, nous poserons aussi les questions sur votre partenaire. Sinon, vous répondez seulement pour vous-même.",
        "إذا نعم، سنطرح أيضًا أسئلة عن شريكك. إذا لا، فأجب عن نفسك فقط.",
        "Evetse partnerinizle ilgili soruları da soracağız. Hayırsa yalnızca kendiniz için yanıtlarsınız.",
        "Nëse po, do të bëjmë edhe pyetjet për partnerin tuaj. Nëse jo, përgjigjeni vetëm për veten.",
    )),

    # ── Frage 1 ──────────────────────────────────────────────────────────
    W_AUSB_A: _Q((
        "Are you currently in school, vocational training or studying?",
        "Befinden Sie sich derzeit in einer Schul-/Berufsausbildung oder im Studium?",
        "Êtes-vous actuellement en formation scolaire, professionnelle ou en études ?",
        "هل أنت حاليًا في تعليم مدرسي/مهني أو دراسة جامعية؟",
        "Şu anda okul/meslek eğitiminde veya üniversitede misiniz?",
        "A jeni aktualisht në shkollë, formim profesional ose studime?",
    )),
    W_AUSB_P: _Q((
        "Is your partner currently in school, vocational training or studying?",
        "Befindet sich Ihr(e) Partner(in) derzeit in einer Schul-/Berufsausbildung oder im Studium?",
        "Votre partenaire est-il/elle actuellement en formation ou en études ?",
        "هل شريكك حاليًا في تعليم مدرسي/مهني أو دراسة؟",
        "Partneriniz şu anda okul/meslek eğitiminde veya üniversitede mi?",
        "A është partneri juaj aktualisht në shkollë, formim ose studime?",
    )),
    W_STAT_A: _Q((
        "Are you currently in a residential (inpatient) institution?",
        "Befinden Sie sich derzeit in einer stationären Einrichtung?",
        "Êtes-vous actuellement dans un établissement avec hébergement ?",
        "هل أنت حاليًا في مؤسسة إقامة داخلية؟",
        "Şu anda yatılı bir kurumda mısınız?",
        "A ndodheni aktualisht në një institucion me qëndrim?",
    )),
    W_STAT_P: _Q((
        "Is your partner currently in a residential (inpatient) institution?",
        "Befindet sich Ihr(e) Partner(in) derzeit in einer stationären Einrichtung?",
        "Votre partenaire est-il/elle actuellement dans un établissement avec hébergement ?",
        "هل شريكك حاليًا في مؤسسة إقامة داخلية؟",
        "Partneriniz şu anda yatılı bir kurumda mı?",
        "A ndodhet partneri juaj aktualisht në një institucion me qëndrim?",
    )),
    W_FOREIGN_A: _Q((
        "Do you receive (or have you applied for) a child benefit from outside Germany instead of Kindergeld?",
        "Erhalten Sie (oder haben Sie beantragt) für Ihre Kinder statt Kindergeld eine Geldleistung aus dem Ausland?",
        "Recevez-vous (ou avez-vous demandé) une prestation pour enfants de l'étranger au lieu du Kindergeld ?",
        "هل تتلقى (أو قدمت طلبًا) لإعانة أطفال من خارج ألمانيا بدلاً من Kindergeld؟",
        "Kindergeld yerine yurt dışından bir çocuk yardımı alıyor musunuz (veya başvurdunuz mu)?",
        "A merrni (ose keni aplikuar) një përfitim fëmijësh nga jashtë Gjermanisë në vend të Kindergeld?",
    )),
    W_FOREIGN_P: _Q((
        "Does your partner receive (or have they applied for) a child benefit from outside Germany instead of Kindergeld?",
        "Erhält Ihr(e) Partner(in) (oder hat beantragt) für die Kinder statt Kindergeld eine Geldleistung aus dem Ausland?",
        "Votre partenaire reçoit-il/elle (ou a-t-il/elle demandé) une prestation pour enfants de l'étranger au lieu du Kindergeld ?",
        "هل يتلقى شريكك (أو قدّم طلبًا) لإعانة أطفال من خارج ألمانيا بدلاً من Kindergeld؟",
        "Partneriniz Kindergeld yerine yurt dışından bir çocuk yardımı alıyor mu (veya başvurdu mu)?",
        "A merr partneri juaj (ose ka aplikuar) një përfitim fëmijësh nga jashtë Gjermanisë në vend të Kindergeld?",
    )),

    # ── Frage 2 — housing ────────────────────────────────────────────────
    W_MIETE: _Q((
        "Do you live in rented accommodation?",
        "Wohnen Sie zur Miete?",
        "Vivez-vous dans un logement loué ?",
        "هل تعيش في مسكن مستأجر؟",
        "Kiralık bir evde mi yaşıyorsunuz?",
        "A jetoni në një banesë me qira?",
    )),
    W_MIETVERTRAG: _Q((
        "Are you attaching the rental contract or a current rent certificate?",
        "Fügen Sie den Mietvertrag oder eine aktuelle Mietbescheinigung bei?",
        "Joignez-vous le contrat de location ou une attestation de loyer actuelle ?",
        "هل ترفق عقد الإيجار أو شهادة إيجار حديثة؟",
        "Kira sözleşmesini veya güncel kira belgesini ekliyor musunuz?",
        "A po bashkëngjisni kontratën e qirasë ose një vërtetim aktual qiraje?",
    )),
    W_KONTOAUSZUG: _Q((
        "Are you attaching a bank statement (because the rent contract is older than one year)?",
        "Fügen Sie einen Kontoauszug bei (weil der Mietvertrag älter als ein Jahr ist)?",
        "Joignez-vous un relevé bancaire (car le bail a plus d'un an) ?",
        "هل ترفق كشف حساب (لأن عقد الإيجار أقدم من سنة)؟",
        "Banka dökümü ekliyor musunuz (kira sözleşmesi bir yıldan eski olduğu için)?",
        "A po bashkëngjisni një nxjerrje llogarie (sepse kontrata e qirasë është më e vjetër se një vit)?",
    )),
    W_HEIZ_MIETE: _Q((
        "Are you attaching proof of your heating costs?",
        "Fügen Sie Belege über Ihre Heizkosten bei?",
        "Joignez-vous un justificatif de vos frais de chauffage ?",
        "هل ترفق إثبات تكاليف التدفئة؟",
        "Isıtma masraflarınızın belgesini ekliyor musunuz?",
        "A po bashkëngjisni dëshmi të shpenzimeve të ngrohjes?",
    )),
    W_BETRIEBSK: _Q((
        "Are you attaching proof of your incidental/operating costs?",
        "Fügen Sie Belege über Ihre Nebenkosten bei?",
        "Joignez-vous un justificatif de vos charges ?",
        "هل ترفق إثبات النفقات الجانبية؟",
        "Yan giderlerinizin belgesini ekliyor musunuz?",
        "A po bashkëngjisni dëshmi të shpenzimeve shtesë?",
    )),
    W_WG_MIETE: _Q((
        "Are you attaching a housing benefit (Wohngeld) decision, if you applied for it?",
        "Fügen Sie einen Wohngeldbescheid bei, falls beantragt?",
        "Joignez-vous une notification d'allocation logement (Wohngeld), si demandée ?",
        "هل ترفق قرار بدل السكن (Wohngeld) إذا طلبته؟",
        "Başvurduysanız konut yardımı (Wohngeld) kararını ekliyor musunuz?",
        "A po bashkëngjisni një vendim për Wohngeld, nëse keni aplikuar?",
    )),
    W_MIETZUSCHUSS: _Q((
        "Are you attaching a decision about a municipal rent subsidy, if you applied for it?",
        "Fügen Sie einen Bescheid über kommunalen Mietzuschuss bei, falls beantragt?",
        "Joignez-vous une décision relative à une subvention municipale au loyer, si demandée ?",
        "هل ترفق قرارًا بشأن دعم إيجار بلدي إذا طلبته؟",
        "Başvurduysanız belediye kira desteği kararını ekliyor musunuz?",
        "A po bashkëngjisni një vendim për subvencion komunal qiraje, nëse keni aplikuar?",
    )),
    W_EIGENHEIM: _Q((
        "Do you live in your own home (property you own)?",
        "Wohnen Sie in einem Eigenheim?",
        "Vivez-vous dans votre propre logement (que vous possédez) ?",
        "هل تعيش في منزلك الخاص (تملكه)؟",
        "Kendi evinizde mi (sahibi olduğunuz) yaşıyorsunuz?",
        "A jetoni në shtëpinë tuaj (që e zotëroni)?",
    )),
    W_SCHULDZINSEN: _Q((
        "Are you attaching proof of your mortgage interest (without repayment instalments)?",
        "Fügen Sie einen Nachweis über die Schuldzinsen bei (ohne Tilgungsraten)?",
        "Joignez-vous un justificatif des intérêts d'emprunt (hors remboursement) ?",
        "هل ترفق إثبات فوائد القرض (دون أقساط السداد)؟",
        "Kredi faizinizin belgesini ekliyor musunuz (anapara taksitleri hariç)?",
        "A po bashkëngjisni dëshmi të interesave të kredisë (pa këstet e shlyerjes)?",
    )),
    W_GRUNDSTEUER: _Q((
        "Are you attaching proof of property tax and building insurance?",
        "Fügen Sie einen Nachweis über Grundsteuer und Gebäudeversicherung bei?",
        "Joignez-vous un justificatif de la taxe foncière et de l'assurance habitation ?",
        "هل ترفق إثبات ضريبة العقار وتأمين المبنى؟",
        "Emlak vergisi ve bina sigortası belgesini ekliyor musunuz?",
        "A po bashkëngjisni dëshmi të tatimit mbi pronën dhe sigurimit të ndërtesës?",
    )),
    W_HEIZ_EIGEN: _Q((
        "Are you attaching proof of your heating costs for the home you own?",
        "Fügen Sie Belege über Ihre Heizkosten (Eigenheim) bei?",
        "Joignez-vous un justificatif des frais de chauffage de votre logement ?",
        "هل ترفق إثبات تكاليف التدفئة لمنزلك المملوك؟",
        "Sahip olduğunuz evin ısıtma masraflarının belgesini ekliyor musunuz?",
        "A po bashkëngjisni dëshmi të shpenzimeve të ngrohjes për shtëpinë tuaj?",
    )),
    W_NEBENKOSTEN: _Q((
        "Are you attaching proof of incidental costs for the home you own?",
        "Fügen Sie Belege über Nebenkosten (Eigenheim) bei?",
        "Joignez-vous un justificatif des charges de votre logement ?",
        "هل ترفق إثبات النفقات الجانبية لمنزلك المملوك؟",
        "Sahip olduğunuz evin yan giderlerinin belgesini ekliyor musunuz?",
        "A po bashkëngjisni dëshmi të shpenzimeve shtesë për shtëpinë tuaj?",
    )),
    W_WG_EIGEN: _Q((
        "Are you attaching a housing benefit decision (Lastenzuschuss), if you applied for it?",
        "Fügen Sie einen Wohngeldbescheid (Lastenzuschuss) bei, falls beantragt?",
        "Joignez-vous une notification d'allocation logement (Lastenzuschuss), si demandée ?",
        "هل ترفق قرار بدل السكن (Lastenzuschuss) إذا طلبته؟",
        "Başvurduysanız konut yardımı kararını (Lastenzuschuss) ekliyor musunuz?",
        "A po bashkëngjisni një vendim Wohngeld (Lastenzuschuss), nëse keni aplikuar?",
    )),
    W_EINZUGSDATUM: _Q((
        "If you moved in during this year or last year, what is the exact move-in date? Write - if not.",
        "Falls Sie dieses oder letztes Jahr eingezogen sind: genaues Einzugsdatum? Schreiben Sie -, wenn nicht.",
        "Si vous avez emménagé cette année ou l'an dernier : date exacte d'emménagement ? Écrivez - sinon.",
        "إذا انتقلت هذا العام أو العام الماضي: تاريخ الانتقال الدقيق؟ اكتب - إذا لا.",
        "Bu yıl veya geçen yıl taşındıysanız: tam taşınma tarihi? Değilse - yazın.",
        "Nëse u zhvendosët këtë vit ose vitin e kaluar: data e saktë e zhvendosjes? Shkruani - nëse jo.",
    ), ex="-", fmt="date"),
    L_WARMWASSER: _Q((
        "How is the hot water in your home produced?",
        "Wie wird das Warmwasser in Ihrer Wohnung erzeugt?",
        "Comment l'eau chaude de votre logement est-elle produite ?",
        "كيف يتم إنتاج الماء الساخن في مسكنك؟",
        "Evinizdeki sıcak su nasıl üretiliyor?",
        "Si prodhohet uji i ngrohtë në banesën tuaj?",
    ), helps=(
        "zentral = centrally (e.g. with the central heating); dezentral = locally (e.g. a boiler or instant water heater).",
        "zentral = mit der zentralen Heizungsanlage; dezentral = mit Boiler oder Durchlauferhitzer.",
        "zentral = par le chauffage central ; dezentral = par un chauffe-eau ou un boiler.",
        "zentral = مركزيًا (مع التدفئة المركزية)؛ dezentral = محليًا (سخان أو غلاية).",
        "zentral = merkezi (kalorifer ile); dezentral = yerel (şofben veya boyler).",
        "zentral = qendrore (me ngrohjen qendrore); dezentral = lokale (bojler ose ngrohës i menjëhershëm).",
    )),

    # ── Frage 3 — Vermögen ───────────────────────────────────────────────
    L_VERMOEGEN: _Q((
        "Do you, your partner and your children together have substantial assets above the limit?",
        "Haben Sie, Ihr(e) Partner(in) und Ihre Kinder gemeinsam ein erhebliches Vermögen über der Grenze?",
        "Vous, votre partenaire et vos enfants avez-vous ensemble un patrimoine important au-dessus du seuil ?",
        "هل لديك أنت وشريكك وأطفالك معًا ثروة كبيرة فوق الحد؟",
        "Siz, partneriniz ve çocuklarınız birlikte sınırın üzerinde önemli bir varlığa sahip misiniz?",
        "A keni ju, partneri juaj dhe fëmijët së bashku pasuri të konsiderueshme mbi kufirin?",
    ), helps=(
        "Substantial = e.g. €55,000 for 2 people, €70,000 for 3, +€15,000 per further person. Includes cash, accounts, savings, securities, a second property, a car worth over €15,000, etc. If yes, also fill in the 'Anlage zum erheblichen Vermögen'.",
        "Erheblich = z. B. 55.000 € bei 2 Personen, 70.000 € bei 3, +15.000 € je weiterer Person. Dazu zählen Bargeld, Konten, Sparguthaben, Wertpapiere, eine zweite Immobilie, ein Auto über 15.000 € usw. Falls ja, füllen Sie auch die 'Anlage zum erheblichen Vermögen' aus.",
        "Important = par ex. 55 000 € pour 2 personnes, 70 000 € pour 3, +15 000 € par personne supplémentaire. Inclut espèces, comptes, épargne, titres, un second bien, une voiture de plus de 15 000 €, etc. Si oui, remplissez aussi l'« Anlage zum erheblichen Vermögen ».",
        "كبيرة = مثلاً 55٬000 يورو لشخصين، 70٬000 لثلاثة، +15٬000 لكل شخص إضافي. تشمل النقد والحسابات والمدخرات والأوراق المالية وعقارًا ثانيًا وسيارة بقيمة تتجاوز 15٬000 يورو. إذا نعم، املأ أيضًا ملحق الثروة.",
        "Önemli = örn. 2 kişi için 55.000 €, 3 kişi için 70.000 €, her ek kişi için +15.000 €. Nakit, hesaplar, tasarruf, menkul kıymetler, ikinci bir mülk, 15.000 €'dan değerli araç vb. dahildir. Evetse 'Anlage zum erheblichen Vermögen' formunu da doldurun.",
        "E konsiderueshme = p.sh. 55.000 € për 2 persona, 70.000 € për 3, +15.000 € për çdo person tjetër. Përfshin para, llogari, kursime, letra me vlerë, një pronë të dytë, një makinë mbi 15.000 € etj. Nëse po, plotësoni edhe 'Anlage zum erheblichen Vermögen'.",
    )),

    # ── Frage 4 — Mehrbedarf ─────────────────────────────────────────────
    W_MEHRBEDARF: _Q((
        "Do you and/or your partner have an additional need (e.g. pregnancy, severe disability, costly diet, single parenting)?",
        "Haben Sie und/oder Ihr(e) Partner(in) einen Mehrbedarf (z. B. Schwangerschaft, Schwerbehinderung, kostenaufwändige Ernährung, Alleinerziehung)?",
        "Vous et/ou votre partenaire avez-vous un besoin supplémentaire (par ex. grossesse, handicap lourd, alimentation coûteuse, parent isolé) ?",
        "هل لديك و/أو لدى شريكك حاجة إضافية (مثل حمل، إعاقة شديدة، تغذية مكلفة، إعالة فردية)؟",
        "Siz ve/veya partnerinizin ek bir ihtiyacı var mı (örn. hamilelik, ağır engellilik, masraflı beslenme, tek ebeveynlik)?",
        "A keni ju dhe/ose partneri juaj një nevojë shtesë (p.sh. shtatzëni, paaftësi e rëndë, ushqim i kushtueshëm, prind i vetëm)?",
    ), helps=(
        "This is voluntary — only fill in if you want the extra need considered. Attach suitable proof. No proof is needed for the single-parent extra need.",
        "Freiwillig — nur ausfüllen, wenn ein Mehrbedarf berücksichtigt werden soll. Geeignete Nachweise beifügen. Für den Alleinerziehenden-Mehrbedarf ist kein Nachweis nötig.",
        "Facultatif — à remplir seulement si vous voulez que ce besoin soit pris en compte. Joignez un justificatif. Aucun justificatif n'est requis pour le besoin de parent isolé.",
        "اختياري — املأ فقط إذا أردت أخذ الحاجة الإضافية بعين الاعتبار. أرفق إثباتًا مناسبًا. لا حاجة لإثبات بشأن إعالة فردية.",
        "İsteğe bağlı — yalnızca ek ihtiyacın dikkate alınmasını istiyorsanız doldurun. Uygun belge ekleyin. Tek ebeveyn ek ihtiyacı için belge gerekmez.",
        "Vullnetare — plotësojeni vetëm nëse doni që nevoja shtesë të merret parasysh. Bashkëngjisni dëshmi. Për nevojën e prindit të vetëm nuk nevojitet dëshmi.",
    )),
    W_ENTBINDUNG: _Q((
        "If pregnant: what is the expected delivery date?",
        "Bei Schwangerschaft: Wie lautet der voraussichtliche Entbindungstermin?",
        "En cas de grossesse : quelle est la date prévue de l'accouchement ?",
        "في حالة الحمل: ما هو تاريخ الولادة المتوقع؟",
        "Hamilelik durumunda: tahmini doğum tarihi nedir?",
        "Në rast shtatzënie: cila është data e pritshme e lindjes?",
    ), ex="01.11.2026", fmt="date"),

    # ── Frage 5 secondary proof boxes ────────────────────────────────────
    W_VERDIENST_A: _Q((
        "Are you attaching the employer's income certificate (Verdienstbescheinigung) instead of payslips?",
        "Fügen Sie statt Lohnabrechnungen die Verdienstbescheinigung des Arbeitgebers bei?",
        "Joignez-vous l'attestation de revenu de l'employeur au lieu des fiches de paie ?",
        "هل ترفق شهادة دخل من صاحب العمل بدلاً من كشوف الرواتب؟",
        "Maaş bordroları yerine işveren gelir belgesini mi ekliyorsunuz?",
        "A po bashkëngjisni vërtetimin e të ardhurave nga punëdhënësi në vend të fletëpagesave?",
    )),
    W_VERDIENST_P: _Q((
        "For your partner: are you attaching the employer's income certificate instead of payslips?",
        "Für Ihre(n) Partner(in): Fügen Sie die Verdienstbescheinigung statt Lohnabrechnungen bei?",
        "Pour votre partenaire : joignez-vous l'attestation de revenu de l'employeur au lieu des fiches de paie ?",
        "لشريكك: هل ترفق شهادة دخل صاحب العمل بدلاً من كشوف الرواتب؟",
        "Partneriniz için: maaş bordroları yerine işveren gelir belgesini mi ekliyorsunuz?",
        "Për partnerin: a po bashkëngjisni vërtetimin e të ardhurave nga punëdhënësi në vend të fletëpagesave?",
    )),
    W_SELBST_NACHW_A: _Q((
        "Are you attaching other business records instead of the self-employment annex?",
        "Fügen Sie andere Nachweise über Betriebseinnahmen/-ausgaben statt der Anlage bei?",
        "Joignez-vous d'autres justificatifs d'entreprise au lieu de l'annexe ?",
        "هل ترفق مستندات أعمال أخرى بدلاً من ملحق العمل الحر؟",
        "Serbest meslek eki yerine başka işletme kayıtları mı ekliyorsunuz?",
        "A po bashkëngjisni regjistra të tjerë biznesi në vend të shtojcës?",
    )),
    W_SELBST_NACHW_P: _Q((
        "For your partner: are you attaching other business records instead of the self-employment annex?",
        "Für Ihre(n) Partner(in): Fügen Sie andere Nachweise über Betriebseinnahmen/-ausgaben statt der Anlage bei?",
        "Pour votre partenaire : joignez-vous d'autres justificatifs d'entreprise au lieu de l'annexe ?",
        "لشريكك: هل ترفق مستندات أعمال أخرى بدلاً من ملحق العمل الحر؟",
        "Partneriniz için: serbest meslek eki yerine başka işletme kayıtları mı ekliyorsunuz?",
        "Për partnerin: a po bashkëngjisni regjistra të tjerë biznesi në vend të shtojcës?",
    )),

    # ── Frage 6 Fahrtkosten ──────────────────────────────────────────────
    W_FK_KM_A: _Q((
        "If you drove a car to work, what was the one-way distance in km? Write - if not.",
        "Wenn Sie mit dem Auto zur Arbeit fuhren: einfache Wegstrecke in km? Schreiben Sie -, wenn nicht.",
        "Si vous alliez au travail en voiture : distance aller simple en km ? Écrivez - sinon.",
        "إذا ذهبت إلى العمل بالسيارة: المسافة باتجاه واحد بالكيلومتر؟ اكتب - إذا لا.",
        "İşe arabayla gittiyseniz: tek yön mesafe km olarak? Değilse - yazın.",
        "Nëse shkonit në punë me makinë: distanca një drejtim në km? Shkruani - nëse jo.",
    ), ex="15"),
    W_FK_TAGE_A: _Q((
        "How many days per week did you travel to work?",
        "An wie vielen Tagen pro Woche fuhren Sie zur Arbeit?",
        "Combien de jours par semaine alliez-vous au travail ?",
        "كم يومًا في الأسبوع ذهبت إلى العمل؟",
        "Haftada kaç gün işe gittiniz?",
        "Sa ditë në javë udhëtonit për në punë?",
    ), ex="5"),
    W_FK_KM_P: _Q((
        "If your partner drove a car to work, what was the one-way distance in km? Write - if not.",
        "Wenn Ihr(e) Partner(in) mit dem Auto zur Arbeit fuhr: einfache Wegstrecke in km? Schreiben Sie -, wenn nicht.",
        "Si votre partenaire allait au travail en voiture : distance aller simple en km ? Écrivez - sinon.",
        "إذا ذهب شريكك إلى العمل بالسيارة: المسافة باتجاه واحد بالكيلومتر؟ اكتب - إذا لا.",
        "Partneriniz işe arabayla gittiyse: tek yön mesafe km olarak? Değilse - yazın.",
        "Nëse partneri juaj shkonte në punë me makinë: distanca një drejtim në km? Shkruani - nëse jo.",
    ), ex="15"),
    W_FK_TAGE_P: _Q((
        "How many days per week did your partner travel to work?",
        "An wie vielen Tagen pro Woche fuhr Ihr(e) Partner(in) zur Arbeit?",
        "Combien de jours par semaine votre partenaire allait-il/elle au travail ?",
        "كم يومًا في الأسبوع ذهب شريكك إلى العمل؟",
        "Partneriniz haftada kaç gün işe gitti?",
        "Sa ditë në javë udhëtonte partneri juaj për në punë?",
    ), ex="5"),

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

# ── Generate the income / expense A+P questions ───────────────────────────────
for _base, _wa, _wp, _noun, _att in _INCOME:
    _QUESTIONS[_wa] = _money_q(_noun, "A", _att, "income")
    _QUESTIONS[_wp] = _money_q(_noun, "P", _att, "income")

# fk_oeffis (public transport) — phrased as an expense
_FK_OEFFIS_NOUN = (
    "public transport tickets to work",
    "Fahrkarten für öffentliche Verkehrsmittel zur Arbeit",
    "des titres de transport public pour aller au travail",
    "تذاكر مواصلات عامة للعمل",
    "işe gidiş için toplu taşıma biletleri",
    "bileta transporti publik për në punë",
)
_QUESTIONS[W_FK_OEFFIS_A] = _money_q(_FK_OEFFIS_NOUN, "A", None, "expense")
_QUESTIONS[W_FK_OEFFIS_P] = _money_q(_FK_OEFFIS_NOUN, "P", None, "expense")

for _base, _wa, _wp, _noun, _att in _EXPENSE:
    _QUESTIONS[_wa] = _money_q(_noun, "A", _att, "expense")
    _QUESTIONS[_wp] = _money_q(_noun, "P", _att, "expense")


def _register_kizana_verified_questions() -> None:
    """Merge KiZ Anlage Antragsteller verified questions into VERIFIED_BY_FIELD_ID.
    Runs once at module import (lazily via form_templates._all_templates())."""
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    VERIFIED_BY_FIELD_ID.update(_QUESTIONS)


_register_kizana_verified_questions()
