"""
Verified field map for the Familienkasse "Antrag auf Kinderzuschlag" (KiZ 1).

Fourth Level 1 verified template. The Kinderzuschlag main application — the
form low-income working families submit to top up Kindergeld. It is the
gateway form of the KiZ family (the income details live on the companion
"Anlage Antragsteller(in)/Partner(in)" and one "Anlage Kind" per child, both
separate forms triaged for later).

Source PDF
----------
templates_source/incoming/kiz1_antrag.pdf
(official: arbeitsagentur.de/datei/kiz1-antrag_ba036540.pdf, Stand 02/2024)

The PDF is XFA-styled (Formular1[0]… widget tree, /Btn stubs without /AP),
so it uses the same fill_strategy="fitz_acroform" path as KG1.

Fingerprint
-----------
Required phrases (all): "antrag auf kinderzuschlag" + the form-unique footer
"kiz 1 - seite". The footer appears ONLY on this main form, never on the KiZ
Anlagen or any KG form — verified empirically against every PDF in
templates_source/incoming/.

Field strategy (v1)
-------------------
- Page 1 of the PDF is an info cover sheet with no widgets; all fields live on
  physical pages 2-3 (source_page 1-2 here, 1-indexed from the first page that
  actually carries fields — matches how fitz/pdfplumber number them).
- Frage 1 applicant block, Frage 2 partner (progressive — details unlock once a
  partner name is entered), Frage 3 bank, Frage 4 the claimed-children table
  (progressive rows), and the rarely-used Frage 5-7 household-edge tables
  (anchor cell shown, the rest unlocks only when the anchor is a real entry).
- Familienstand is one logical radio question over 5 /Btn widgets.
- No SplitField: the IBAN is a single maxlen-34 widget, not a comb.

Progressive disclosure
---------------------
Repeating rows/details are gated with field_not_equals "-" (and the partner
block on its name): an unanswered or "-" anchor keeps the dependent fields
hidden, a real entry reveals the next row. This keeps a one-child / no-partner
family to a short flow while still supporting large households. Evaluated
client-side (frontend lib/conditions.ts) and re-applied at fill time.

Every shown field has a verified question in en/de/fr/ar/tr/sq.
weak_questions=0 and ai_calls_made=0 invariants must hold.
"""
from __future__ import annotations

from app.services.form_templates import RadioGroup, VerifiedTemplate

_S1 = "Formular1[0].Seite-1[0]"
_S2 = "Formular1[0].Seite-2[0]"

# ── Header ────────────────────────────────────────────────────────────────────
W_NAME_KGB = _S1 + ".Kopfzeile[0].#area[2].Name_Vorname_KGB[0]"
W_KG_NR    = _S1 + ".Kopfzeile[0].#area[2].KG-Nr[0]"

# ── Frage 1 — Angaben zur Person ──────────────────────────────────────────────
W_NAME        = _S1 + ".Frage-1[0].Name-KGB[0]"
W_GEBDATUM    = _S1 + ".Frage-1[0].Geburtsdatum-KGB[0]"
W_GEBNAME_ABW = _S1 + ".Frage-1[0].abweichenderGeburtsname[0]"
W_TITEL       = _S1 + ".Frage-1[0].Titel-KGB[0]"
W_ANSCHRIFT   = _S1 + ".Frage-1[0].Anschrift[0]"
W_GESCHLECHT  = _S1 + ".Frage-1[0].Geschlecht[0]"
W_STAATSANG   = _S1 + ".Frage-1[0].Staatsangeh-KGB[0]"
W_TELEFON     = _S1 + ".Frage-1[0].Telefonnr[0]"
# Familienstand — 5 sibling checkboxes
W_FS_LEDIG       = _S1 + ".Frage-1[0].ledig[0]"
W_FS_VERHEIRATET = _S1 + ".Frage-1[0].verheiratet[0]"
W_FS_GESCHIEDEN  = _S1 + ".Frage-1[0].geschieden[0]"
W_FS_GETRENNT    = _S1 + ".Frage-1[0].getrennt-lebend[0]"
W_FS_VERWITWET   = _S1 + ".Frage-1[0].verwitwet[0]"
W_FS_SEIT        = _S1 + ".Frage-1[0].Fam-stand-seit[0]"

# ── Frage 2 — Partner ─────────────────────────────────────────────────────────
W_PRT_NAME      = _S1 + ".Frage-2[0].Name-Partner[0]"
W_PRT_STAATSANG = _S1 + ".Frage-2[0].Staatsangeh-Partner[0]"
W_PRT_GEBDATUM  = _S1 + ".Frage-2[0].Geburtsdatum-Partner[0]"

