"""
Verified field map for the Jobcenter "Hauptantrag Bürgergeld" (SGB II).

Seventh Level 1 verified template — the main application for basic income
support, the highest-volume Jobcenter form. Unlike the Familienkasse forms
this is a BORN-AcroForm PDF (real /AP appearance streams, technical field
names like txtfPersonVorname): checkboxes export the custom value
"selektiert" and the ja/nein questions are NATIVE radio fields with export
values "0" (Ja) / "1" (Nein). It therefore uses fill_strategy="pypdf_native"
(see app/services/pdf_generator/pypdf_native_fill.py) — fitz mis-handles
both custom exports.

Source PDF
----------
templates_source/incoming/buergergeld_hauptantrag.pdf
(official: arbeitsagentur.de/datei/antrag-sgb2_ba042689.pdf, Jobcenter-HA 04/2026)

Fingerprint
-----------
Required (all): "hauptantrag bürgergeld" + the page footer "jobcenter-ha".
Both are unique to this form: the WBA carries "jobcenter-wba", and the BuT
template requires "persönliche angaben" which this form does not contain
(it uses "persönliche daten"). Verified empirically.

Mechanics (verified on the real PDF)
------------------------------------
- Native ja/nein radios (rbtn*): field_type="radio", options "0"/"1" with
  option_labels Ja/Nein. The value IS the export; written directly. Gating
  helpers _ja()/_nein() compare against "0"/"1".
- Logical checkbox-radios (RadioGroup): gender (4), marital status (7),
  pension-number status (3), benefit-start (2) — one user question over
  several "selektiert" checkboxes; expand_logical_fields writes Yes/Off and
  the pypdf_native engine maps Yes → the real on-state "selektiert".
- Independent checkboxes: the "other benefits applied for" list (Q43) and the
  "who lives with you" list (Q80), gated on their trigger radio.
- "weiter mit N" skip logic from the paper form is reproduced with conditions.

Every shown field has a verified question in en/de/fr/ar/tr/sq.
weak_questions=0 and ai_calls_made=0 invariants must hold.
"""
from __future__ import annotations

from app.services.form_templates import RadioGroup, VerifiedTemplate

# ── Native radio export values (verified: 0=Ja, 1=Nein on every rbtn) ─────────
_JA = "0"
_NEIN = "1"
_YESNO_LABELS = {"0": "Ja", "1": "Nein"}

# ── Logical IDs (RadioGroup over checkbox widgets) ────────────────────────────
L_GESCHLECHT  = "bg_geschlecht"
L_RVNR_STATUS = "bg_rvnr_status"
L_BUEG_AB     = "bg_bueg_ab"
L_FAMSTAND    = "bg_familienstand"


# ── Conditions ────────────────────────────────────────────────────────────────
def _ja(field: str) -> dict:
    return {"type": "field_equals", "field_key": field, "value": _JA}


def _nein(field: str) -> dict:
    return {"type": "field_equals", "field_key": field, "value": _NEIN}


def _eq(field: str, value: str) -> dict:
    return {"type": "field_equals", "field_key": field, "value": value}


_C_GETRENNT = {"type": "field_in", "field_key": L_FAMSTAND,
               "values": ["getrennt", "geschieden", "aufgehoben"]}


_REQUIRED = ["hauptantrag bürgergeld", "jobcenter-ha"]


