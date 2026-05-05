"""
Dynamic form template creation from PDF AcroForm fields.

When a user uploads any fillable PDF, this service:
  1. Reads the AcroForm field names directly from the PDF
  2. Generates multilingual questions for each empty field
  3. Creates a case-specific FormTemplate + Question rows in the DB
  4. Pre-fills answers for fields that already have values in the PDF

This replaces the fixed ALG-II-only question flow for any fillable PDF.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.form_template import FormField, FormTemplate
from app.models.question import Question


# ── Multilingual question lookup for common form field names ───────────────────
# Key: lowercase field name (after cleaning). Value: en/de/ar/tr question + type.

_Q = {
    # ── Personal ──────────────────────────────────────────────────────────────
    "vorname":            ("First name",            "Vorname",                  "الاسم الأول",           "Ad",                  "text"),
    "nachname":           ("Last name",             "Nachname",                 "اسم العائلة",           "Soyad",               "text"),
    "familienname":       ("Family name",           "Familienname",             "اسم العائلة",           "Soyad",               "text"),
    "name":               ("Full name",             "Vollständiger Name",        "الاسم الكامل",          "Tam ad",              "text"),
    "geburtsdatum":       ("Date of birth",         "Geburtsdatum",             "تاريخ الميلاد",         "Doğum tarihi",        "date"),
    "geburtsort":         ("Place of birth",        "Geburtsort",               "مكان الميلاد",          "Doğum yeri",          "text"),
    "geburtsland":        ("Country of birth",      "Geburtsland",              "بلد الميلاد",           "Doğum ülkesi",        "text"),
    "staatsangehörigkeit":("Nationality",           "Staatsangehörigkeit",       "الجنسية",               "Uyruk",               "text"),
    "staatsangehoerigkeit":("Nationality",          "Staatsangehörigkeit",       "الجنسية",               "Uyruk",               "text"),
    "familienstand":      ("Marital status",        "Familienstand",            "الحالة الاجتماعية",      "Medeni hal",          "text"),
    "geschlecht":         ("Gender",                "Geschlecht",               "الجنس",                 "Cinsiyet",            "text"),
    "telefon":            ("Phone number",          "Telefonnummer",            "رقم الهاتف",            "Telefon numarası",    "text"),
    "telefonnummer":      ("Phone number",          "Telefonnummer",            "رقم الهاتف",            "Telefon numarası",    "text"),
    "handynummer":        ("Mobile number",         "Handynummer",              "رقم الجوال",            "Cep telefonu",        "text"),
    "email":              ("Email address",         "E-Mail-Adresse",           "البريد الإلكتروني",     "E-posta",             "text"),
    "emailadresse":       ("Email address",         "E-Mail-Adresse",           "البريد الإلكتروني",     "E-posta",             "text"),
    # ── Address ───────────────────────────────────────────────────────────────
    "straße":             ("Street + house no.",    "Straße und Hausnummer",    "الشارع والرقم",         "Sokak ve kapı no.",   "text"),
    "strasse":            ("Street + house no.",    "Straße und Hausnummer",    "الشارع والرقم",         "Sokak ve kapı no.",   "text"),
    "straßehausnummer":   ("Street + house no.",    "Straße und Hausnummer",    "الشارع والرقم",         "Sokak ve kapı no.",   "text"),
    "strassehausnummer":  ("Street + house no.",    "Straße und Hausnummer",    "الشارع والرقم",         "Sokak ve kapı no.",   "text"),
    "hausnummer":         ("House number",          "Hausnummer",               "رقم المنزل",            "Kapı numarası",       "text"),
    "postleitzahl":       ("Postal code",           "Postleitzahl",             "الرمز البريدي",         "Posta kodu",          "text"),
    "plz":                ("Postal code",           "Postleitzahl",             "الرمز البريدي",         "Posta kodu",          "text"),
    "ort":                ("City",                  "Ort",                      "المدينة",               "Şehir",               "text"),
    "stadt":              ("City",                  "Stadt",                    "المدينة",               "Şehir",               "text"),
    "wohnort":            ("Place of residence",    "Wohnort",                  "مكان الإقامة",          "Yaşanılan şehir",     "text"),
    "land":               ("Country",               "Land",                     "البلد",                 "Ülke",                "text"),
    "bundesland":         ("Federal state",         "Bundesland",               "الولاية الفيدرالية",    "Federal eyalet",      "text"),
    "adresse":            ("Address",               "Adresse",                  "العنوان",               "Adres",               "text"),
    # ── Bank ──────────────────────────────────────────────────────────────────
    "iban":               ("IBAN (bank account no.)","IBAN",                    "رقم الحساب (IBAN)",     "IBAN",                "text"),
    "bic":                ("BIC / SWIFT code",      "BIC / SWIFT-Code",         "رمز BIC / SWIFT",       "BIC / SWIFT kodu",    "text"),
    "bank":               ("Bank name",             "Name der Bank",            "اسم البنك",             "Banka adı",           "text"),
    "kreditinstitut":     ("Bank / credit institution","Kreditinstitut",        "المؤسسة المصرفية",      "Banka kurumu",        "text"),
    "kontonummer":        ("Account number",        "Kontonummer",              "رقم الحساب",            "Hesap numarası",      "text"),
    # ── Income / finances ─────────────────────────────────────────────────────
    "einkommen":          ("Monthly income (€)",    "Monatliches Einkommen (€)","الدخل الشهري (€)",      "Aylık gelir (€)",     "text"),
    "gehalt":             ("Salary (€)",            "Gehalt (€)",               "الراتب (€)",            "Maaş (€)",            "text"),
    "kaltmiete":          ("Cold rent (€)",         "Kaltmiete (€)",            "الإيجار الأساسي (€)",   "Kira (€)",            "text"),
    "miete":              ("Monthly rent (€)",      "Monatliche Miete (€)",     "الإيجار الشهري (€)",    "Aylık kira (€)",      "text"),
    "nebenkosten":        ("Utilities (€)",         "Nebenkosten (€)",          "رسوم الخدمات (€)",      "Hizmet bedeli (€)",   "text"),
    "heizkosten":         ("Heating costs (€)",     "Heizkosten (€)",           "تكاليف التدفئة (€)",    "Isıtma gideri (€)",   "text"),
    # ── Employment ────────────────────────────────────────────────────────────
    "arbeitgeber":        ("Employer",              "Arbeitgeber",              "جهة العمل",             "İşveren",             "text"),
    "beruf":              ("Occupation",            "Beruf",                    "المهنة",                "Meslek",              "text"),
    "beschäftigung":      ("Employment status",     "Beschäftigung",            "حالة التوظيف",          "İstihdam durumu",     "text"),
    "beschaeftigung":     ("Employment status",     "Beschäftigung",            "حالة التوظيف",          "İstihdam durumu",     "text"),
    # ── Signature / date ──────────────────────────────────────────────────────
    "datum":              ("Date",                  "Datum",                    "التاريخ",               "Tarih",               "date"),
    "unterschrift":       ("Signature",             "Unterschrift",             "التوقيع",               "İmza",                "text"),
    "ortdatum":           ("Place and date",        "Ort und Datum",            "المكان والتاريخ",        "Yer ve tarih",        "text"),
    # ── Common English field names ────────────────────────────────────────────
    "first_name":         ("First name",            "Vorname",                  "الاسم الأول",           "Ad",                  "text"),
    "last_name":          ("Last name",             "Nachname",                 "اسم العائلة",           "Soyad",               "text"),
    "firstname":          ("First name",            "Vorname",                  "الاسم الأول",           "Ad",                  "text"),
    "lastname":           ("Last name",             "Nachname",                 "اسم العائلة",           "Soyad",               "text"),
    "surname":            ("Surname",               "Nachname",                 "اسم العائلة",           "Soyad",               "text"),
    "date_of_birth":      ("Date of birth",         "Geburtsdatum",             "تاريخ الميلاد",         "Doğum tarihi",        "date"),
    "birthdate":          ("Date of birth",         "Geburtsdatum",             "تاريخ الميلاد",         "Doğum tarihi",        "date"),
    "birth_date":         ("Date of birth",         "Geburtsdatum",             "تاريخ الميلاد",         "Doğum tarihi",        "date"),
    "address":            ("Address",               "Adresse",                  "العنوان",               "Adres",               "text"),
    "street":             ("Street",                "Straße",                   "الشارع",                "Sokak",               "text"),
    "zip":                ("ZIP / postal code",     "Postleitzahl",             "الرمز البريدي",         "Posta kodu",          "text"),
    "zipcode":            ("ZIP / postal code",     "Postleitzahl",             "الرمز البريدي",         "Posta kodu",          "text"),
    "city":               ("City",                  "Stadt",                    "المدينة",               "Şehir",               "text"),
    "country":            ("Country",               "Land",                     "البلد",                 "Ülke",                "text"),
    "nationality":        ("Nationality",           "Staatsangehörigkeit",       "الجنسية",               "Uyruk",               "text"),
    "phone":              ("Phone number",          "Telefonnummer",            "رقم الهاتف",            "Telefon",             "text"),
    "mobile":             ("Mobile number",         "Handynummer",              "رقم الجوال",            "Cep telefonu",        "text"),
    "date":               ("Date",                  "Datum",                    "التاريخ",               "Tarih",               "date"),
    "signature":          ("Signature",             "Unterschrift",             "التوقيع",               "İmza",                "text"),
    "gender":             ("Gender",                "Geschlecht",               "الجنس",                 "Cinsiyet",            "text"),
    "occupation":         ("Occupation",            "Beruf",                    "المهنة",                "Meslek",              "text"),
    "employer":           ("Employer",              "Arbeitgeber",              "جهة العمل",             "İşveren",             "text"),
    "income":             ("Monthly income (€)",    "Monatliches Einkommen",    "الدخل الشهري",          "Aylık gelir",         "text"),
    "salary":             ("Salary",                "Gehalt",                   "الراتب",                "Maaş",                "text"),
    "rent":               ("Monthly rent",          "Monatliche Miete",         "الإيجار الشهري",        "Aylık kira",          "text"),
    "iban_number":        ("IBAN",                  "IBAN",                     "رقم الحساب (IBAN)",     "IBAN",                "text"),
}


def _clean_field_name(raw: str) -> str:
    """
    Remove PDF path noise from widget names.
    'Page1[0].subform[0].Vorname[0]' → 'Vorname'
    'F_Vorname_1' → 'Vorname'
    """
    # Take the last dot-segment (XFA path style)
    parts = re.split(r'[\.\[\]]', raw)
    clean = next((p for p in reversed(parts) if p and not p.isdigit()), raw)
    # Strip leading/trailing underscores, digits, common prefixes
    clean = re.sub(r'^[FfT]_+', '', clean)   # F_ or T_ prefixes
    clean = re.sub(r'_?\d+$', '', clean)      # trailing _1, 1, _01
    return clean.strip()


def _infer_input_type(field_name: str) -> str:
    """Heuristic: detect date or yes/no fields from field name."""
    lower = field_name.lower()
    if any(w in lower for w in ("datum", "date", "geburt", "birth")):
        return "date"
    if any(w in lower for w in ("janein", "ja_nein", "yesno", "yes_no", "checkbox")):
        return "yes_no"
    return "text"


def _humanize(field_name: str) -> str:
    """Turn a raw field name into a readable label: 'GeburtsDatum' → 'Geburts Datum'."""
    # Insert spaces before uppercase letters (camelCase)
    spaced = re.sub(r'([A-Z])', r' \1', field_name).strip()
    # Replace underscores/hyphens with spaces
    human = re.sub(r'[_\-]+', ' ', spaced).strip()
    return human.capitalize()


def make_question_for_field(raw_field_name: str) -> dict:
    """
    Return a dict with question_text, explanation_text, and input_type
    suitable for a Question DB row, based on the PDF field name.
    """
    clean = _clean_field_name(raw_field_name)
    lookup_key = re.sub(r'[^a-z0-9]', '', clean.lower())  # strip all non-alnum for lookup

    # Direct lookup
    data = _Q.get(clean.lower()) or _Q.get(lookup_key)

    # Partial match: find a key that is contained in the lookup_key or vice versa
    if not data:
        for k, v in _Q.items():
            k_plain = re.sub(r'[^a-z0-9]', '', k)
            if len(k_plain) >= 4 and (k_plain in lookup_key or lookup_key in k_plain):
                data = v
                break

    if data:
        en, de, ar, tr, itype = data
        return {
            "question_text":    {"en": en,   "de": de,  "ar": ar,  "tr": tr},
            "explanation_text": {"en": "",   "de": "",  "ar": "",  "tr": ""},
            "input_type": itype,
        }

    # Fallback: use humanised field name as the question label
    human = _humanize(clean) if clean else raw_field_name
    return {
        "question_text":    {"en": human, "de": human, "ar": human, "tr": human},
        "explanation_text": {"en": "",    "de": "",     "ar": "",    "tr": ""},
        "input_type": _infer_input_type(clean),
    }


# ── Template creation ──────────────────────────────────────────────────────────

def create_dynamic_template(
    db: Session,
    case_id: str,
    acroform_fields: dict[str, str],
    form_name: str = "Uploaded PDF Form",
) -> tuple[str, dict[str, str]]:
    """
    Build a case-specific FormTemplate + Questions from the PDF's AcroForm fields.

    Returns:
        template_id  — the ID of the newly created template
        prefilled    — {field_key: value} for fields that were already filled in the PDF
    """
    template_id = f"dyn_{case_id}"

    # Delete stale dynamic template for this case if it exists (re-upload scenario)
    existing = db.query(FormTemplate).filter(FormTemplate.id == template_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    # pdf_field_map is identity for dynamic templates (field_key == pdf widget name)
    pdf_field_map = {name: name for name in acroform_fields}

    db.add(FormTemplate(
        id=template_id,
        name=form_name,
        institution="",
        version="1.0",
        supported_languages=json.dumps(["en", "de", "ar", "tr"]),
        pdf_field_map=json.dumps(pdf_field_map),
        blank_pdf_filename=None,  # signals: use original uploaded PDF
    ))

    prefilled: dict[str, str] = {}

    for idx, (field_name, value) in enumerate(acroform_fields.items(), start=1):
        q_data = make_question_for_field(field_name)

        db.add(FormField(
            id=str(uuid.uuid4()),
            template_id=template_id,
            field_key=field_name,
            pdf_field_name=field_name,
            data_type=q_data["input_type"],
            required=False,
        ))

        db.add(Question(
            id=str(uuid.uuid4()),
            template_id=template_id,
            field_key=field_name,
            order_index=idx,
            input_type=q_data["input_type"],
            question_text=json.dumps(q_data["question_text"]),
            explanation_text=json.dumps(q_data["explanation_text"]),
            options=None,
            condition=None,
        ))

        if value:
            prefilled[field_name] = value

    db.flush()
    return template_id, prefilled