# ── Frage 3 — Kontoverbindung ─────────────────────────────────────────────────
W_IBAN         = _S1 + ".Frage-3[0].IBAN[0]"
W_BIC          = _S1 + ".Frage-3[0].BIC[0]"
W_KONTOINHABER = _S1 + ".Frage-3[0].Kontoinhaber[0]"

# ── Frage 4 — claimed children (6 rows × 2 cols) ──────────────────────────────
def _w_t4(row: int, cell: int) -> str:
    return f"{_S1}.Frage-4[0].Kindertabelle-P-4[0].Zeile{row}[0].Zelle{cell}[0]"

# ── Frage 5 — children not permanently in the household (3 rows × 2 cols) ──────
# Quirk: row 2's second cell is Zelle1[1], not Zelle3[0].
_F5 = _S2 + ".Frage-5[0].Kindertabelle-P-5[0]"
_F5_CELLS = {
    1: (_F5 + ".Zeile1[0].Zelle1[0]", _F5 + ".Zeile1[0].Zelle3[0]"),
    2: (_F5 + ".Zeile2[0].Zelle1[0]", _F5 + ".Zeile2[0].Zelle1[1]"),
    3: (_F5 + ".Zeile3[0].Zelle1[0]", _F5 + ".Zeile3[0].Zelle3[0]"),
}

# ── Frage 6 — other under-25 children not in the household (3 rows × 3 cols) ──
def _w_t6(row: int, cell: int) -> str:
    return f"{_S2}.Frage-6[0].Kindertabelle-P-6[0].Zeile{row}[0].Zelle{cell}[0]"

# ── Frage 7 — other permanent household members (5 rows × 4 cols) ─────────────
# Quirk: row 3's third cell is #field[2], not Zelle3[0].
_F7 = _S2 + ".Frage-7[0].Tabelle-P-7[0]"
def _w_t7(row: int, cell: int) -> str:
    if row == 3 and cell == 3:
        return _F7 + ".Zeile3[0].#field[2]"
    return f"{_F7}.Zeile{row}[0].Zelle{cell}[0]"

# ── Signature block ───────────────────────────────────────────────────────────
W_DATUM  = _S2 + ".#area[3].Datum\\.Antrag\\.0[0]"
W_KG_NR2 = _S2 + ".#area[3].KG-Nr-zweiter-Antragsteller[0]"

# ── Logical IDs ───────────────────────────────────────────────────────────────
L_FAMILIENSTAND = "kiz1_familienstand"

_FS_OPTIONS = [
    "ledig", "verheiratet/verpartnert",
    "geschieden/Partnerschaft aufgehoben", "getrennt lebend", "verwitwet",
]


# ── Conditions ────────────────────────────────────────────────────────────────
def _real(widget: str) -> dict:
    """Show only when `widget` holds a real entry (answered AND not the '-'
    skip value). Unanswered → field_not_equals is false → hidden."""
    return {"type": "field_not_equals", "field_key": widget, "value": "-"}


# "getrennt lebend seit" date only when the status is 'getrennt lebend'.
_C_GETRENNT = {"type": "field_equals", "field_key": L_FAMILIENSTAND,
               "value": "getrennt lebend"}
# Partner details unlock once a partner name is entered.
_C_HAS_PARTNER = _real(W_PRT_NAME)


_REQUIRED = [
    "antrag auf kinderzuschlag",
    "kiz 1 - seite",          # footer — unique to the main KiZ 1 form
]