class BuergergeldHauptantragTemplate(VerifiedTemplate):
    template_id   = "buergergeld_hauptantrag_v1"
    name          = "Jobcenter — Hauptantrag Bürgergeld (SGB II)"
    fill_strategy = "pypdf_native"

    def fingerprint(self, full_text: str) -> bool:
        lo = full_text.lower()
        return all(p in lo for p in _REQUIRED)

    def get_field_map(self) -> list:
        from app.services.pdf_pipeline import FieldMapEntry

        def txt(field_id, label, page, condition=None, ftype="text", src=None):
            return FieldMapEntry(
                field_id=field_id, original_label=label, field_type=ftype,
                source_page=page, options=[], current_value="", confidence=1.0,
                source="verified_template", source_text=src or label,
                reason="pdf_field", condition=condition,
            )

        def yesno(field_id, label, page, condition=None):
            """A native ja/nein radio (export 0=Ja, 1=Nein)."""
            e = FieldMapEntry(
                field_id=field_id, original_label=label, field_type="radio",
                source_page=page, options=[_JA, _NEIN], current_value="",
                confidence=1.0, source="verified_template", source_text=label,
                reason="pdf_field", condition=condition,
            )
            e.option_labels = dict(_YESNO_LABELS)
            return e

        def logical(field_id, label, page, opts, condition=None):
            return FieldMapEntry(
                field_id=field_id, original_label=label, field_type="radio",
                source_page=page, options=opts, current_value="", confidence=1.0,
                source="verified_template", source_text=label,
                reason="pdf_field", condition=condition,
            )

        def chk(field_id, label, page, condition=None):
            return FieldMapEntry(
                field_id=field_id, original_label=label, field_type="checkbox",
                source_page=page, options=[], current_value="", confidence=1.0,
                source="verified_template", source_text=label,
                reason="pdf_field", condition=condition,
            )

        return [
            # ── A. Persönliche Daten (page 1) ────────────────────────────
            txt("txtfPersonVorname", "Vorname", 1),
            txt("txtfPersonNachname", "Nachname", 1),
            txt("datePersonGebDatum", "Geburtsdatum", 1),
            txt("txtfPersonGebName", "Geburtsname / früherer Name", 1),
            txt("txtfPersonGebOrt", "Geburtsort", 1),
            txt("txtfPersonGebLand", "Geburtsland", 1),
            txt("txtfPersonStaat", "Staatsangehörigkeit", 1),
            logical(L_GESCHLECHT, "Geschlecht", 1,
                    ["männlich", "weiblich", "divers", "keine Angabe"]),
            txt("txtfPersonStr", "Straße", 1),
            txt("txtfPersonHausNr", "Hausnummer", 1),
            txt("txtfPersonPlz", "Postleitzahl", 1),
            txt("txtfPersonOrt", "Wohnort", 1),
            txt("txtfPersonPostfach", "Postfachanschrift", 1),
            txt("txtfPersonTel", "Telefonnummer (freiwillig)", 1),
            yesno("rbtnWohnsitz", "Kein fester Wohnsitz?", 1),
            txt("txtareaWohnhaft", "Gegebenenfalls wohnhaft bei (Name und Anschrift)", 1),

            # ── Bankverbindung + IDs (page 2) ────────────────────────────
            txt("txtfKonto", "Kontoinhaberin / Kontoinhaber", 2),
            txt("txtfKontoIBAN", "IBAN", 2),
            txt("txtareaKontoGrund", "Grund, falls keine Bankverbindung angegeben werden kann", 2),
            logical(L_RVNR_STATUS, "Rentenversicherungsnummer", 2,
                    ["vorhanden", "nicht vorhanden", "beantragt"]),
            txt("txtfRVNr", "Rentenversicherungsnummer", 2,
                condition=_eq(L_RVNR_STATUS, "vorhanden")),
            txt("numfStIDNr", "Steuerliche Identifikationsnummer", 2),
            yesno("rbtnBetreuer", "Gesetzliche Betreuung, Bevollmächtigte oder Vormund?", 2),

            # ── B. Nationalität (page 2) ─────────────────────────────────
            yesno("rbtnAufenthalt", "Gültiger Aufenthaltstitel?", 2),
            yesno("rbtnAsylbLG", "Leistungen nach dem Asylbewerberleistungsgesetz?", 2),
            txt("dateAsylbLG", "Asylbewerberleistungen bis", 2, condition=_ja("rbtnAsylbLG")),
            txt("txtfAZRNr", "Ausländerzentralregisternummer (falls vorhanden)", 2),
            yesno("rbtnKostenUebernahme", "Verpflichtungserklärung (Kostenübernahme)?", 2),
            txt("txtfNatIDNr", "Nationale Personenidentifikationsnummer (falls vorhanden)", 2),

            # ── C. Antragstellung (page 3) ───────────────────────────────
            logical(L_BUEG_AB, "Bürgergeld ab wann?", 3, ["ab sofort", "später"]),
            txt("dateBUEGSpaeter", "Späterer Zeitpunkt", 3,
                condition=_eq(L_BUEG_AB, "später")),
            txt("dateEinreise", "Datum der Einreise nach Deutschland (falls zutreffend)", 3),

            # ── D. Aktuelle Lebenssituation (page 3) ─────────────────────
            logical(L_FAMSTAND, "Familienstand", 3,
                    ["ledig", "verheiratet", "verwitwet", "eingetragene Lebenspartnerschaft",
                     "getrennt", "geschieden", "aufgehoben"]),
            txt("dateGetrennt", "Getrennt lebend / geschieden seit", 3, condition=_C_GETRENNT),
            yesno("rtbnErwerbsfaehig", "Erwerbsfähig (mind. 3 Stunden täglich arbeiten können)?", 3),
            yesno("rbtnAlleinerziehend", "Alleinerziehend?", 3),
            yesno("rbtnSchwanger", "Schwanger?", 3),
            txt("dateEntbindung", "Voraussichtlicher Entbindungstermin", 3, condition=_ja("rbtnSchwanger")),
            yesno("rbtnElternAusserhalb", "Unter 25 und ein Elternteil lebt außerhalb der Bedarfsgemeinschaft?", 3),
            yesno("rbtnSchueler", "Schüler/in, Student/in oder Auszubildende/r?", 3),
            yesno("rbtnKostenBuecher", "Kosten für Schulbücher / Arbeitshefte?", 3, condition=_ja("rbtnSchueler")),

            # ── (page 4) ─────────────────────────────────────────────────
            yesno("rbtnAusbildungUneterkunft", "Während der Ausbildung auswärts untergebracht?", 4, condition=_ja("rbtnSchueler")),
            yesno("rbtnLeistungAndere", "Andere Leistungen beantragt oder geplant?", 4),
            chk("chbxLeistungBafoeg", "BAföG beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungBAB", "Berufsausbildungsbeihilfe (BAB) beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungWohngeld", "Wohngeld beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungArbeitslosengeld", "Arbeitslosengeld beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungRente", "Rente beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungKRG", "Krankengeld beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungKG", "Kindergeld beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungKIZ", "Kinderzuschlag beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            chk("chbxLeistungSonstiges", "Sonstige Leistungen beantragt", 4, condition=_ja("rbtnLeistungAndere")),
            txt("txtfLeistungSonstiges", "Welche sonstigen Leistungen?", 4, condition=_eq("chbxLeistungSonstiges", "yes")),
            yesno("rbtnMEB", "Aus medizinischen Gründen kostenaufwändige Ernährung nötig?", 4),
            yesno("rbtnBehinderung", "Behinderung?", 4),
            yesno("rbtnLeistungTeilhabe", "Leistungen zur Teilhabe am Arbeitsleben (SGB IX)?", 4, condition=_ja("rbtnBehinderung")),
            yesno("rbtnBB", "Unabweisbarer besonderer Bedarf?", 4),
            yesno("rbtnStationaer", "Derzeit oder demnächst in einer stationären Einrichtung?", 4),
            txt("txtfStationaerArt", "Art der stationären Einrichtung", 4, condition=_ja("rbtnStationaer")),
            txt("dateStationaerVon", "Aufenthalt von", 4, condition=_ja("rbtnStationaer")),
            txt("dateStationaerBis", "Aufenthalt bis", 4, condition=_ja("rbtnStationaer")),

            # ── E. Bisherige Lebenssituation (page 5) ────────────────────
            yesno("rbtnBUEG", "In den letzten 3 Jahren Bürgergeld oder Sozialhilfe bezogen/beantragt?", 5),
            txt("txtfLeistungArt", "Art der Leistung", 5, condition=_ja("rbtnBUEG")),
            txt("dateLeistungVon", "Leistung von", 5, condition=_ja("rbtnBUEG")),
            txt("dateLeistungBis", "Leistung bis", 5, condition=_ja("rbtnBUEG")),
            txt("txtfTraegerName", "Name des Leistungsträgers", 5, condition=_ja("rbtnBUEG")),
            txt("txtfTraegerStr", "Straße des Leistungsträgers", 5, condition=_ja("rbtnBUEG")),
            txt("txtfTraegerHausNr", "Hausnummer des Leistungsträgers", 5, condition=_ja("rbtnBUEG")),
            txt("txtfTraegerPlz", "Postleitzahl des Leistungsträgers", 5, condition=_ja("rbtnBUEG")),
            txt("txtfTraegerOrt", "Ort des Leistungsträgers", 5, condition=_ja("rbtnBUEG")),
            yesno("rbtnAngestellt", "In den letzten 5 Jahren angestellt / beschäftigt?", 5),
            txt("dateBeschaeftigtVon", "Beschäftigung von", 5, condition=_ja("rbtnAngestellt")),
            txt("dateBeschaeftigtBis", "Beschäftigung bis", 5, condition=_ja("rbtnAngestellt")),
            txt("dateBeschaeftigt2Von", "Weitere Beschäftigung von", 5, condition=_ja("rbtnAngestellt")),
            txt("dateBeschaeftigt2Bis", "Weitere Beschäftigung bis", 5, condition=_ja("rbtnAngestellt")),
            yesno("rbtnLohnanspruch", "Ausstehende Lohnansprüche gegen einen Arbeitgeber?", 5, condition=_ja("rbtnAngestellt")),
            txt("txtfAGName", "Name des Arbeitgebers", 5, condition=_ja("rbtnLohnanspruch")),
            txt("txtfAGStr", "Straße des Arbeitgebers", 5, condition=_ja("rbtnLohnanspruch")),
            txt("txtfAGHausNr", "Hausnummer des Arbeitgebers", 5, condition=_ja("rbtnLohnanspruch")),
            txt("txtfAGPlz", "Postleitzahl des Arbeitgebers", 5, condition=_ja("rbtnLohnanspruch")),
            txt("txtfAGOrt", "Ort des Arbeitgebers", 5, condition=_ja("rbtnLohnanspruch")),
            yesno("rbtnSelbstaendig", "In den letzten 5 Jahren selbständig / freiberuflich tätig?", 5),
            yesno("rbtnEntgeltersatz", "Entgeltersatzleistungen erhalten (z. B. Krankengeld, ALG, Elterngeld)?", 5),
            txt("txtfEntgeltersatz", "Welche Entgeltersatzleistung?", 5, condition=_ja("rbtnEntgeltersatz")),
            txt("dateEntgeltersatzVon", "Entgeltersatzleistung von", 5, condition=_ja("rbtnEntgeltersatz")),
            txt("dateEntgeltersatzBis", "Entgeltersatzleistung bis", 5, condition=_ja("rbtnEntgeltersatz")),

            # ── (page 6) ─────────────────────────────────────────────────
            yesno("rbtnWehrdienst", "Wehrdienst oder freiwilligen Dienst geleistet?", 6),
            yesno("rbtnPflege", "Angehörige gepflegt (SGB XI)?", 6),
            txt("txtareaLebensunterhalt", "Wie haben Sie Ihren Lebensunterhalt bestritten?", 6),
            yesno("rbtnAnspruchDritte", "Anspruch gegenüber Dritten (z. B. Schadensersatz, Erbschaft)?", 6),
            yesno("rbtnSchadenDritte", "Unfall oder Gesundheitsschaden durch Dritte?", 6),
            yesno("rbtnKVPV", "Gesetzlich kranken- und pflegeversichert (familien-/pflichtversichert)?", 6),
            txt("txtfKV", "Name der Krankenkasse", 6),
            yesno("rbtnPKV", "Privat, freiwillig gesetzlich oder nicht versichert?", 6),

            # ── G. Wohnsituation (page 6-7) ──────────────────────────────
            yesno("rbtnWohnsituation", "Wohnen Sie allein?", 6),
            chk("chbxWohnenEhegatte", "Ehegatte / Partner (eheähnliche Gemeinschaft)", 6, condition=_nein("rbtnWohnsituation")),
            chk("chbxWohnenKind", "Unverheiratete Kinder zwischen 15 und 24 Jahren", 6, condition=_nein("rbtnWohnsituation")),
            chk("chbxWohnenKindU15", "Kinder unter 15 Jahren", 6, condition=_nein("rbtnWohnsituation")),
            chk("chbxWohnenEltern", "Eltern oder ein Elternteil", 7, condition=_nein("rbtnWohnsituation")),
            chk("chbxWohnenVerwandte", "Sonstige Verwandte oder Verschwägerte", 7, condition=_nein("rbtnWohnsituation")),
            chk("chbxWohnenSonstige", "Sonstige Personen (z. B. Wohngemeinschaft)", 7, condition=_nein("rbtnWohnsituation")),
            yesno("rbtnBedarfUnterkunft", "Entstehen Ihnen Bedarfe für Unterkunft und Heizung?", 7),

            # ── I. Unterschrift (page 8) ─────────────────────────────────
            txt("dateUnterschriftPerson", "Datum (Unterschrift antragstellende Person)", 8),
            txt("dateUnterschriftBetreuer", "Datum (Unterschrift Betreuer/Vormund)", 8, condition=_ja("rbtnBetreuer")),
        ]

    def get_radio_groups(self) -> list[RadioGroup]:
        return [
            RadioGroup(
                field_id=L_GESCHLECHT,
                widget_names=["chbxMaennlich", "chbxWeiblich", "chbxDivers", "chbxKeineAngabe"],
                options=[("männlich", "chbxMaennlich"), ("weiblich", "chbxWeiblich"),
                         ("divers", "chbxDivers"), ("keine Angabe", "chbxKeineAngabe")],
            ),
            RadioGroup(
                field_id=L_RVNR_STATUS,
                widget_names=["chbxRVNrVorhanden", "chbxRVNrKeine", "chbxRVNrBeantragt"],
                options=[("vorhanden", "chbxRVNrVorhanden"),
                         ("nicht vorhanden", "chbxRVNrKeine"),
                         ("beantragt", "chbxRVNrBeantragt")],
            ),
            RadioGroup(
                field_id=L_BUEG_AB,
                widget_names=["chbxBUEGSofort", "chbxBUEGSpaeter"],
                options=[("ab sofort", "chbxBUEGSofort"), ("später", "chbxBUEGSpaeter")],
            ),
            RadioGroup(
                field_id=L_FAMSTAND,
                widget_names=["chbxFamStandLedig", "chbxFamStandVerheiratet",
                              "chbxFamStandVerwitwet", "chbxFamStandEingetragen",
                              "chbxFamStandGetrennt", "chbxFamStandGeschieden",
                              "chbxFamStandAufgehoben"],
                options=[("ledig", "chbxFamStandLedig"),
                         ("verheiratet", "chbxFamStandVerheiratet"),
                         ("verwitwet", "chbxFamStandVerwitwet"),
                         ("eingetragene Lebenspartnerschaft", "chbxFamStandEingetragen"),
                         ("getrennt", "chbxFamStandGetrennt"),
                         ("geschieden", "chbxFamStandGeschieden"),
                         ("aufgehoben", "chbxFamStandAufgehoben")],
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


_QUESTIONS: dict = {
    # ── A. Persönliche Daten ─────────────────────────────────────────────
    "txtfPersonVorname": _Q((
        "What is your first name?", "Wie lautet Ihr Vorname?", "Quel est votre prénom ?",
        "ما هو اسمك الأول؟", "Adınız nedir?", "Cili është emri juaj?",
    ), ex="Aminata"),
    "txtfPersonNachname": _Q((
        "What is your last name?", "Wie lautet Ihr Nachname?", "Quel est votre nom de famille ?",
        "ما هو اسم عائلتك؟", "Soyadınız nedir?", "Cili është mbiemri juaj?",
    ), ex="Diallo"),
    "datePersonGebDatum": _Q((
        "What is your date of birth?", "Wann wurden Sie geboren?", "Quelle est votre date de naissance ?",
        "ما تاريخ ميلادك؟", "Doğum tarihiniz nedir?", "Cila është data juaj e lindjes?",
    ), ex="15.03.1990", fmt="date"),
    "txtfPersonGebName": _Q((
        "What is your birth name or former name, if different? Write - if the same.",
        "Wie lautet Ihr Geburtsname oder früherer Name, falls abweichend? Schreiben Sie -, wenn gleich.",
        "Quel est votre nom de naissance ou nom antérieur, s'il diffère ? Écrivez - sinon.",
        "ما اسم الميلاد أو اسمك السابق إن اختلف؟ اكتب - إذا كان نفسه.",
        "Doğum adınız veya önceki adınız farklıysa nedir? Aynıysa - yazın.",
        "Cili është mbiemri i lindjes ose i mëparshëm nëse ndryshon? Shkruani - nëse i njëjtë.",
    ), ex="-"),
    "txtfPersonGebOrt": _Q((
        "Where were you born (city)?", "Wo wurden Sie geboren (Ort)?", "Où êtes-vous né(e) (ville) ?",
        "أين وُلدت (المدينة)؟", "Nerede doğdunuz (şehir)?", "Ku keni lindur (qyteti)?",
    ), ex="Conakry"),
    "txtfPersonGebLand": _Q((
        "In which country were you born?", "In welchem Land wurden Sie geboren?", "Dans quel pays êtes-vous né(e) ?",
        "في أي بلد وُلدت؟", "Hangi ülkede doğdunuz?", "Në cilin shtet keni lindur?",
    ), ex=("Guinea", "Guinea", "Guinée", "غينيا", "Gine", "Guine")),
    "txtfPersonStaat": _Q((
        "What is your nationality?", "Welche Staatsangehörigkeit haben Sie?", "Quelle est votre nationalité ?",
        "ما جنسيتك؟", "Uyruğunuz nedir?", "Cila është shtetësia juaj?",
    ), ex=("Guinean", "guineisch", "guinéenne", "غينية", "Gineli", "guineane")),
    L_GESCHLECHT: _Q((
        "What is your gender?", "Welches Geschlecht haben Sie?", "Quel est votre genre ?",
        "ما هو جنسك؟", "Cinsiyetiniz nedir?", "Cila është gjinia juaj?",
    ), helps=(
        "männlich = male, weiblich = female, divers = diverse, keine Angabe = prefer not to say.",
        "männlich, weiblich, divers oder keine Angabe.",
        "männlich = masculin, weiblich = féminin, divers = divers, keine Angabe = ne pas préciser.",
        "männlich = ذكر، weiblich = أنثى، divers = آخر، keine Angabe = دون تحديد.",
        "männlich = erkek, weiblich = kadın, divers = diğer, keine Angabe = belirtmek istemiyorum.",
        "männlich = mashkull, weiblich = femër, divers = tjetër, keine Angabe = pa deklaruar.",
    )),
    "txtfPersonStr": _Q((
        "What is your street name?", "Wie lautet Ihre Straße?", "Quel est le nom de votre rue ?",
        "ما اسم شارعك؟", "Sokak adınız nedir?", "Cili është emri i rrugës suaj?",
    ), ex="Hauptstraße"),
    "txtfPersonHausNr": _Q((
        "What is your house number?", "Wie lautet Ihre Hausnummer?", "Quel est votre numéro de maison ?",
        "ما رقم منزلك؟", "Kapı numaranız nedir?", "Cili është numri i shtëpisë suaj?",
    ), ex="12"),
    "txtfPersonPlz": _Q((
        "What is your postal code?", "Wie lautet Ihre Postleitzahl?", "Quel est votre code postal ?",
        "ما رمزك البريدي؟", "Posta kodunuz nedir?", "Cili është kodi juaj postar?",
    ), ex="18055"),
    "txtfPersonOrt": _Q((
        "What is your town or city?", "Wie lautet Ihr Wohnort?", "Quelle est votre ville ?",
        "ما مدينتك؟", "Şehriniz nedir?", "Cili është qyteti juaj?",
    ), ex="Rostock"),
    "txtfPersonPostfach": _Q((
        "What is your PO box address, if you have one? Write - if none.",
        "Wie lautet Ihre Postfachanschrift, falls vorhanden? Schreiben Sie -, wenn keine.",
        "Quelle est votre adresse de boîte postale, le cas échéant ? Écrivez - sinon.",
        "ما عنوان صندوق البريد إن وُجد؟ اكتب - إذا لا.",
        "Varsa posta kutusu adresiniz nedir? Yoksa - yazın.",
        "Cila është adresa e kutisë postare nëse keni? Shkruani - nëse jo.",
    ), ex="-"),
    "txtfPersonTel": _Q((
        "What is your phone number? This is voluntary — write - to leave it out.",
        "Wie lautet Ihre Telefonnummer? Freiwillig — schreiben Sie -, wenn Sie keine angeben möchten.",
        "Quel est votre numéro de téléphone ? Facultatif — écrivez - pour ne pas le donner.",
        "ما رقم هاتفك؟ اختياري — اكتب - إذا لم ترغب في ذكره.",
        "Telefon numaranız nedir? İsteğe bağlı — vermek istemiyorsanız - yazın.",
        "Cili është numri juaj i telefonit? Vullnetare — shkruani - nëse nuk doni ta jepni.",
    ), ex="-"),
    "rbtnWohnsitz": _Q((
        "Do you have no fixed address (no permanent home)?",
        "Haben Sie keinen festen Wohnsitz?",
        "N'avez-vous pas de domicile fixe ?",
        "هل ليس لديك محل إقامة ثابت؟",
        "Sabit bir ikametgâhınız yok mu?",
        "A nuk keni një vendbanim të përhershëm?",
    )),
    "txtareaWohnhaft": _Q((
        "If you stay with a person or institution, what is their name and address? Write - if not applicable.",
        "Falls Sie bei einer Person/Einrichtung wohnen: Name und Anschrift? Schreiben Sie -, wenn nicht zutreffend.",
        "Si vous logez chez une personne/institution : nom et adresse ? Écrivez - sinon.",
        "إذا كنت تقيم لدى شخص/مؤسسة: الاسم والعنوان؟ اكتب - إذا لم ينطبق.",
        "Bir kişi/kurumda kalıyorsanız: ad ve adres? Uygun değilse - yazın.",
        "Nëse qëndroni te një person/institucion: emri dhe adresa? Shkruani - nëse jo.",
    ), ex="-"),

    # ── Bank + IDs ───────────────────────────────────────────────────────
    "txtfKonto": _Q((
        "Who is the account holder (the name on the bank account)?",
        "Wer ist die Kontoinhaberin / der Kontoinhaber?",
        "Qui est le/la titulaire du compte ?",
        "من هو صاحب الحساب؟", "Hesap sahibi kim?", "Kush është mbajtësi i llogarisë?",
    ), ex="Aminata Diallo"),
    "txtfKontoIBAN": _Q((
        "What is your IBAN (account number)?", "Wie lautet Ihre IBAN?", "Quel est votre IBAN ?",
        "ما هو IBAN الخاص بك؟", "IBAN'ınız nedir?", "Cili është IBAN-i juaj?",
    ), ex="DE89 3704 0044 0532 0130 00"),
    "txtareaKontoGrund": _Q((
        "If you cannot give a bank account, explain why you cannot open a basic account. Write - if you gave an IBAN.",
        "Falls Sie keine Bankverbindung angeben können: Warum können Sie kein Basiskonto eröffnen? Schreiben Sie -, wenn Sie eine IBAN angegeben haben.",
        "Si vous ne pouvez pas donner de compte : pourquoi ne pouvez-vous pas ouvrir un compte de base ? Écrivez - si vous avez donné un IBAN.",
        "إذا لم تستطع تقديم حساب: لماذا لا يمكنك فتح حساب أساسي؟ اكتب - إذا أعطيت IBAN.",
        "Banka hesabı veremiyorsanız: neden temel hesap açamıyorsunuz? IBAN verdiyseniz - yazın.",
        "Nëse nuk mund të jepni llogari: pse nuk mund të hapni një llogari bazë? Shkruani - nëse keni dhënë IBAN.",
    ), ex="-"),
    L_RVNR_STATUS: _Q((
        "What is the status of your pension/social-insurance number?",
        "Wie ist der Status Ihrer Rentenversicherungs-/Sozialversicherungsnummer?",
        "Quel est le statut de votre numéro d'assurance pension/sociale ?",
        "ما حالة رقم تأمينك التقاعدي/الاجتماعي؟",
        "Emeklilik/sosyal sigorta numaranızın durumu nedir?",
        "Cili është statusi i numrit tuaj të sigurimit pensional/social?",
    ), helps=(
        "vorhanden = I have one, nicht vorhanden = I don't have one, beantragt = I have applied for one.",
        "vorhanden, nicht vorhanden oder beantragt.",
        "vorhanden = j'en ai un, nicht vorhanden = je n'en ai pas, beantragt = j'en ai fait la demande.",
        "vorhanden = لدي، nicht vorhanden = ليس لدي، beantragt = قدمت طلبًا.",
        "vorhanden = var, nicht vorhanden = yok, beantragt = başvurdum.",
        "vorhanden = e kam, nicht vorhanden = nuk e kam, beantragt = kam aplikuar.",
    )),
    "txtfRVNr": _Q((
        "What is your pension insurance number?",
        "Wie lautet Ihre Rentenversicherungsnummer?",
        "Quel est votre numéro d'assurance pension ?",
        "ما رقم تأمينك التقاعدي؟",
        "Emeklilik sigorta numaranız nedir?",
        "Cili është numri juaj i sigurimit pensional?",
    ), ex="65 160390 D 123"),
    "numfStIDNr": _Q((
        "What is your tax identification number (11 digits)?",
        "Wie lautet Ihre steuerliche Identifikationsnummer (11 Ziffern)?",
        "Quel est votre numéro d'identification fiscale (11 chiffres) ?",
        "ما رقم التعريف الضريبي الخاص بك (11 رقمًا)؟",
        "Vergi kimlik numaranız nedir (11 hane)?",
        "Cili është numri juaj i identifikimit tatimor (11 shifra)?",
    ), ex="12345678901"),
    "rbtnBetreuer": _Q((
        "Do you have a legal guardian, an authorised representative or a custodian?",
        "Haben Sie eine gesetzliche Betreuung, eine bevollmächtigte Person oder einen Vormund?",
        "Avez-vous un tuteur légal, un mandataire ou un curateur ?",
        "هل لديك وصي قانوني أو مفوض أو ولي؟",
        "Yasal vasiniz, vekiliniz veya kayyumunuz var mı?",
        "A keni një kujdestar ligjor, përfaqësues të autorizuar ose kujdestar?",
    ), helps=(
        "If yes, attach the appointment certificate, the power of attorney or the guardian ID.",
        "Falls ja, fügen Sie die Bestellungsurkunde, Vollmacht oder den Betreuerausweis bei.",
        "Si oui, joignez l'acte de nomination, la procuration ou la carte de tuteur.",
        "إذا نعم، أرفق وثيقة التعيين أو التوكيل أو بطاقة الوصي.",
        "Evetse atama belgesini, vekâletnameyi veya vasi kimliğini ekleyin.",
        "Nëse po, bashkëngjisni aktin e emërimit, prokurën ose ID-në e kujdestarit.",
    )),

    # ── B. Nationalität ──────────────────────────────────────────────────
    "rbtnAufenthalt": _Q((
        "Do you have a valid residence permit?",
        "Haben Sie einen gültigen Aufenthaltstitel?",
        "Avez-vous un titre de séjour valide ?",
        "هل لديك تصريح إقامة ساري المفعول؟",
        "Geçerli bir oturma izniniz var mı?",
        "A keni një leje qëndrimi të vlefshme?",
    ), helps=(
        "If yes, attach the residence permit.",
        "Falls ja, fügen Sie den Aufenthaltstitel bei.",
        "Si oui, joignez le titre de séjour.",
        "إذا نعم، أرفق تصريح الإقامة.",
        "Evetse oturma iznini ekleyin.",
        "Nëse po, bashkëngjisni lejen e qëndrimit.",
    )),
    "rbtnAsylbLG": _Q((
        "Do you receive benefits under the Asylum Seekers Benefits Act (Asylbewerberleistungsgesetz)?",
        "Erhalten Sie Leistungen nach dem Asylbewerberleistungsgesetz?",
        "Recevez-vous des prestations au titre de la loi sur les prestations pour demandeurs d'asile ?",
        "هل تتلقى إعانات بموجب قانون إعانات طالبي اللجوء؟",
        "Sığınmacı Yardımları Yasası kapsamında yardım alıyor musunuz?",
        "A merrni përfitime sipas ligjit për azilkërkuesit (Asylbewerberleistungsgesetz)?",
    )),
    "dateAsylbLG": _Q((
        "Until when do you receive asylum seeker benefits?",
        "Bis wann erhalten Sie Asylbewerberleistungen?",
        "Jusqu'à quand recevez-vous ces prestations ?",
        "حتى متى تتلقى إعانات طالبي اللجوء؟",
        "Sığınmacı yardımlarını ne zamana kadar alıyorsunuz?",
        "Deri kur i merrni përfitimet e azilkërkuesit?",
    ), ex="31.12.2026", fmt="date"),
    "txtfAZRNr": _Q((
        "What is your Central Register of Foreigners number (AZR), if you have one? Write - if none.",
        "Wie lautet Ihre Ausländerzentralregisternummer (AZR), falls vorhanden? Schreiben Sie -, wenn keine.",
        "Quel est votre numéro au registre central des étrangers (AZR), le cas échéant ? Écrivez - sinon.",
        "ما رقمك في السجل المركزي للأجانب (AZR) إن وُجد؟ اكتب - إذا لا.",
        "Yabancılar Merkezi Sicil numaranız (AZR) varsa nedir? Yoksa - yazın.",
        "Cili është numri juaj në regjistrin qendror të të huajve (AZR), nëse keni? Shkruani - nëse jo.",
    ), ex="-"),
    "rbtnKostenUebernahme": _Q((
        "Has someone given a formal undertaking to cover all costs of your stay in Germany (Verpflichtungserklärung)?",
        "Hat jemand eine Verpflichtungserklärung abgegeben, alle Kosten Ihres Aufenthalts in Deutschland zu übernehmen?",
        "Quelqu'un s'est-il engagé formellement à couvrir tous les frais de votre séjour en Allemagne ?",
        "هل تعهد أحد رسميًا بتغطية جميع تكاليف إقامتك في ألمانيا؟",
        "Almanya'daki konaklamanızın tüm masraflarını karşılamayı biri resmen taahhüt etti mi?",
        "A ka marrë dikush përsipër zyrtarisht të mbulojë të gjitha shpenzimet e qëndrimit tuaj në Gjermani?",
    ), helps=(
        "If yes, attach the declaration (Verpflichtungserklärung) or other proof.",
        "Falls ja, fügen Sie die Verpflichtungserklärung oder einen anderen Nachweis bei.",
        "Si oui, joignez la déclaration ou un autre justificatif.",
        "إذا نعم، أرفق التعهد أو إثباتًا آخر.",
        "Evetse taahhütnameyi veya başka bir belgeyi ekleyin.",
        "Nëse po, bashkëngjisni deklaratën ose një dëshmi tjetër.",
    )),
    "txtfNatIDNr": _Q((
        "What is your national personal ID number from your home country, if you have one? Write - if none.",
        "Wie lautet Ihre nationale Personenidentifikationsnummer Ihres Herkunftslandes, falls vorhanden? Schreiben Sie -, wenn keine.",
        "Quel est votre numéro d'identification national de votre pays d'origine, le cas échéant ? Écrivez - sinon.",
        "ما رقم هويتك الوطنية في بلدك الأصلي إن وُجد؟ اكتب - إذا لا.",
        "Menşe ülkenizdeki ulusal kimlik numaranız varsa nedir? Yoksa - yazın.",
        "Cili është numri juaj kombëtar i identitetit nga vendi i origjinës, nëse keni? Shkruani - nëse jo.",
    ), ex="-"),

    # ── C. Antragstellung ────────────────────────────────────────────────
    L_BUEG_AB: _Q((
        "From when do you want to apply for Bürgergeld?",
        "Ab welchem Zeitpunkt möchten Sie Bürgergeld beantragen?",
        "À partir de quand voulez-vous demander le Bürgergeld ?",
        "من متى تريد طلب Bürgergeld؟",
        "Bürgergeld'i ne zamandan itibaren talep etmek istiyorsunuz?",
        "Nga kur dëshironi të aplikoni për Bürgergeld?",
    ), helps=(
        "ab sofort = from now, später = from a later date (you then give the date).",
        "ab sofort oder später (dann geben Sie das Datum an).",
        "ab sofort = dès maintenant, später = à une date ultérieure (vous indiquez alors la date).",
        "ab sofort = من الآن، später = من تاريخ لاحق (ثم تحدد التاريخ).",
        "ab sofort = hemen, später = daha sonra (sonra tarihi belirtirsiniz).",
        "ab sofort = që tani, später = nga një datë e mëvonshme (pastaj jepni datën).",
    )),
    "dateBUEGSpaeter": _Q((
        "From which later date do you want Bürgergeld?",
        "Ab welchem späteren Zeitpunkt möchten Sie Bürgergeld?",
        "À partir de quelle date ultérieure voulez-vous le Bürgergeld ?",
        "من أي تاريخ لاحق تريد Bürgergeld؟",
        "Hangi ileri tarihten itibaren Bürgergeld istiyorsunuz?",
        "Nga cila datë e mëvonshme e dëshironi Bürgergeld?",
    ), ex="01.08.2026", fmt="date"),
    "dateEinreise": _Q((
        "If you previously lived abroad, when did you enter Germany? Write - if not applicable.",
        "Falls Sie zuvor im Ausland gelebt haben: Wann sind Sie nach Deutschland eingereist? Schreiben Sie -, wenn nicht zutreffend.",
        "Si vous viviez à l'étranger : quand êtes-vous entré(e) en Allemagne ? Écrivez - sinon.",
        "إذا كنت تعيش في الخارج: متى دخلت ألمانيا؟ اكتب - إذا لم ينطبق.",
        "Daha önce yurt dışında yaşadıysanız: Almanya'ya ne zaman giriş yaptınız? Uygun değilse - yazın.",
        "Nëse keni jetuar jashtë: kur hytë në Gjermani? Shkruani - nëse jo.",
    ), ex="-", fmt="date"),

    # ── D. Aktuelle Lebenssituation ──────────────────────────────────────
    L_FAMSTAND: _Q((
        "What is your current marital status?",
        "Wie ist Ihr aktueller Familienstand?",
        "Quelle est votre situation de famille actuelle ?",
        "ما هي حالتك الاجتماعية الحالية؟",
        "Mevcut medeni durumunuz nedir?",
        "Cila është gjendja juaj aktuale civile?",
    ), helps=(
        "ledig = single, verheiratet = married, verwitwet = widowed, eingetragene Lebenspartnerschaft = registered partnership, getrennt = living apart, geschieden = divorced, aufgehoben = partnership dissolved.",
        "ledig, verheiratet, verwitwet, eingetragene Lebenspartnerschaft, getrennt lebend, geschieden oder aufgehobene Lebenspartnerschaft.",
        "ledig = célibataire, verheiratet = marié(e), verwitwet = veuf/veuve, eingetragene Lebenspartnerschaft = partenariat enregistré, getrennt = séparé(e), geschieden = divorcé(e), aufgehoben = partenariat dissous.",
        "ledig = أعزب، verheiratet = متزوج، verwitwet = أرمل، eingetragene Lebenspartnerschaft = شراكة مسجلة، getrennt = منفصل، geschieden = مطلق، aufgehoben = شراكة مُلغاة.",
        "ledig = bekâr, verheiratet = evli, verwitwet = dul, eingetragene Lebenspartnerschaft = kayıtlı birliktelik, getrennt = ayrı, geschieden = boşanmış, aufgehoben = feshedilmiş birliktelik.",
        "ledig = beqar, verheiratet = i martuar, verwitwet = i ve, eingetragene Lebenspartnerschaft = partneritet i regjistruar, getrennt = i ndarë, geschieden = i divorcuar, aufgehoben = partneritet i shfuqizuar.",
    )),
    "dateGetrennt": _Q((
        "Since when have you been living apart, divorced, or when was the partnership dissolved?",
        "Seit wann leben Sie getrennt, sind geschieden, oder wann wurde die Lebenspartnerschaft aufgehoben?",
        "Depuis quand vivez-vous séparé(e), êtes-vous divorcé(e), ou quand le partenariat a-t-il été dissous ?",
        "منذ متى تعيش منفصلاً أو مطلقًا، أو متى أُلغيت الشراكة؟",
        "Ne zamandan beri ayrı yaşıyorsunuz, boşandınız veya birliktelik ne zaman feshedildi?",
        "Që kur jetoni të ndarë, jeni i divorcuar, ose kur u shfuqizua partneriteti?",
    ), ex="01.01.2025", fmt="date"),
    "rtbnErwerbsfaehig": _Q((
        "Are you able to work? This means you can generally work at least 3 hours a day for health reasons.",
        "Sind Sie erwerbsfähig? Das heißt, Sie können gesundheitlich grundsätzlich mindestens 3 Stunden täglich arbeiten.",
        "Êtes-vous apte à travailler ? Cela signifie pouvoir travailler au moins 3 heures par jour pour des raisons de santé.",
        "هل أنت قادر على العمل؟ أي أنك صحيًا قادر على العمل 3 ساعات يوميًا على الأقل.",
        "Çalışabilir misiniz? Yani sağlık açısından günde en az 3 saat çalışabilirsiniz.",
        "A jeni i aftë për punë? Domethënë mund të punoni të paktën 3 orë në ditë për arsye shëndetësore.",
    )),
    "rbtnAlleinerziehend": _Q((
        "Are you a single parent?", "Sind Sie alleinerziehend?", "Êtes-vous parent isolé ?",
        "هل أنت معيل وحيد؟", "Tek ebeveyn misiniz?", "A jeni prind i vetëm?",
    )),
    "rbtnSchwanger": _Q((
        "Are you pregnant?", "Sind Sie schwanger?", "Êtes-vous enceinte ?",
        "هل أنتِ حامل؟", "Hamile misiniz?", "A jeni shtatzënë?",
    )),
    "dateEntbindung": _Q((
        "What is the expected delivery date?", "Wann ist der voraussichtliche Entbindungstermin?",
        "Quelle est la date prévue de l'accouchement ?", "ما هو تاريخ الولادة المتوقع؟",
        "Tahmini doğum tarihi nedir?", "Cila është data e pritshme e lindjes?",
    ), ex="01.11.2026", fmt="date"),
    "rbtnElternAusserhalb": _Q((
        "Are you under 25 and does at least one parent live outside your benefit household (Bedarfsgemeinschaft)?",
        "Sind Sie unter 25 und lebt mindestens ein Elternteil außerhalb der Bedarfsgemeinschaft?",
        "Avez-vous moins de 25 ans et au moins un parent vit-il hors de votre foyer de prestations ?",
        "هل عمرك أقل من 25 ويعيش أحد الوالدين على الأقل خارج وحدة الاحتياج؟",
        "25 yaşın altında mısınız ve en az bir ebeveyniniz yardım hanenizin dışında mı yaşıyor?",
        "A jeni nën 25 vjeç dhe a jeton të paktën një prind jashtë njësisë suaj të përfitimeve?",
    ), helps=(
        "If yes, also fill in the Anlage UH3.",
        "Falls ja, füllen Sie auch die Anlage UH3 aus.",
        "Si oui, remplissez aussi l'annexe UH3.",
        "إذا نعم، املأ أيضًا ملحق UH3.",
        "Evetse Anlage UH3'ü de doldurun.",
        "Nëse po, plotësoni edhe Anlage UH3.",
    )),
    "rbtnSchueler": _Q((
        "Are you a school pupil, a student, or an apprentice/trainee?",
        "Sind Sie Schülerin/Schüler, Studentin/Student oder Auszubildende/r?",
        "Êtes-vous élève, étudiant(e) ou apprenti(e) ?",
        "هل أنت تلميذ أو طالب جامعي أو متدرب؟",
        "Öğrenci, üniversite öğrencisi veya çırak/stajyer misiniz?",
        "A jeni nxënës, student ose praktikant?",
    ), helps=(
        "If yes, attach proof (e.g. enrolment certificate).",
        "Falls ja, fügen Sie Nachweise bei (z. B. Schulbescheinigung).",
        "Si oui, joignez un justificatif (par ex. certificat de scolarité).",
        "إذا نعم، أرفق إثباتًا (مثل شهادة قيد).",
        "Evetse belge ekleyin (örn. öğrenci belgesi).",
        "Nëse po, bashkëngjisni dëshmi (p.sh. vërtetim regjistrimi).",
    )),
    "rbtnKostenBuecher": _Q((
        "Do you have costs for school books or workbooks?",
        "Fallen Kosten für Schulbücher oder Arbeitshefte an?",
        "Avez-vous des frais de manuels scolaires ou de cahiers ?",
        "هل لديك تكاليف للكتب المدرسية أو دفاتر التمارين؟",
        "Okul kitapları veya çalışma kitapları için masrafınız var mı?",
        "A keni shpenzime për libra shkollorë ose fletore pune?",
    )),
    "rbtnAusbildungUneterkunft": _Q((
        "During your training, are you housed away from home?",
        "Sind Sie während der Ausbildung auswärts untergebracht?",
        "Pendant votre formation, êtes-vous logé(e) ailleurs qu'à votre domicile ?",
        "أثناء التدريب، هل تقيم خارج المنزل؟",
        "Eğitiminiz sırasında dışarıda mı kalıyorsunuz?",
        "Gjatë formimit, a jeni i strehuar jashtë shtëpisë?",
    )),

    # ── Other benefits (Q42-43) ──────────────────────────────────────────
    "rbtnLeistungAndere": _Q((
        "Have you applied for, or do you intend to apply for, other benefits?",
        "Haben Sie schon andere Leistungen beantragt oder beabsichtigen Sie, welche zu beantragen?",
        "Avez-vous demandé ou comptez-vous demander d'autres prestations ?",
        "هل طلبت أو تنوي طلب إعانات أخرى؟",
        "Başka yardımlar için başvurdunuz mu veya başvurmayı düşünüyor musunuz?",
        "A keni aplikuar ose keni ndërmend të aplikoni për përfitime të tjera?",
    )),
    "chbxLeistungBafoeg": _Q((
        "Have you applied for BAföG (study/training grant)?",
        "Haben Sie BAföG beantragt?",
        "Avez-vous demandé le BAföG ?",
        "هل طلبت BAföG؟", "BAföG için başvurdunuz mu?", "A keni aplikuar për BAföG?",
    )),
    "chbxLeistungBAB": _Q((
        "Have you applied for vocational training assistance (BAB)?",
        "Haben Sie Berufsausbildungsbeihilfe (BAB) beantragt?",
        "Avez-vous demandé l'aide à la formation professionnelle (BAB) ?",
        "هل طلبت مساعدة التدريب المهني (BAB)؟", "Mesleki eğitim yardımı (BAB) için başvurdunuz mu?",
        "A keni aplikuar për ndihmë formimi profesional (BAB)?",
    )),
    "chbxLeistungWohngeld": _Q((
        "Have you applied for housing benefit (Wohngeld)?",
        "Haben Sie Wohngeld beantragt?", "Avez-vous demandé l'allocation logement (Wohngeld) ?",
        "هل طلبت بدل السكن (Wohngeld)؟", "Konut yardımı (Wohngeld) için başvurdunuz mu?",
        "A keni aplikuar për Wohngeld?",
    )),
    "chbxLeistungArbeitslosengeld": _Q((
        "Have you applied for unemployment benefit (Arbeitslosengeld)?",
        "Haben Sie Arbeitslosengeld beantragt?", "Avez-vous demandé l'allocation chômage ?",
        "هل طلبت إعانة البطالة؟", "İşsizlik ödeneği için başvurdunuz mu?",
        "A keni aplikuar për pagesë papunësie?",
    )),
    "chbxLeistungRente": _Q((
        "Have you applied for a pension (Rente)?",
        "Haben Sie Rente beantragt?", "Avez-vous demandé une pension (Rente) ?",
        "هل طلبت معاشًا تقاعديًا؟", "Emekli maaşı için başvurdunuz mu?",
        "A keni aplikuar për pension?",
    )),
    "chbxLeistungKRG": _Q((
        "Have you applied for sickness benefit (Krankengeld)?",
        "Haben Sie Krankengeld beantragt?", "Avez-vous demandé des indemnités de maladie ?",
        "هل طلبت بدل المرض؟", "Hastalık ödeneği için başvurdunuz mu?",
        "A keni aplikuar për pagesë sëmundjeje?",
    )),
    "chbxLeistungKG": _Q((
        "Have you applied for child benefit (Kindergeld)?",
        "Haben Sie Kindergeld beantragt?", "Avez-vous demandé le Kindergeld ?",
        "هل طلبت Kindergeld؟", "Kindergeld için başvurdunuz mu?",
        "A keni aplikuar për Kindergeld?",
    )),
    "chbxLeistungKIZ": _Q((
        "Have you applied for the child supplement (Kinderzuschlag)?",
        "Haben Sie Kinderzuschlag beantragt?", "Avez-vous demandé le Kinderzuschlag ?",
        "هل طلبت Kinderzuschlag؟", "Kinderzuschlag için başvurdunuz mu?",
        "A keni aplikuar për Kinderzuschlag?",
    )),
    "chbxLeistungSonstiges": _Q((
        "Have you applied for any other benefits?",
        "Haben Sie sonstige Leistungen beantragt?", "Avez-vous demandé d'autres prestations ?",
        "هل طلبت إعانات أخرى؟", "Başka yardımlar için başvurdunuz mu?",
        "A keni aplikuar për përfitime të tjera?",
    )),
    "txtfLeistungSonstiges": _Q((
        "Which other benefits did you apply for?",
        "Welche sonstigen Leistungen haben Sie beantragt?",
        "Quelles autres prestations avez-vous demandées ?",
        "ما الإعانات الأخرى التي طلبتها؟", "Hangi diğer yardımlara başvurdunuz?",
        "Për cilat përfitime të tjera keni aplikuar?",
    )),
    "rbtnMEB": _Q((
        "Do you need a costly special diet for medical reasons?",
        "Benötigen Sie aus medizinischen Gründen eine kostenaufwändige Ernährung?",
        "Avez-vous besoin, pour raisons médicales, d'une alimentation coûteuse ?",
        "هل تحتاج لأسباب طبية إلى تغذية مكلفة؟",
        "Tıbbi nedenlerle masraflı bir beslenmeye ihtiyacınız var mı?",
        "A keni nevojë për arsye mjekësore për një ushqim të kushtueshëm?",
    ), helps=(
        "If yes, also fill in the Anlage MEB.",
        "Falls ja, füllen Sie auch die Anlage MEB aus.",
        "Si oui, remplissez aussi l'annexe MEB.",
        "إذا نعم، املأ أيضًا ملحق MEB.",
        "Evetse Anlage MEB'i de doldurun.",
        "Nëse po, plotësoni edhe Anlage MEB.",
    )),
    "rbtnBehinderung": _Q((
        "Do you have a disability?", "Haben Sie eine Behinderung?", "Avez-vous un handicap ?",
        "هل لديك إعاقة؟", "Engeliniz var mı?", "A keni një aftësi të kufizuar?",
    )),
    "rbtnLeistungTeilhabe": _Q((
        "Do you receive benefits for participation in working life (SGB IX) or other job-integration support?",
        "Erhalten Sie Leistungen zur Teilhabe am Arbeitsleben (SGB IX) oder sonstige Eingliederungshilfen?",
        "Recevez-vous des prestations de participation à la vie professionnelle (SGB IX) ou d'autres aides à l'insertion ?",
        "هل تتلقى إعانات للمشاركة في الحياة العملية (SGB IX) أو مساعدات إدماج أخرى؟",
        "Çalışma yaşamına katılım (SGB IX) yardımları veya başka entegrasyon yardımları alıyor musunuz?",
        "A merrni përfitime për pjesëmarrje në jetën e punës (SGB IX) ose ndihma të tjera integrimi?",
    ), helps=(
        "If yes, attach the decision letter (Bescheid).",
        "Falls ja, fügen Sie den Bescheid bei.",
        "Si oui, joignez la notification (Bescheid).",
        "إذا نعم، أرفق خطاب القرار (Bescheid).",
        "Evetse karar yazısını (Bescheid) ekleyin.",
        "Nëse po, bashkëngjisni vendimin (Bescheid).",
    )),
    "rbtnBB": _Q((
        "Do you have an unavoidable special need you cannot cover by savings or otherwise (e.g. costs of contact rights with a child living apart)?",
        "Haben Sie einen unabweisbaren besonderen Bedarf, den Sie nicht durch Einsparungen abdecken können (z. B. Kosten zur Wahrnehmung des Umgangsrechts)?",
        "Avez-vous un besoin particulier inévitable que vous ne pouvez pas couvrir (par ex. frais de droit de visite) ?",
        "هل لديك حاجة خاصة لا مفر منها لا يمكنك تغطيتها (مثل تكاليف حق الزيارة)؟",
        "Tasarrufla karşılayamadığınız kaçınılmaz özel bir ihtiyacınız var mı (örn. çocukla görüşme hakkı masrafları)?",
        "A keni një nevojë të veçantë të pashmangshme që nuk e mbuloni dot (p.sh. shpenzime për të drejtën e kontaktit me fëmijën)?",
    ), helps=(
        "If yes, also fill in the Anlage BB.",
        "Falls ja, füllen Sie auch die Anlage BB aus.",
        "Si oui, remplissez aussi l'annexe BB.",
        "إذا نعم، املأ أيضًا ملحق BB.",
        "Evetse Anlage BB'yi de doldurun.",
        "Nëse po, plotësoni edhe Anlage BB.",
    )),
    "rbtnStationaer": _Q((
        "Are you now, or will you soon be, in a residential institution (e.g. hospital, care home, prison)?",
        "Befinden Sie sich derzeit oder demnächst in einer stationären Einrichtung (z. B. Krankenhaus, Altenheim, Justizvollzugsanstalt)?",
        "Êtes-vous actuellement ou bientôt dans un établissement (par ex. hôpital, maison de retraite, prison) ?",
        "هل أنت حاليًا أو قريبًا في مؤسسة إقامة (مثل مستشفى، دار مسنين، سجن)؟",
        "Şu anda veya yakında yatılı bir kurumda mısınız (örn. hastane, huzurevi, cezaevi)?",
        "A ndodheni tani ose së shpejti në një institucion me qëndrim (p.sh. spital, shtëpi pleqsh, burg)?",
    )),
    "txtfStationaerArt": _Q((
        "What type of residential institution is it?",
        "Um welche Art von stationärer Einrichtung handelt es sich?",
        "De quel type d'établissement s'agit-il ?",
        "ما نوع المؤسسة؟", "Hangi tür kurum?", "Çfarë lloj institucioni është?",
    ), ex=("Hospital", "Krankenhaus", "Hôpital", "مستشفى", "Hastane", "Spital")),
    "dateStationaerVon": _Q((
        "From when is the stay?", "Ab wann dauert der Aufenthalt?", "À partir de quand dure le séjour ?",
        "من متى تبدأ الإقامة؟", "Kalış ne zaman başlıyor?", "Nga kur është qëndrimi?",
    ), ex="01.07.2026", fmt="date"),
    "dateStationaerBis": _Q((
        "Until when is the stay (expected)?", "Bis wann dauert der Aufenthalt (voraussichtlich)?",
        "Jusqu'à quand (prévu) ?", "حتى متى (المتوقع)؟", "Ne zamana kadar (tahmini)?",
        "Deri kur (e pritshme)?",
    ), ex="31.08.2026", fmt="date"),

    # ── E. Bisherige Lebenssituation ─────────────────────────────────────
    "rbtnBUEG": _Q((
        "In the last 3 years, have you already applied for or received Bürgergeld or social assistance?",
        "Haben Sie in den letzten 3 Jahren bereits Bürgergeld oder Sozialhilfe beantragt oder bezogen?",
        "Au cours des 3 dernières années, avez-vous déjà demandé ou reçu le Bürgergeld ou l'aide sociale ?",
        "خلال السنوات الثلاث الماضية، هل سبق أن طلبت أو تلقيت Bürgergeld أو مساعدة اجتماعية؟",
        "Son 3 yılda Bürgergeld veya sosyal yardım için başvurdunuz mu veya aldınız mı?",
        "Në 3 vitet e fundit, a keni aplikuar ose marrë Bürgergeld ose ndihmë sociale?",
    )),
    "txtfLeistungArt": _Q((
        "What type of benefit was it?", "Um welche Art von Leistung handelte es sich?",
        "De quel type de prestation s'agissait-il ?", "ما نوع الإعانة؟",
        "Hangi tür yardımdı?", "Çfarë lloj përfitimi ishte?",
    ), ex=("Bürgergeld", "Bürgergeld", "Bürgergeld", "Bürgergeld", "Bürgergeld", "Bürgergeld")),
    "dateLeistungVon": _Q((
        "From when did you receive the benefit?", "Ab wann erhielten Sie die Leistung?",
        "À partir de quand avez-vous reçu la prestation ?", "من متى تلقيت الإعانة؟",
        "Yardımı ne zamandan itibaren aldınız?", "Nga kur e morët përfitimin?",
    ), ex="01.2023", fmt="date"),
    "dateLeistungBis": _Q((
        "Until when did you receive the benefit?", "Bis wann erhielten Sie die Leistung?",
        "Jusqu'à quand avez-vous reçu la prestation ?", "حتى متى تلقيت الإعانة؟",
        "Yardımı ne zamana kadar aldınız?", "Deri kur e morët përfitimin?",
    ), ex="12.2023", fmt="date"),
    "txtfTraegerName": _Q((
        "What is the name of the benefit provider (e.g. the Jobcenter or Sozialamt)?",
        "Wie heißt der Leistungsträger (z. B. das Jobcenter oder Sozialamt)?",
        "Quel est le nom de l'organisme prestataire (par ex. le Jobcenter) ?",
        "ما اسم جهة الإعانة (مثل Jobcenter)؟", "Yardım kurumunun adı nedir (örn. Jobcenter)?",
        "Cili është emri i institucionit (p.sh. Jobcenter)?",
    )),
    "txtfTraegerStr": _Q((
        "What is the street of the benefit provider?", "Wie lautet die Straße des Leistungsträgers?",
        "Quelle est la rue de l'organisme ?", "ما شارع جهة الإعانة؟",
        "Yardım kurumunun sokağı nedir?", "Cila është rruga e institucionit?",
    )),
    "txtfTraegerHausNr": _Q((
        "What is the house number of the benefit provider?", "Wie lautet die Hausnummer des Leistungsträgers?",
        "Quel est le numéro de l'organisme ?", "ما رقم منزل جهة الإعانة؟",
        "Yardım kurumunun kapı numarası nedir?", "Cili është numri i institucionit?",
    )),
    "txtfTraegerPlz": _Q((
        "What is the postal code of the benefit provider?", "Wie lautet die Postleitzahl des Leistungsträgers?",
        "Quel est le code postal de l'organisme ?", "ما الرمز البريدي لجهة الإعانة؟",
        "Yardım kurumunun posta kodu nedir?", "Cili është kodi postar i institucionit?",
    )),
    "txtfTraegerOrt": _Q((
        "What is the town of the benefit provider?", "Wie lautet der Ort des Leistungsträgers?",
        "Quelle est la ville de l'organisme ?", "ما مدينة جهة الإعانة؟",
        "Yardım kurumunun şehri nedir?", "Cili është qyteti i institucionit?",
    )),
    "rbtnAngestellt": _Q((
        "In the last 5 years, were you employed by an employer?",
        "Waren Sie in den letzten 5 Jahren bei einer Arbeitgeberin/einem Arbeitgeber angestellt oder beschäftigt?",
        "Au cours des 5 dernières années, avez-vous été salarié(e) chez un employeur ?",
        "خلال السنوات الخمس الماضية، هل عملت لدى صاحب عمل؟",
        "Son 5 yılda bir işverende çalıştınız mı?",
        "Në 5 vitet e fundit, a keni qenë i punësuar te një punëdhënës?",
    )),
    "dateBeschaeftigtVon": _Q((
        "From when was the employment?", "Ab wann dauerte die Beschäftigung?",
        "À partir de quand a duré l'emploi ?", "من متى بدأ العمل؟",
        "İş ne zaman başladı?", "Nga kur ishte punësimi?",
    ), ex="01.2022", fmt="date"),
    "dateBeschaeftigtBis": _Q((
        "Until when was the employment?", "Bis wann dauerte die Beschäftigung?",
        "Jusqu'à quand a duré l'emploi ?", "حتى متى استمر العمل؟",
        "İş ne zamana kadar sürdü?", "Deri kur ishte punësimi?",
    ), ex="12.2023", fmt="date"),
    "dateBeschaeftigt2Von": _Q((
        "If there was a second job, from when? Write - if not.",
        "Falls es eine zweite Beschäftigung gab: ab wann? Schreiben Sie -, wenn nicht.",
        "S'il y a eu un second emploi : à partir de quand ? Écrivez - sinon.",
        "إذا كان هناك عمل ثانٍ: من متى؟ اكتب - إذا لا.",
        "İkinci bir iş varsa: ne zamandan? Yoksa - yazın.",
        "Nëse kishte një punë të dytë: nga kur? Shkruani - nëse jo.",
    ), ex="-", fmt="date"),
    "dateBeschaeftigt2Bis": _Q((
        "If there was a second job, until when? Write - if not.",
        "Falls es eine zweite Beschäftigung gab: bis wann? Schreiben Sie -, wenn nicht.",
        "S'il y a eu un second emploi : jusqu'à quand ? Écrivez - sinon.",
        "إذا كان هناك عمل ثانٍ: حتى متى؟ اكتب - إذا لا.",
        "İkinci bir iş varsa: ne zamana kadar? Yoksa - yazın.",
        "Nëse kishte një punë të dytë: deri kur? Shkruani - nëse jo.",
    ), ex="-", fmt="date"),
    "rbtnLohnanspruch": _Q((
        "Do you have outstanding wage claims against a (former) employer?",
        "Haben Sie ausstehende Lohnansprüche gegen eine (ehemalige) Arbeitgeberin/einen (ehemaligen) Arbeitgeber?",
        "Avez-vous des créances salariales impayées envers un (ancien) employeur ?",
        "هل لديك مستحقات أجور غير مدفوعة لدى صاحب عمل (سابق)؟",
        "(Eski) bir işverene karşı ödenmemiş ücret alacaklarınız var mı?",
        "A keni paga të papaguara nga një punëdhënës (i mëparshëm)?",
    )),
    "txtfAGName": _Q((
        "What is the employer's name?", "Wie heißt die Arbeitgeberin / der Arbeitgeber?",
        "Quel est le nom de l'employeur ?", "ما اسم صاحب العمل؟",
        "İşverenin adı nedir?", "Cili është emri i punëdhënësit?",
    )),
    "txtfAGStr": _Q((
        "What is the employer's street?", "Wie lautet die Straße der Arbeitgeberin/des Arbeitgebers?",
        "Quelle est la rue de l'employeur ?", "ما شارع صاحب العمل؟",
        "İşverenin sokağı nedir?", "Cila është rruga e punëdhënësit?",
    )),
    "txtfAGHausNr": _Q((
        "What is the employer's house number?", "Wie lautet die Hausnummer der Arbeitgeberin/des Arbeitgebers?",
        "Quel est le numéro de l'employeur ?", "ما رقم منزل صاحب العمل؟",
        "İşverenin kapı numarası nedir?", "Cili është numri i punëdhënësit?",
    )),
    "txtfAGPlz": _Q((
        "What is the employer's postal code?", "Wie lautet die Postleitzahl der Arbeitgeberin/des Arbeitgebers?",
        "Quel est le code postal de l'employeur ?", "ما الرمز البريدي لصاحب العمل؟",
        "İşverenin posta kodu nedir?", "Cili është kodi postar i punëdhënësit?",
    )),
    "txtfAGOrt": _Q((
        "What is the employer's town?", "Wie lautet der Ort der Arbeitgeberin/des Arbeitgebers?",
        "Quelle est la ville de l'employeur ?", "ما مدينة صاحب العمل؟",
        "İşverenin şehri nedir?", "Cili është qyteti i punëdhënësit?",
    )),
    "rbtnSelbstaendig": _Q((
        "In the last 5 years, were you self-employed or a freelancer?",
        "Waren Sie in den letzten 5 Jahren selbständig oder freiberuflich tätig?",
        "Au cours des 5 dernières années, avez-vous été indépendant(e) ou freelance ?",
        "خلال السنوات الخمس الماضية، هل عملت لحسابك الخاص أو كمستقل؟",
        "Son 5 yılda serbest meslek sahibi veya freelance miydiniz?",
        "Në 5 vitet e fundit, a keni qenë i vetëpunësuar ose i pavarur?",
    )),
    "rbtnEntgeltersatz": _Q((
        "Did you receive wage-replacement benefits (e.g. sickness benefit, unemployment benefit, parental allowance)?",
        "Haben Sie Entgeltersatzleistungen erhalten (z. B. Krankengeld, Arbeitslosengeld, Elterngeld)?",
        "Avez-vous reçu des prestations de remplacement de revenu (par ex. indemnités maladie, chômage, allocation parentale) ?",
        "هل تلقيت إعانات بديلة عن الأجر (مثل بدل المرض، إعانة البطالة، علاوة الوالدين)؟",
        "Ücret yerine geçen ödenekler aldınız mı (örn. hastalık ödeneği, işsizlik ödeneği, ebeveyn ödeneği)?",
        "A keni marrë përfitime zëvendësuese të pagës (p.sh. pagesë sëmundjeje, papunësie, prindërore)?",
    )),
    "txtfEntgeltersatz": _Q((
        "Which wage-replacement benefit was it?",
        "Welche Entgeltersatzleistung war es?",
        "De quelle prestation s'agissait-il ?",
        "ما الإعانة البديلة عن الأجر؟", "Hangi ödenekti?", "Cili përfitim ishte?",
    )),
    "dateEntgeltersatzVon": _Q((
        "From when did you receive it?", "Ab wann erhielten Sie sie?", "À partir de quand l'avez-vous reçue ?",
        "من متى تلقيتها؟", "Ne zamandan aldınız?", "Nga kur e morët?",
    ), ex="01.2024", fmt="date"),
    "dateEntgeltersatzBis": _Q((
        "Until when did you receive it?", "Bis wann erhielten Sie sie?", "Jusqu'à quand l'avez-vous reçue ?",
        "حتى متى تلقيتها؟", "Ne zamana kadar aldınız?", "Deri kur e morët?",
    ), ex="06.2024", fmt="date"),

    # ── (page 6) ─────────────────────────────────────────────────────────
    "rbtnWehrdienst": _Q((
        "Did you do military service or a voluntary service (e.g. FSJ, federal volunteer service)?",
        "Haben Sie Wehrdienst oder einen freiwilligen Dienst geleistet (z. B. FSJ, Bundesfreiwilligendienst)?",
        "Avez-vous fait un service militaire ou volontaire (par ex. FSJ, service civique fédéral) ?",
        "هل أديت خدمة عسكرية أو تطوعية (مثل FSJ، الخدمة التطوعية الاتحادية)؟",
        "Askerlik veya gönüllü hizmet yaptınız mı (örn. FSJ, federal gönüllü hizmet)?",
        "A keni kryer shërbim ushtarak ose vullnetar (p.sh. FSJ, shërbim vullnetar federal)?",
    )),
    "rbtnPflege": _Q((
        "Did you care for relatives (care under SGB XI)?",
        "Haben Sie Angehörige gepflegt (Pflege nach dem SGB XI)?",
        "Avez-vous pris soin de proches (soins selon le SGB XI) ?",
        "هل اعتنيت بأقارب (رعاية وفق SGB XI)؟",
        "Yakınlarınıza baktınız mı (SGB XI kapsamında bakım)?",
        "A keni kujdesur për të afërm (kujdes sipas SGB XI)?",
    )),
    "txtareaLebensunterhalt": _Q((
        "If none of the above applied in the last 5 years, how did you support yourself (e.g. help from relatives, savings, inheritance)? Write - if not applicable.",
        "Wenn nichts davon in den letzten 5 Jahren zutraf: Wie haben Sie Ihren Lebensunterhalt bestritten (z. B. Unterstützung durch Verwandte, Ersparnisse, Erbschaft)? Schreiben Sie -, wenn nicht zutreffend.",
        "Si rien de ce qui précède ne s'applique : comment avez-vous subvenu à vos besoins (aide de proches, économies, héritage) ? Écrivez - sinon.",
        "إذا لم ينطبق ما سبق: كيف أعلت نفسك (مثل دعم الأقارب، مدخرات، إرث)؟ اكتب - إذا لم ينطبق.",
        "Yukarıdakiler geçerli değilse: geçiminizi nasıl sağladınız (örn. akraba yardımı, birikim, miras)? Uygun değilse - yazın.",
        "Nëse asgjë e mësipërme nuk vlen: si e siguruat jetesën (p.sh. ndihmë nga të afërmit, kursime, trashëgimi)? Shkruani - nëse jo.",
    ), ex="-"),
    "rbtnAnspruchDritte": _Q((
        "Do you have a claim against a third party (e.g. compensation, inheritance)?",
        "Haben Sie einen Anspruch gegenüber Dritten (z. B. Schadensersatz, Erbschaft)?",
        "Avez-vous une créance envers un tiers (par ex. dommages-intérêts, héritage) ?",
        "هل لديك مطالبة تجاه طرف ثالث (مثل تعويض، إرث)؟",
        "Üçüncü bir tarafa karşı alacağınız var mı (örn. tazminat, miras)?",
        "A keni një kërkesë ndaj një pale të tretë (p.sh. dëmshpërblim, trashëgimi)?",
    ), helps=(
        "If yes, attach proof of the claim.",
        "Falls ja, fügen Sie einen Nachweis über den Anspruch bei.",
        "Si oui, joignez un justificatif de la créance.",
        "إذا نعم، أرفق إثباتًا للمطالبة.",
        "Evetse alacağın belgesini ekleyin.",
        "Nëse po, bashkëngjisni dëshmi të kërkesës.",
    )),
    "rbtnSchadenDritte": _Q((
        "Did you suffer an accident or health damage caused by a third party?",
        "Haben Sie einen Unfall oder gesundheitlichen Schaden durch einen Dritten erlitten?",
        "Avez-vous subi un accident ou un dommage corporel causé par un tiers ?",
        "هل تعرضت لحادث أو ضرر صحي بسبب طرف ثالث؟",
        "Üçüncü bir tarafın neden olduğu kaza veya sağlık zararı yaşadınız mı?",
        "A keni pësuar aksident ose dëm shëndetësor nga një palë e tretë?",
    ), helps=(
        "If yes, also fill in the Anlage UF.",
        "Falls ja, füllen Sie auch die Anlage UF aus.",
        "Si oui, remplissez aussi l'annexe UF.",
        "إذا نعم، املأ أيضًا ملحق UF.",
        "Evetse Anlage UF'yi de doldurun.",
        "Nëse po, plotësoni edhe Anlage UF.",
    )),
    "rbtnKVPV": _Q((
        "Are you, or were you most recently, in the statutory health and care insurance (family or compulsory insured)?",
        "Sind oder waren Sie zuletzt in der gesetzlichen Kranken- und Pflegeversicherung familien- oder pflichtversichert?",
        "Êtes-vous (ou étiez-vous récemment) assuré(e) maladie/dépendance légale (assurance familiale ou obligatoire) ?",
        "هل أنت (أو كنت مؤخرًا) في التأمين الصحي/الرعاية القانوني (تأمين عائلي أو إجباري)؟",
        "Yasal sağlık/bakım sigortasında (aile veya zorunlu sigortalı) mısınız veya son olarak mıydınız?",
        "A jeni (ose ishit së fundmi) në sigurimin ligjor shëndetësor/kujdesit (familjar ose i detyrueshëm)?",
    )),
    "txtfKV": _Q((
        "Which health insurance fund are you (or want to be) insured with?",
        "Bei welcher Krankenkasse sind oder möchten Sie versichert werden?",
        "Auprès de quelle caisse d'assurance maladie êtes-vous (ou souhaitez-vous être) assuré(e) ?",
        "في أي صندوق تأمين صحي أنت (أو تريد أن تكون) مؤمَّنًا؟",
        "Hangi hastalık sigortası kasasında sigortalısınız (veya olmak istiyorsunuz)?",
        "Në cilën kasë sigurimi shëndetësor jeni (ose dëshironi të jeni) i siguruar?",
    ), helps=(
        "Give the name of the health insurance fund and attach a current proof of insurance.",
        "Geben Sie den Namen der Krankenkasse an und fügen Sie einen aktuellen Nachweis bei.",
        "Indiquez le nom de la caisse et joignez un justificatif d'assurance actuel.",
        "اذكر اسم صندوق التأمين وأرفق إثباتًا حديثًا.",
        "Sağlık kasasının adını verin ve güncel bir sigorta belgesi ekleyin.",
        "Jepni emrin e kasës dhe bashkëngjisni një dëshmi aktuale sigurimi.",
    ), ex="AOK"),
    "rbtnPKV": _Q((
        "Are you privately insured, voluntarily insured under the statutory scheme, or not insured?",
        "Sind Sie privat versichert, freiwillig gesetzlich versichert oder nicht versichert?",
        "Êtes-vous assuré(e) en privé, en assurance légale volontaire, ou non assuré(e) ?",
        "هل أنت مؤمَّن خاصًا أو طوعيًا قانونيًا أو غير مؤمَّن؟",
        "Özel sigortalı, isteğe bağlı yasal sigortalı mı yoksa sigortasız mısınız?",
        "A jeni i siguruar privat, vullnetar sipas skemës ligjore, ose i pasiguruar?",
    ), helps=(
        "If yes, also fill in the Anlage SV.",
        "Falls ja, füllen Sie auch die Anlage SV aus.",
        "Si oui, remplissez aussi l'annexe SV.",
        "إذا نعم، املأ أيضًا ملحق SV.",
        "Evetse Anlage SV'yi de doldurun.",
        "Nëse po, plotësoni edhe Anlage SV.",
    )),

    # ── G. Wohnsituation ─────────────────────────────────────────────────
    "rbtnWohnsituation": _Q((
        "Do you live alone?", "Wohnen Sie allein?", "Vivez-vous seul(e) ?",
        "هل تعيش بمفردك؟", "Yalnız mı yaşıyorsunuz?", "A jetoni vetëm?",
    )),
    "chbxWohnenEhegatte": _Q((
        "Do you live with a spouse, registered partner, or a partner in a marriage-like relationship?",
        "Wohnen Sie mit Ehegatte/in, eingetragener Partner/in oder Partner/in (eheähnliche Gemeinschaft) zusammen?",
        "Vivez-vous avec un(e) conjoint(e), partenaire enregistré(e) ou partenaire (union de fait) ?",
        "هل تعيش مع زوج/شريك مسجل/شريك (علاقة شبيهة بالزواج)؟",
        "Eş, kayıtlı partner veya partnerle (evlilik benzeri) mi yaşıyorsunuz?",
        "A jetoni me bashkëshort, partner të regjistruar ose partner (bashkësi si martesë)?",
    ), helps=(
        "If yes, also fill in the Anlage WEP.",
        "Falls ja, füllen Sie auch die Anlage WEP aus.",
        "Si oui, remplissez aussi l'annexe WEP.",
        "إذا نعم، املأ أيضًا ملحق WEP.",
        "Evetse Anlage WEP'i de doldurun.",
        "Nëse po, plotësoni edhe Anlage WEP.",
    )),
    "chbxWohnenKind": _Q((
        "Do unmarried children aged between 15 and 24 live with you?",
        "Wohnen unverheiratete Kinder zwischen 15 und 24 Jahren bei Ihnen?",
        "Des enfants non mariés de 15 à 24 ans vivent-ils avec vous ?",
        "هل يعيش معك أطفال غير متزوجين بين 15 و24 عامًا؟",
        "Sizinle 15-24 yaş arası evli olmayan çocuklar mı yaşıyor?",
        "A jetojnë me ju fëmijë të pamartuar 15-24 vjeç?",
    ), helps=(
        "If yes, also fill in an Anlage WEP for each such child.",
        "Falls ja, füllen Sie für jedes solche Kind eine Anlage WEP aus.",
        "Si oui, remplissez une annexe WEP pour chaque enfant concerné.",
        "إذا نعم، املأ ملحق WEP لكل طفل من هؤلاء.",
        "Evetse her böyle çocuk için bir Anlage WEP doldurun.",
        "Nëse po, plotësoni një Anlage WEP për secilin fëmijë.",
    )),
    "chbxWohnenKindU15": _Q((
        "Do children under 15 live with you?",
        "Wohnen Kinder unter 15 Jahren bei Ihnen?",
        "Des enfants de moins de 15 ans vivent-ils avec vous ?",
        "هل يعيش معك أطفال دون 15 عامًا؟",
        "Sizinle 15 yaşın altında çocuklar mı yaşıyor?",
        "A jetojnë me ju fëmijë nën 15 vjeç?",
    ), helps=(
        "If yes, also fill in an Anlage KI for each such child.",
        "Falls ja, füllen Sie für jedes solche Kind eine Anlage KI aus.",
        "Si oui, remplissez une annexe KI pour chaque enfant concerné.",
        "إذا نعم، املأ ملحق KI لكل طفل من هؤلاء.",
        "Evetse her böyle çocuk için bir Anlage KI doldurun.",
        "Nëse po, plotësoni një Anlage KI për secilin fëmijë.",
    )),
    "chbxWohnenEltern": _Q((
        "Do you live with your parents or one parent?",
        "Wohnen Sie mit Ihren Eltern oder einem Elternteil zusammen?",
        "Vivez-vous avec vos parents ou l'un d'eux ?",
        "هل تعيش مع والديك أو أحدهما؟",
        "Ebeveynlerinizle veya bir ebeveyninizle mi yaşıyorsunuz?",
        "A jetoni me prindërit ose me një prind?",
    )),
    "chbxWohnenVerwandte": _Q((
        "Do you live with other relatives or in-laws (e.g. grandparents, siblings over 25, married children, aunts/uncles)?",
        "Wohnen Sie mit sonstigen Verwandten oder Verschwägerten zusammen (z. B. Großeltern, Geschwister über 25, verheiratete Kinder, Tanten/Onkel)?",
        "Vivez-vous avec d'autres parents ou alliés (par ex. grands-parents, frères/sœurs de plus de 25 ans, enfants mariés, oncles/tantes) ?",
        "هل تعيش مع أقارب آخرين أو أصهار (مثل الأجداد، إخوة فوق 25، أبناء متزوجين، أعمام/خالات)؟",
        "Diğer akraba veya hısımlarla mı yaşıyorsunuz (örn. büyükanne/baba, 25 üstü kardeşler, evli çocuklar, hala/dayı)?",
        "A jetoni me të afërm ose krushq të tjerë (p.sh. gjyshër, vëllezër/motra mbi 25, fëmijë të martuar, hallë/xhaxha)?",
    )),
    "chbxWohnenSonstige": _Q((
        "Do you live with other people (e.g. flatmates in a shared flat)?",
        "Wohnen Sie mit sonstigen Personen zusammen (z. B. in einer Wohngemeinschaft)?",
        "Vivez-vous avec d'autres personnes (par ex. en colocation) ?",
        "هل تعيش مع أشخاص آخرين (مثل سكن مشترك)؟",
        "Başka kişilerle mi yaşıyorsunuz (örn. paylaşımlı evde)?",
        "A jetoni me persona të tjerë (p.sh. në një banesë të përbashkët)?",
    )),
    "rbtnBedarfUnterkunft": _Q((
        "Do you have costs for accommodation and heating?",
        "Entstehen Ihnen Bedarfe für Unterkunft und Heizung?",
        "Avez-vous des frais de logement et de chauffage ?",
        "هل لديك تكاليف للسكن والتدفئة؟",
        "Konaklama ve ısınma masraflarınız var mı?",
        "A keni shpenzime për strehim dhe ngrohje?",
    ), helps=(
        "If yes, also fill in the Anlage KDU.",
        "Falls ja, füllen Sie auch die Anlage KDU aus.",
        "Si oui, remplissez aussi l'annexe KDU.",
        "إذا نعم، املأ أيضًا ملحق KDU.",
        "Evetse Anlage KDU'yu da doldurun.",
        "Nëse po, plotësoni edhe Anlage KDU.",
    )),

    # ── I. Unterschrift ──────────────────────────────────────────────────
    "dateUnterschriftPerson": _Q((
        "What is today's date (date of your signature)?",
        "Welches Datum hat heute (Datum Ihrer Unterschrift)?",
        "Quelle est la date d'aujourd'hui (date de votre signature) ?",
        "ما تاريخ اليوم (تاريخ توقيعك)؟",
        "Bugünün tarihi nedir (imza tarihiniz)?",
        "Cila është data e sotme (data e nënshkrimit tuaj)?",
    ), helps=(
        "You sign the printed form by hand.",
        "Die Unterschrift leisten Sie von Hand auf dem ausgedruckten Formular.",
        "Vous signez le formulaire imprimé à la main.",
        "توقع على النموذج المطبوع بخط اليد.",
        "Yazdırılan formu elle imzalarsınız.",
        "Formularin e printuar e nënshkruani me dorë.",
    ), ex="13.06.2026", fmt="date"),
    "dateUnterschriftBetreuer": _Q((
        "What is the date for the guardian's/custodian's signature?",
        "Welches Datum gilt für die Unterschrift der Betreuerin/des Betreuers bzw. Vormunds?",
        "Quelle est la date pour la signature du tuteur/curateur ?",
        "ما تاريخ توقيع الوصي/الولي؟",
        "Vasi/kayyum imzası için tarih nedir?",
        "Cila është data për nënshkrimin e kujdestarit?",
    ), ex="13.06.2026", fmt="date"),
}


def _register_bg_verified_questions() -> None:
    """Merge Bürgergeld Hauptantrag verified questions into VERIFIED_BY_FIELD_ID."""
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    VERIFIED_BY_FIELD_ID.update(_QUESTIONS)


_register_bg_verified_questions()