class Kiz1AntragTemplate(VerifiedTemplate):
    template_id   = "kiz1_antrag_v1"
    name          = "Familienkasse — Antrag auf Kinderzuschlag (KiZ 1)"
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

        fields = [
            # ── Header ───────────────────────────────────────────────────
            auto(W_NAME_KGB, "Name, Vorname der kindergeldbeziehenden Person",
                 "text", 1, src_text="Familienname und Vorname der kindergeldbeziehenden Person"),
            auto(W_KG_NR, "Kindergeld-Nummer", "text", 1, src_text="Kindergeld-Nr."),

            # ── Frage 1 — Person ─────────────────────────────────────────
            auto(W_NAME, "Familienname, Vorname", "text", 1),
            auto(W_GEBDATUM, "Geburtsdatum", "text", 1),
            auto(W_GEBNAME_ABW,
                 "Abweichender Geburtsname / Name aus früherer Ehe", "text", 1,
                 src_text="Ggf. abweichender Geburtsname und/oder Familienname aus früherer Ehe"),
            auto(W_TITEL, "Titel", "text", 1, src_text="Titel (optional)"),
            auto(W_ANSCHRIFT, "Anschrift (Straße, Hausnummer, PLZ, Wohnort)",
                 "text", 1),
            auto(W_GESCHLECHT, "Geschlecht", "select", 1, opts=["m", "w", "d"]),
            auto(W_STAATSANG, "Staatsangehörigkeit", "text", 1),
            auto(W_TELEFON, "Telefonnummer für Rückfragen", "text", 1),
            auto(L_FAMILIENSTAND, "Familienstand", "radio", 1,
                 opts=_FS_OPTIONS, src_text="Familienstand"),
            auto(W_FS_SEIT, "Getrennt lebend seit", "text", 1,
                 src_text="getrennt lebend seit", condition=_C_GETRENNT),

            # ── Frage 2 — Partner ────────────────────────────────────────
            auto(W_PRT_NAME,
                 "Familienname, Vorname des Partners / der Partnerin", "text", 1,
                 src_text="Angaben zu meinem/meiner im Haushalt lebenden Partner(in)"),
            auto(W_PRT_GEBDATUM, "Geburtsdatum des Partners / der Partnerin",
                 "text", 1, condition=_C_HAS_PARTNER),
            auto(W_PRT_STAATSANG, "Staatsangehörigkeit des Partners / der Partnerin",
                 "text", 1, condition=_C_HAS_PARTNER),

            # ── Frage 3 — Bank ───────────────────────────────────────────
            auto(W_IBAN, "IBAN", "text", 1),
            auto(W_BIC, "BIC", "text", 1, src_text="BIC (bei deutscher IBAN nicht nötig)"),
            auto(W_KONTOINHABER, "Kontoinhaber(in)", "text", 1),
        ]

        # ── Frage 4 — claimed children (progressive rows) ────────────────
        for r in range(1, 7):
            name_w = _w_t4(r, 1)
            cond = None if r == 1 else _real(_w_t4(r - 1, 1))
            fields.append(auto(name_w, f"child{r}_name", "text", 1, condition=cond))
            fields.append(auto(_w_t4(r, 2), f"child{r}_dob", "text", 1,
                               condition=_real(name_w)))

        # ── Frage 5 — children not permanently in household ──────────────
        for r in (1, 2, 3):
            c1, c2 = _F5_CELLS[r]
            cond = None if r == 1 else _real(_F5_CELLS[r - 1][0])
            fields.append(auto(c1, f"f5_{r}_name", "text", 2, condition=cond))
            fields.append(auto(c2, f"f5_{r}_reason", "text", 2, condition=_real(c1)))

        # ── Frage 6 — other under-25 children without Kindergeld ─────────
        for r in (1, 2, 3):
            name_w = _w_t6(r, 1)
            cond = None if r == 1 else _real(_w_t6(r - 1, 1))
            fields.append(auto(name_w, f"f6_{r}_name", "text", 2, condition=cond))
            fields.append(auto(_w_t6(r, 2), f"f6_{r}_dob", "text", 2, condition=_real(name_w)))
            fields.append(auto(_w_t6(r, 3), f"f6_{r}_reason", "text", 2, condition=_real(name_w)))

        # ── Frage 7 — other permanent household members ──────────────────
        for r in (1, 2, 3, 4, 5):
            name_w = _w_t7(r, 1)
            cond = None if r == 1 else _real(_w_t7(r - 1, 1))
            fields.append(auto(name_w, f"f7_{r}_name", "text", 2, condition=cond))
            fields.append(auto(_w_t7(r, 2), f"f7_{r}_dob", "text", 2, condition=_real(name_w)))
            fields.append(auto(_w_t7(r, 3), f"f7_{r}_rel_me", "text", 2, condition=_real(name_w)))
            fields.append(auto(_w_t7(r, 4), f"f7_{r}_rel_partner", "text", 2, condition=_real(name_w)))

        # ── Signature block ──────────────────────────────────────────────
        fields.append(auto(W_DATUM, "Datum (Unterschrift)", "text", 2,
                           src_text="Datum / Unterschrift"))
        fields.append(auto(W_KG_NR2,
                           "Kindergeld-Nummer der zweiten antragstellenden Person",
                           "text", 2, src_text="KG-Nr. zweiter Antragsteller",
                           condition=_C_HAS_PARTNER))

        return fields

    def get_radio_groups(self) -> list[RadioGroup]:
        widgets = [W_FS_LEDIG, W_FS_VERHEIRATET, W_FS_GESCHIEDEN,
                   W_FS_GETRENNT, W_FS_VERWITWET]
        return [RadioGroup(
            field_id=L_FAMILIENSTAND,
            widget_names=widgets,
            options=list(zip(_FS_OPTIONS, widgets)),
        )]


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


# Ordinal words per locale for the repeating tables.
_ORD = {
    "en": ["1st", "2nd", "3rd", "4th", "5th", "6th"],
    "de": ["1.", "2.", "3.", "4.", "5.", "6."],
    "fr": ["1er", "2e", "3e", "4e", "5e", "6e"],
    "ar": ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس"],
    "tr": ["1.", "2.", "3.", "4.", "5.", "6."],
    "sq": ["1-rë", "2-të", "3-të", "4-t", "5-të", "6-të"],
}


def _row_q(row: int, templates: tuple, helps=None, fmt=None):
    """Build a per-row question. `templates` is a 6-tuple of format strings
    each containing one {o} placeholder for the localized ordinal."""
    o = {loc: _ORD[loc][row - 1] for loc in _LOCALES}
    qs = tuple(templates[i].format(o=o[_LOCALES[i]]) for i in range(6))
    hs = None
    if helps:
        hs = tuple(helps[i].format(o=o[_LOCALES[i]]) for i in range(6))
    return _Q(qs, helps=hs, fmt=fmt)


_QUESTIONS: dict = {
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

    # ── Frage 1 ──────────────────────────────────────────────────────────
    W_NAME: _Q((
        "What is your family name and first name?",
        "Wie lauten Ihr Familienname und Vorname?",
        "Quels sont votre nom de famille et votre prénom ?",
        "ما اسم عائلتك واسمك الشخصي؟",
        "Soyadınız ve adınız nedir?",
        "Cili është mbiemri dhe emri juaj?",
    ), ex="Diallo, Aminata"),
    W_GEBDATUM: _Q((
        "What is your date of birth?",
        "Wann wurden Sie geboren?",
        "Quelle est votre date de naissance ?",
        "ما تاريخ ميلادك؟",
        "Doğum tarihiniz nedir?",
        "Cila është data juaj e lindjes?",
    ), ex="15.03.1990", fmt="date"),
    W_GEBNAME_ABW: _Q((
        "Do you have a different birth name or a name from a former marriage? Write - if not.",
        "Haben Sie einen abweichenden Geburtsnamen oder Namen aus früherer Ehe? Schreiben Sie -, wenn nicht.",
        "Avez-vous un nom de naissance différent ou un nom d'un mariage antérieur ? Écrivez - sinon.",
        "هل لديك اسم ميلاد مختلف أو اسم من زواج سابق؟ اكتب - إذا لا.",
        "Farklı bir doğum adınız veya önceki evlilikten bir adınız var mı? Yoksa - yazın.",
        "A keni një mbiemër lindjeje të ndryshëm ose nga një martesë e mëparshme? Shkruani - nëse jo.",
    ), ex="-"),
    W_TITEL: _Q((
        "Do you have an academic title? Write - if none.",
        "Haben Sie einen Titel? Schreiben Sie -, wenn keinen.",
        "Avez-vous un titre ? Écrivez - sinon.",
        "هل لديك لقب أكاديمي؟ اكتب - إذا لا.",
        "Bir unvanınız var mı? Yoksa - yazın.",
        "A keni ndonjë titull? Shkruani - nëse jo.",
    ), ex="-"),
    W_ANSCHRIFT: _Q((
        "What is your address (street, house number, postal code, city)?",
        "Wie lautet Ihre Anschrift (Straße, Hausnummer, PLZ, Wohnort)?",
        "Quelle est votre adresse (rue, numéro, code postal, ville) ?",
        "ما عنوانك (الشارع، رقم المنزل، الرمز البريدي، المدينة)؟",
        "Adresiniz nedir (sokak, kapı no, posta kodu, şehir)?",
        "Cila është adresa juaj (rruga, numri, kodi postar, qyteti)?",
    ), ex="Hauptstraße 12, 18055 Rostock"),
    W_GESCHLECHT: _Q((
        "What is your gender as in your official documents?",
        "Welches Geschlecht haben Sie laut Ihren Dokumenten?",
        "Quel est votre genre selon vos documents officiels ?",
        "ما جنسك كما في وثائقك الرسمية؟",
        "Resmi belgelerinize göre cinsiyetiniz nedir?",
        "Cila është gjinia juaj sipas dokumenteve zyrtare?",
    ), helps=(
        "Choose m (male), w (female) or d (diverse).",
        "Wählen Sie m (männlich), w (weiblich) oder d (divers).",
        "Choisissez m (masculin), w (féminin) ou d (divers).",
        "اختر m (ذكر) أو w (أنثى) أو d (آخر).",
        "m (erkek), w (kadın) veya d (diğer) seçin.",
        "Zgjidhni m (mashkull), w (femër) ose d (tjetër).",
    )),
    W_STAATSANG: _Q((
        "What is your nationality?",
        "Welche Staatsangehörigkeit haben Sie?",
        "Quelle est votre nationalité ?",
        "ما جنسيتك؟",
        "Uyruğunuz nedir?",
        "Cila është shtetësia juaj?",
    ), ex=("Guinean", "guineisch", "guinéenne", "غينية", "Gineli", "guineane")),
    W_TELEFON: _Q((
        "What phone number can the Familienkasse reach you on during the day?",
        "Unter welcher Telefonnummer sind Sie tagsüber für Rückfragen erreichbar?",
        "À quel numéro de téléphone la Familienkasse peut-elle vous joindre la journée ?",
        "ما رقم الهاتف الذي يمكن لـ Familienkasse الاتصال بك عليه نهارًا؟",
        "Familienkasse gündüz size hangi telefon numarasından ulaşabilir?",
        "Në cilin numër telefoni mund t'ju gjejë Familienkasse gjatë ditës?",
    ), ex="0151 23456789"),
    L_FAMILIENSTAND: _Q((
        "What is your marital status?",
        "Wie ist Ihr Familienstand?",
        "Quelle est votre situation de famille ?",
        "ما هي حالتك الاجتماعية؟",
        "Medeni durumunuz nedir?",
        "Cila është gjendja juaj civile?",
    ), helps=(
        "ledig = single, verheiratet/verpartnert = married/in a registered partnership, "
        "geschieden = divorced, getrennt lebend = living apart, verwitwet = widowed.",
        "ledig, verheiratet/verpartnert, geschieden, getrennt lebend oder verwitwet.",
        "ledig = célibataire, verheiratet/verpartnert = marié(e)/pacsé(e), "
        "geschieden = divorcé(e), getrennt lebend = séparé(e), verwitwet = veuf/veuve.",
        "ledig = أعزب، verheiratet = متزوج، geschieden = مطلق، getrennt lebend = منفصل، verwitwet = أرمل.",
        "ledig = bekâr, verheiratet = evli, geschieden = boşanmış, getrennt lebend = ayrı yaşıyor, verwitwet = dul.",
        "ledig = beqar, verheiratet = i martuar, geschieden = i divorcuar, "
        "getrennt lebend = i ndarë, verwitwet = i ve.",
    )),
    W_FS_SEIT: _Q((
        "Since when have you been living apart?",
        "Seit wann leben Sie getrennt?",
        "Depuis quand vivez-vous séparé(e) ?",
        "منذ متى تعيش منفصلاً؟",
        "Ne zamandan beri ayrı yaşıyorsunuz?",
        "Që kur jetoni të ndarë?",
    ), ex="01.2025", fmt="date"),

    # ── Frage 2 ──────────────────────────────────────────────────────────
    W_PRT_NAME: _Q((
        "If a partner lives in your household, what is their family name and first name? Write - if you have no partner.",
        "Wenn ein(e) Partner(in) in Ihrem Haushalt lebt: Familienname und Vorname? Schreiben Sie -, wenn kein(e) Partner(in).",
        "Si un(e) partenaire vit dans votre foyer, quels sont son nom et prénom ? Écrivez - sinon.",
        "إذا كان لديك شريك في منزلك، ما اسمه واسم عائلته؟ اكتب - إذا لا يوجد شريك.",
        "Hanenizde bir partner yaşıyorsa, soyadı ve adı nedir? Partneriniz yoksa - yazın.",
        "Nëse një partner jeton në shtëpinë tuaj, cili është mbiemri dhe emri? Shkruani - nëse nuk keni partner.",
    ), helps=(
        "This means a spouse or partner who lives with you, even if you are not married.",
        "Gemeint ist ein(e) Ehe- oder Lebenspartner(in), der/die mit Ihnen lebt — auch ohne Trauschein.",
        "Il s'agit d'un(e) conjoint(e) ou partenaire vivant avec vous, même sans mariage.",
        "المقصود زوج أو شريك يعيش معك، حتى دون زواج رسمي.",
        "Sizinle yaşayan eş veya partner kastediliyor, evli olmasanız bile.",
        "Bëhet fjalë për një bashkëshort ose partner që jeton me ju, edhe pa martesë.",
    ), ex="-"),
    W_PRT_GEBDATUM: _Q((
        "What is your partner's date of birth?",
        "Wann wurde Ihr(e) Partner(in) geboren?",
        "Quelle est la date de naissance de votre partenaire ?",
        "ما تاريخ ميلاد شريكك؟",
        "Partnerinizin doğum tarihi nedir?",
        "Cila është data e lindjes së partnerit tuaj?",
    ), ex="20.07.1988", fmt="date"),
    W_PRT_STAATSANG: _Q((
        "What is your partner's nationality?",
        "Welche Staatsangehörigkeit hat Ihr(e) Partner(in)?",
        "Quelle est la nationalité de votre partenaire ?",
        "ما جنسية شريكك؟",
        "Partnerinizin uyruğu nedir?",
        "Cila është shtetësia e partnerit tuaj?",
    )),

    # ── Frage 3 ──────────────────────────────────────────────────────────
    W_IBAN: _Q((
        "What is the IBAN of the bank account where the Kinderzuschlag should be paid?",
        "Wie lautet die IBAN des Kontos, auf das der Kinderzuschlag gezahlt werden soll?",
        "Quel est l'IBAN du compte sur lequel verser le Kinderzuschlag ?",
        "ما هو IBAN الحساب الذي يجب دفع Kinderzuschlag إليه؟",
        "Kinderzuschlag'ın yatırılacağı hesabın IBAN'ı nedir?",
        "Cili është IBAN i llogarisë ku duhet paguar Kinderzuschlag?",
    ), ex="DE89 3704 0044 0532 0130 00"),
    W_BIC: _Q((
        "What is the BIC of your bank? For a German IBAN you can write -.",
        "Wie lautet der BIC Ihrer Bank? Bei deutscher IBAN können Sie - schreiben.",
        "Quel est le BIC de votre banque ? Pour un IBAN allemand, écrivez -.",
        "ما هو BIC لبنكك؟ مع IBAN ألماني يمكنك كتابة -.",
        "Bankanızın BIC'i nedir? Alman IBAN'ı için - yazabilirsiniz.",
        "Cili është BIC i bankës suaj? Për një IBAN gjerman mund të shkruani -.",
    ), ex="-"),
    W_KONTOINHABER: _Q((
        "Who is the account holder (the name on the bank account)?",
        "Wer ist der/die Kontoinhaber(in) (der Name auf dem Konto)?",
        "Qui est le/la titulaire du compte (le nom figurant sur le compte) ?",
        "من هو صاحب الحساب (الاسم المسجل على الحساب)؟",
        "Hesap sahibi kim (hesaptaki isim)?",
        "Kush është mbajtësi i llogarisë (emri në llogari)?",
    ), ex="Aminata Diallo"),

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
    W_KG_NR2: _Q((
        "What is the partner's own Kindergeld number, if they are a second applicant? Write - if none.",
        "Wie lautet die eigene Kindergeld-Nummer des Partners als zweite antragstellende Person? Schreiben Sie -, wenn keine.",
        "Quel est le numéro Kindergeld propre au/à la partenaire comme deuxième demandeur ? Écrivez - sinon.",
        "ما رقم Kindergeld الخاص بالشريك كمقدم طلب ثانٍ؟ اكتب - إذا لا يوجد.",
        "Partnerin ikinci başvuran olarak kendi Kindergeld numarası nedir? Yoksa - yazın.",
        "Cili është numri i vetë Kindergeld i partnerit si aplikant i dytë? Shkruani - nëse jo.",
    ), ex="-"),
}


# ── Programmatic table questions ──────────────────────────────────────────────

# Frage 4 — claimed children
for _r in range(1, 7):
    _QUESTIONS[_w_t4(_r, 1)] = _row_q(_r, (
        "Full name of the {o} child you are claiming Kinderzuschlag for? Write - to stop.",
        "Vor- und Familienname des {o} Kindes, für das Sie Kinderzuschlag beantragen? - zum Beenden.",
        "Nom et prénom du {o} enfant pour lequel vous demandez le Kinderzuschlag ? - pour terminer.",
        "الاسم الكامل للطفل {o} الذي تطلب له Kinderzuschlag؟ اكتب - للإنهاء.",
        "Kinderzuschlag talep ettiğiniz {o} çocuğun tam adı? Bitirmek için -.",
        "Emri i plotë i fëmijës së {o} për të cilin kërkoni Kinderzuschlag? - për të mbaruar.",
    ), helps=(
        "The child must be under 25, unmarried, and your or your partner's biological/adopted child.",
        "Das Kind muss unter 25, unverheiratet und Ihr leibliches/adoptiertes Kind (oder das Ihres Partners) sein.",
        "L'enfant doit avoir moins de 25 ans, être non marié et votre enfant biologique/adopté (ou celui du partenaire).",
        "يجب أن يكون الطفل دون 25 عامًا، غير متزوج، وطفلك البيولوجي/المتبنى أو طفل شريكك.",
        "Çocuk 25 yaşın altında, evli olmamalı ve sizin veya partnerinizin öz/evlat edinilmiş çocuğu olmalı.",
        "Fëmija duhet të jetë nën 25 vjeç, i pamartuar dhe fëmijë biologjik/i adoptuar i juaji ose i partnerit.",
    ))
    _QUESTIONS[_w_t4(_r, 2)] = _row_q(_r, (
        "Date of birth of the {o} child?",
        "Geburtsdatum des {o} Kindes?",
        "Date de naissance du {o} enfant ?",
        "تاريخ ميلاد الطفل {o}؟",
        "{o} çocuğun doğum tarihi?",
        "Data e lindjes së fëmijës së {o}?",
    ), fmt="date")

# Frage 5 — children not permanently in household
for _r in (1, 2, 3):
    _c1, _c2 = _F5_CELLS[_r]
    _QUESTIONS[_c1] = _row_q(_r, (
        "First name of the {o} of your claimed children who does NOT always live with you? Write - if none.",
        "Vorname des {o} unter Punkt 4 genannten Kindes, das NICHT ständig bei Ihnen lebt? - wenn keines.",
        "Prénom du {o} enfant (point 4) qui NE vit PAS toujours chez vous ? - si aucun.",
        "الاسم الأول للطفل {o} المذكور في النقطة 4 الذي لا يعيش معك دائمًا؟ اكتب - إذا لا أحد.",
        "4. maddedeki, sizinle SÜREKLİ yaşamayan {o} çocuğun adı? Yoksa -.",
        "Emri i fëmijës së {o} (pika 4) që NUK jeton gjithmonë me ju? - nëse asnjë.",
    ))
    _QUESTIONS[_c2] = _row_q(_r, (
        "Reason and duration of this child's absence (e.g. with the other parent 1-12 or 13-17 days)?",
        "Grund und Dauer der Abwesenheit dieses Kindes (z. B. beim anderen Elternteil 1-12 oder 13-17 Tage)?",
        "Motif et durée de l'absence de cet enfant (par ex. chez l'autre parent 1-12 ou 13-17 jours) ?",
        "سبب ومدة غياب هذا الطفل (مثلاً عند الوالد الآخر 1-12 أو 13-17 يومًا)؟",
        "Bu çocuğun yokluğunun nedeni ve süresi (örn. diğer ebeveynde 1-12 veya 13-17 gün)?",
        "Arsyeja dhe kohëzgjatja e mungesës së këtij fëmije (p.sh. te prindi tjetër 1-12 ose 13-17 ditë)?",
    ))

# Frage 6 — other under-25 children without Kindergeld
for _r in (1, 2, 3):
    _QUESTIONS[_w_t6(_r, 1)] = _row_q(_r, (
        "Full name of the {o} other under-25 child in your household (no Kindergeld)? Write - if none.",
        "Vor- und Familienname des {o} weiteren Kindes unter 25 in Ihrem Haushalt (ohne Kindergeld)? - wenn keines.",
        "Nom et prénom du {o} autre enfant de moins de 25 ans de votre foyer (sans Kindergeld) ? - si aucun.",
        "الاسم الكامل للطفل {o} الآخر دون 25 عامًا في منزلك (بدون Kindergeld)؟ اكتب - إذا لا أحد.",
        "Hanenizdeki Kindergeld almayan 25 yaş altı {o} diğer çocuğun tam adı? Yoksa -.",
        "Emri i plotë i fëmijës tjetër nën 25 në shtëpinë tuaj (pa Kindergeld), i {o}? - nëse asnjë.",
    ))
    _QUESTIONS[_w_t6(_r, 2)] = _row_q(_r, (
        "Date of birth of this child?",
        "Geburtsdatum dieses Kindes?",
        "Date de naissance de cet enfant ?",
        "تاريخ ميلاد هذا الطفل؟",
        "Bu çocuğun doğum tarihi?",
        "Data e lindjes së këtij fëmije?",
    ), fmt="date")
    _QUESTIONS[_w_t6(_r, 3)] = _row_q(_r, (
        "Reason and duration this child is present in your household?",
        "Grund und Dauer der Anwesenheit dieses Kindes in Ihrem Haushalt?",
        "Motif et durée de la présence de cet enfant dans votre foyer ?",
        "سبب ومدة وجود هذا الطفل في منزلك؟",
        "Bu çocuğun hanenizde bulunma nedeni ve süresi?",
        "Arsyeja dhe kohëzgjatja e pranisë së këtij fëmije në shtëpinë tuaj?",
    ))

# Frage 7 — other permanent household members
for _r in (1, 2, 3, 4, 5):
    _QUESTIONS[_w_t7(_r, 1)] = _row_q(_r, (
        "Full name of the {o} other person permanently living in your household? Write - if none.",
        "Vor- und Familienname der {o} weiteren ständig in Ihrem Haushalt lebenden Person? - wenn keine.",
        "Nom et prénom de la {o} autre personne vivant en permanence dans votre foyer ? - si aucune.",
        "الاسم الكامل للشخص {o} الآخر الذي يعيش بشكل دائم في منزلك؟ اكتب - إذا لا أحد.",
        "Hanenizde sürekli yaşayan {o} diğer kişinin tam adı? Yoksa -.",
        "Emri i plotë i personit tjetër të {o} që jeton përhershëm në shtëpinë tuaj? - nëse asnjë.",
    ), helps=(
        "For example: own children without Kindergeld, step/foster/grandchildren, parents, siblings.",
        "Zum Beispiel: eigene Kinder ohne Kindergeldanspruch, Stief-/Pflege-/Enkelkinder, Eltern, Geschwister.",
        "Par exemple : enfants sans Kindergeld, beaux-enfants, petits-enfants, parents, frères et sœurs.",
        "مثلاً: أطفال بلا Kindergeld، أبناء الزوج/الكفالة/الأحفاد، الوالدان، الإخوة.",
        "Örneğin: Kindergeld almayan kendi çocukları, üvey/koruyucu/torun, ebeveynler, kardeşler.",
        "Për shembull: fëmijë pa Kindergeld, thjeshtër/në kujdestari/nipër, prindër, vëllezër e motra.",
    ))
    _QUESTIONS[_w_t7(_r, 2)] = _row_q(_r, (
        "Date of birth of this person?",
        "Geburtsdatum dieser Person?",
        "Date de naissance de cette personne ?",
        "تاريخ ميلاد هذا الشخص؟",
        "Bu kişinin doğum tarihi?",
        "Data e lindjes së këtij personi?",
    ), fmt="date")
    _QUESTIONS[_w_t7(_r, 3)] = _row_q(_r, (
        "What is this person's relationship to YOU?",
        "In welchem Verwandtschaftsverhältnis steht diese Person zu IHNEN?",
        "Quel est le lien de parenté de cette personne avec VOUS ?",
        "ما صلة قرابة هذا الشخص بك أنت؟",
        "Bu kişinin SİZE akrabalık ilişkisi nedir?",
        "Cila është lidhja farefisnore e këtij personi me JU?",
    ))
    _QUESTIONS[_w_t7(_r, 4)] = _row_q(_r, (
        "What is this person's relationship to your PARTNER? Write - if you have no partner.",
        "In welchem Verwandtschaftsverhältnis steht diese Person zu Ihrem/Ihrer PARTNER(IN)? - wenn kein(e) Partner(in).",
        "Quel est le lien de cette personne avec votre PARTENAIRE ? - si aucun(e) partenaire.",
        "ما صلة قرابة هذا الشخص بشريكك؟ اكتب - إذا لا يوجد شريك.",
        "Bu kişinin PARTNERİNİZE akrabalık ilişkisi nedir? Partneriniz yoksa -.",
        "Cila është lidhja e këtij personi me PARTNERIN tuaj? - nëse nuk keni partner.",
    ))


def _register_kiz1_verified_questions() -> None:
    """Merge KiZ1 verified questions into VERIFIED_BY_FIELD_ID.
    Runs once at module import (lazily via form_templates._all_templates())."""
    from app.services.verified_questions import VERIFIED_BY_FIELD_ID
    VERIFIED_BY_FIELD_ID.update(_QUESTIONS)


_register_kiz1_verified_questions()
