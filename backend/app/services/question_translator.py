"""
Translates PDF field labels and their options into the user's preferred language.

Called once per upload — generates question text + option labels for every
field in the PDF, in whatever language the user selected.

Fallback chain when Anthropic is unavailable or returns wrong language:
  1. Anthropic (Claude) AI translation in selected language
  2. Deterministic lookup table for known German labels
  3. Number-prefix-stripped label → deterministic lookup
  4. First-word lookup (for compound labels)
  5. Generic "Translation unavailable" message with original label — never silent German
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English", "de": "German", "fr": "French", "ar": "Arabic",
    "tr": "Turkish", "es": "Spanish", "sq": "Albanian", "ru": "Russian",
    "zh": "Chinese", "it": "Italian", "pl": "Polish", "pt": "Portuguese",
    "nl": "Dutch", "fa": "Persian/Farsi", "ur": "Urdu", "hi": "Hindi",
    "bn": "Bengali", "sw": "Swahili", "ha": "Hausa", "fula": "Fula/Fulfulde",
    "so": "Somali", "am": "Amharic", "uk": "Ukrainian", "ro": "Romanian",
}


# ── Deterministic translations for common German form labels ──────────────────
# Keyed by the cleaned German label. Matched case-insensitively.
# Values are SHORT QUESTIONS in each language, not just noun translations.

_DETERMINISTIC_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Vorname": {
        "en": "What is your first name?",
        "fr": "Quel est votre prénom ?",
        "ar": "ما هو اسمك الأول؟",
        "es": "¿Cuál es tu nombre?",
        "tr": "Adınız nedir?",
        "sq": "Cili është emri juaj?",
        "de": "Vorname",
        "ru": "Как ваше имя?",
        "uk": "Яке ваше ім'я?",
        "fa": "نام شما چیست؟",
    },
    "Nachname": {
        "en": "What is your last name?",
        "fr": "Quel est votre nom de famille ?",
        "ar": "ما هو اسم عائلتك؟",
        "es": "¿Cuál es tu apellido?",
        "tr": "Soyadınız nedir?",
        "sq": "Cili është mbiemri juaj?",
        "de": "Nachname",
        "ru": "Как ваша фамилия?",
        "uk": "Яке ваше прізвище?",
        "fa": "نام خانوادگی شما چیست؟",
    },
    "Familienname": {
        "en": "What is your family name?",
        "fr": "Quel est votre nom de famille ?",
        "ar": "ما هو اسم عائلتك؟",
        "es": "¿Cuál es tu apellido?",
        "tr": "Soyadınız nedir?",
        "sq": "Cili është mbiemri juaj?",
        "de": "Familienname",
        "ru": "Как ваша фамилия?",
        "uk": "Яке ваше прізвище?",
    },
    "Geburtsdatum": {
        "en": "What is your date of birth?",
        "fr": "Quelle est votre date de naissance ?",
        "ar": "ما هو تاريخ ميلادك؟",
        "es": "¿Cuál es tu fecha de nacimiento?",
        "tr": "Doğum tarihiniz nedir?",
        "sq": "Cila është data juaj e lindjes?",
        "de": "Geburtsdatum",
        "ru": "Какова ваша дата рождения?",
        "uk": "Яка ваша дата народження?",
        "fa": "تاریخ تولد شما چیست؟",
    },
    "Geburtsname": {
        "en": "What is your birth name (maiden name)?",
        "fr": "Quel est votre nom de naissance ?",
        "ar": "ما هو اسم الولادة (اسم الفتاة)؟",
        "es": "¿Cuál es tu nombre de nacimiento?",
        "tr": "Doğum adınız nedir?",
        "sq": "Cili është emri juaj i lindjes?",
        "de": "Geburtsname",
        "ru": "Какова ваша девичья фамилия?",
        "uk": "Яке ваше дівоче прізвище?",
    },
    "Geburtsort": {
        "en": "What is your place of birth?",
        "fr": "Quel est votre lieu de naissance ?",
        "ar": "ما هو مكان ولادتك؟",
        "es": "¿Cuál es tu lugar de nacimiento?",
        "tr": "Doğum yeriniz nedir?",
        "sq": "Cili është vendi juaj i lindjes?",
        "de": "Geburtsort",
        "ru": "Каково ваше место рождения?",
        "uk": "Яке ваше місце народження?",
    },
    "Staatsangehörigkeit": {
        "en": "What is your nationality?",
        "fr": "Quelle est votre nationalité ?",
        "ar": "ما هي جنسيتك؟",
        "es": "¿Cuál es tu nacionalidad?",
        "tr": "Uyruğunuz nedir?",
        "sq": "Cila është shtetësia juaj?",
        "de": "Staatsangehörigkeit",
        "ru": "Какое у вас гражданство?",
        "uk": "Яке ваше громадянство?",
    },
    "Familienstand": {
        "en": "What is your marital status?",
        "fr": "Quelle est votre situation familiale ?",
        "ar": "ما هي حالتك الاجتماعية؟",
        "es": "¿Cuál es tu estado civil?",
        "tr": "Medeni durumunuz nedir?",
        "sq": "Cila është gjendja juaj civile?",
        "de": "Familienstand",
        "ru": "Каково ваше семейное положение?",
        "uk": "Який ваш сімейний стан?",
    },
    "Geschlecht": {
        "en": "What is your gender?",
        "fr": "Quel est votre genre ?",
        "ar": "ما هو جنسك؟",
        "es": "¿Cuál es tu género?",
        "tr": "Cinsiyetiniz nedir?",
        "sq": "Cili është gjinia juaj?",
        "de": "Geschlecht",
        "ru": "Какой у вас пол?",
        "uk": "Яка ваша стать?",
    },
    "Straße": {
        "en": "What is your street name?",
        "fr": "Quelle est votre rue ?",
        "ar": "ما هو اسم شارعك؟",
        "es": "¿Cuál es tu calle?",
        "tr": "Sokak adınız nedir?",
        "sq": "Cila është rruga juaj?",
        "de": "Straße",
        "ru": "Какая у вас улица?",
        "uk": "Яка ваша вулиця?",
    },
    "Strasse": {
        "en": "What is your street name?",
        "fr": "Quelle est votre rue ?",
        "ar": "ما هو اسم شارعك؟",
        "es": "¿Cuál es tu calle?",
        "tr": "Sokak adınız nedir?",
        "sq": "Cila është rruga juaj?",
        "de": "Straße",
        "ru": "Какая у вас улица?",
        "uk": "Яка ваша вулиця?",
    },
    "Hausnummer": {
        "en": "What is your house number?",
        "fr": "Quel est votre numéro de maison ?",
        "ar": "ما هو رقم منزلك؟",
        "es": "¿Cuál es el número de tu casa?",
        "tr": "Kapı numaranız nedir?",
        "sq": "Cili është numri i shtëpisë suaj?",
        "de": "Hausnummer",
        "ru": "Какой у вас номер дома?",
        "uk": "Який ваш номер будинку?",
    },
    "Postleitzahl": {
        "en": "What is your postal code?",
        "fr": "Quel est votre code postal ?",
        "ar": "ما هو رمزك البريدي؟",
        "es": "¿Cuál es tu código postal?",
        "tr": "Posta kodunuz nedir?",
        "sq": "Cili është kodi juaj postar?",
        "de": "Postleitzahl",
        "ru": "Какой у вас почтовый индекс?",
        "uk": "Який ваш поштовий індекс?",
    },
    "PLZ": {
        "en": "What is your postal code?",
        "fr": "Quel est votre code postal ?",
        "ar": "ما هو رمزك البريدي؟",
        "es": "¿Cuál es tu código postal?",
        "tr": "Posta kodunuz nedir?",
        "sq": "Cili është kodi juaj postar?",
        "de": "Postleitzahl",
        "ru": "Какой у вас почтовый индекс?",
        "uk": "Який ваш поштовий індекс?",
    },
    "Ort": {
        "en": "What is your city or town?",
        "fr": "Quelle est votre ville ?",
        "ar": "ما هي مدينتك؟",
        "es": "¿Cuál es tu ciudad?",
        "tr": "Şehriniz nedir?",
        "sq": "Cili është qyteti juaj?",
        "de": "Ort",
        "ru": "Какой у вас город?",
        "uk": "Яке ваше місто?",
    },
    "Wohnort": {
        "en": "What is your place of residence?",
        "fr": "Quel est votre lieu de résidence ?",
        "ar": "ما هو مكان إقامتك؟",
        "es": "¿Cuál es tu lugar de residencia?",
        "tr": "İkamet yeriniz nedir?",
        "sq": "Cili është vendbanimi juaj?",
        "de": "Wohnort",
        "ru": "Каково ваше место проживания?",
        "uk": "Яке ваше місце проживання?",
    },
    "Land": {
        "en": "What country do you live in?",
        "fr": "Dans quel pays vivez-vous ?",
        "ar": "في أي بلد تعيش؟",
        "es": "¿En qué país vives?",
        "tr": "Hangi ülkede yaşıyorsunuz?",
        "sq": "Në cilin shtet jetoni?",
        "de": "Land",
        "ru": "В какой стране вы живёте?",
        "uk": "В якій країні ви живете?",
    },
    "Telefon": {
        "en": "What is your phone number?",
        "fr": "Quel est votre numéro de téléphone ?",
        "ar": "ما هو رقم هاتفك؟",
        "es": "¿Cuál es tu número de teléfono?",
        "tr": "Telefon numaranız nedir?",
        "sq": "Cili është numri juaj i telefonit?",
        "de": "Telefon",
        "ru": "Какой у вас номер телефона?",
        "uk": "Який ваш номер телефону?",
    },
    "Telefonnummer": {
        "en": "What is your phone number?",
        "fr": "Quel est votre numéro de téléphone ?",
        "ar": "ما هو رقم هاتفك؟",
        "es": "¿Cuál es tu número de teléfono?",
        "tr": "Telefon numaranız nedir?",
        "sq": "Cili është numri juaj i telefonit?",
        "de": "Telefonnummer",
        "ru": "Какой у вас номер телефона?",
        "uk": "Який ваш номер телефону?",
    },
    "E-Mail": {
        "en": "What is your email address?",
        "fr": "Quelle est votre adresse e-mail ?",
        "ar": "ما هو بريدك الإلكتروني؟",
        "es": "¿Cuál es tu correo electrónico?",
        "tr": "E-posta adresiniz nedir?",
        "sq": "Cila është adresa juaj e emailit?",
        "de": "E-Mail",
        "ru": "Какой у вас адрес электронной почты?",
        "uk": "Яка ваша електронна пошта?",
    },
    "Email": {  # alias — common AcroForm spelling without hyphen
        "en": "What is your email address?",
        "fr": "Quelle est votre adresse e-mail ?",
        "ar": "ما هو بريدك الإلكتروني؟",
        "es": "¿Cuál es tu correo electrónico?",
        "tr": "E-posta adresiniz nedir?",
        "sq": "Cila është adresa juaj e emailit?",
        "de": "E-Mail",
        "ru": "Какой у вас адрес электронной почты?",
        "uk": "Яка ваша електронна пошта?",
    },
    "EMail": {  # alias — common camelCase variant after _clean_acroform_field_name
        "en": "What is your email address?",
        "fr": "Quelle est votre adresse e-mail ?",
        "ar": "ما هو بريدك الإلكتروني؟",
        "es": "¿Cuál es tu correo electrónico?",
        "tr": "E-posta adresiniz nedir?",
        "sq": "Cila është adresa juaj e emailit?",
        "de": "E-Mail",
        "ru": "Какой у вас адрес электронной почты?",
        "uk": "Яка ваша електронна пошта?",
    },
    "Mobilfunknummer": {
        "en": "What is your mobile phone number?",
        "fr": "Quel est votre numéro de téléphone portable ?",
        "ar": "ما هو رقم هاتفك المحمول؟",
        "es": "¿Cuál es tu número de móvil?",
        "tr": "Cep telefonu numaranız nedir?",
        "sq": "Cili është numri juaj i telefonit celular?",
        "de": "Mobilfunknummer",
        "ru": "Какой у вас номер мобильного телефона?",
        "uk": "Який ваш номер мобільного телефону?",
    },
    "Mobiltelefon": {
        "en": "What is your mobile phone number?",
        "fr": "Quel est votre numéro de téléphone portable ?",
        "ar": "ما هو رقم هاتفك المحمول؟",
        "es": "¿Cuál es tu número de móvil?",
        "tr": "Cep telefonu numaranız nedir?",
        "sq": "Cili është numri juaj i telefonit celular?",
        "de": "Mobiltelefon",
        "ru": "Какой у вас номер мобильного телефона?",
        "uk": "Який ваш номер мобільного телефону?",
    },
    "Handynummer": {
        "en": "What is your mobile phone number?",
        "fr": "Quel est votre numéro de téléphone portable ?",
        "ar": "ما هو رقم هاتفك المحمول؟",
        "es": "¿Cuál es tu número de móvil?",
        "tr": "Cep telefonu numaranız nedir?",
        "sq": "Cili është numri juaj i telefonit celular?",
        "de": "Handynummer",
        "ru": "Какой у вас номер мобильного телефона?",
        "uk": "Який ваш номер мобільного телефону?",
    },
    "IBAN": {
        "en": "What is your IBAN (bank account number)?",
        "fr": "Quel est votre IBAN (numéro de compte bancaire) ?",
        "ar": "ما هو رقم حسابك المصرفي (IBAN)؟",
        "es": "¿Cuál es tu IBAN (número de cuenta bancaria)?",
        "tr": "IBAN numaranız nedir (banka hesap numarası)?",
        "sq": "Cili është IBAN-i juaj (numri i llogarisë bankare)?",
        "de": "IBAN",
        "ru": "Каков ваш IBAN (номер банковского счёта)?",
        "uk": "Який ваш IBAN (номер банківського рахунку)?",
    },
    "BIC": {
        "en": "What is your BIC (bank identifier code)?",
        "fr": "Quel est votre BIC (code bancaire) ?",
        "ar": "ما هو رمز البنك BIC؟",
        "es": "¿Cuál es tu BIC (código bancario)?",
        "tr": "BIC kodunuz nedir?",
        "sq": "Cili është kodi juaj BIC?",
        "de": "BIC",
        "ru": "Каков ваш BIC?",
        "uk": "Який ваш BIC?",
    },
    "Kontonummer": {
        "en": "What is your account number?",
        "fr": "Quel est votre numéro de compte ?",
        "ar": "ما هو رقم حسابك؟",
        "es": "¿Cuál es tu número de cuenta?",
        "tr": "Hesap numaranız nedir?",
        "sq": "Cili është numri juaj i llogarisë?",
        "de": "Kontonummer",
        "ru": "Каков ваш номер счёта?",
        "uk": "Який ваш номер рахунку?",
    },
    "Steuernummer": {
        "en": "What is your tax identification number?",
        "fr": "Quel est votre numéro fiscal ?",
        "ar": "ما هو رقمك الضريبي؟",
        "es": "¿Cuál es tu número de identificación fiscal?",
        "tr": "Vergi kimlik numaranız nedir?",
        "sq": "Cili është numri juaj i identifikimit tatimor?",
        "de": "Steuernummer",
        "ru": "Каков ваш налоговый номер?",
        "uk": "Який ваш податковий номер?",
    },
    "Ausweisnummer": {
        "en": "What is your ID document number?",
        "fr": "Quel est votre numéro de pièce d'identité ?",
        "ar": "ما هو رقم وثيقة هويتك؟",
        "es": "¿Cuál es el número de tu documento de identidad?",
        "tr": "Kimlik belgenizin numarası nedir?",
        "sq": "Cili është numri i dokumentit tuaj të identitetit?",
        "de": "Ausweisnummer",
        "ru": "Каков номер вашего удостоверения личности?",
        "uk": "Який номер вашого посвідчення особи?",
    },
    "Datum": {
        "en": "What is the date?",
        "fr": "Quelle est la date ?",
        "ar": "ما هو التاريخ؟",
        "es": "¿Cuál es la fecha?",
        "tr": "Tarih nedir?",
        "sq": "Cila është data?",
        "de": "Datum",
        "ru": "Какова дата?",
        "uk": "Яка дата?",
    },
    "Unterschrift": {
        "en": "Please sign here.",
        "fr": "Veuillez signer ici.",
        "ar": "يرجى التوقيع هنا.",
        "es": "Por favor firme aquí.",
        "tr": "Lütfen burayı imzalayın.",
        "sq": "Ju lutemi nënshkruani këtu.",
        "de": "Unterschrift",
        "ru": "Пожалуйста, подпишите здесь.",
        "uk": "Будь ласка, підпишіть тут.",
    },
    "Ort Datum": {
        "en": "Please enter the place and date.",
        "fr": "Veuillez indiquer le lieu et la date.",
        "ar": "يرجى إدخال المكان والتاريخ.",
        "es": "Por favor indique el lugar y la fecha.",
        "tr": "Lütfen yer ve tarihi girin.",
        "sq": "Ju lutemi shkruani vendin dhe datën.",
        "de": "Ort und Datum",
        "ru": "Пожалуйста, укажите место и дату.",
        "uk": "Будь ласка, вкажіть місце та дату.",
    },
    "Bankverbindung": {
        "en": "What are your bank account details?",
        "fr": "Quelles sont vos coordonnées bancaires ?",
        "ar": "ما هي تفاصيل حسابك المصرفي؟",
        "es": "¿Cuáles son tus datos bancarios?",
        "tr": "Banka hesap bilgileriniz nedir?",
        "sq": "Cilat janë të dhënat tuaja bankare?",
        "de": "Bankverbindung",
        "ru": "Каковы ваши банковские реквізиты?",
        "uk": "Які ваші банківські реквізити?",
    },
    # Date components — full questions, not single words
    "Tag": {
        "en": "What day of the month are you filling out this form?",
        "fr": "Quel jour du mois remplissez-vous ce formulaire ?",
        "ar": "ما هو يوم الشهر الذي تملأ فيه هذا النموذج؟",
        "es": "¿Qué día del mes estás rellenando este formulario?",
        "tr": "Bu formu doldurduğunuz ayın kaçıdır?",
        "sq": "Cilin ditë të muajit po plotësoni këtë formular?",
        "de": "An welchem Tag des Monats füllen Sie dieses Formular aus?",
        "ru": "Какое число месяца вы заполняете эту форму?",
        "uk": "Яке число місяця ви заповнюєте цю форму?",
        "fa": "چه روزی از ماه این فرم را پر می‌کنید؟",
    },
    "Monat": {
        "en": "What month are you filling out this form?",
        "fr": "Quel mois remplissez-vous ce formulaire ?",
        "ar": "ما هو الشهر الذي تملأ فيه هذا النموذج؟",
        "es": "¿En qué mes estás rellenando este formulario?",
        "tr": "Bu formu doldurduğunuz ay kaçıdır?",
        "sq": "Cilin muaj po plotësoni këtë formular?",
        "de": "In welchem Monat füllen Sie dieses Formular aus?",
        "ru": "В каком месяце вы заполняете эту форму?",
        "uk": "В якому місяці ви заповнюєте цю форму?",
        "fa": "این فرم را در چه ماهی پر می‌کنید؟",
    },
    "Jahr": {
        "en": "What year are you filling out this form?",
        "fr": "En quelle année remplissez-vous ce formulaire ?",
        "ar": "ما هو العام الذي تملأ فيه هذا النموذج؟",
        "es": "¿En qué año estás rellenando este formulario?",
        "tr": "Bu formu doldurduğunuz yıl nedir?",
        "sq": "Cilin vit po plotësoni këtë formular?",
        "de": "In welchem Jahr füllen Sie dieses Formular aus?",
        "ru": "В каком году вы заполняете эту форму?",
        "uk": "В якому році ви заповнюєте цю форму?",
        "fa": "این فرم را در چه سالی پر می‌کنید؟",
    },
    "Uhrzeit": {
        "en": "What time? (hours and minutes)",
        "fr": "Quelle heure ? (heures et minutes)",
        "ar": "ما هو الوقت؟ (ساعة ودقيقة)",
        "es": "¿Qué hora es? (horas y minutos)",
        "tr": "Saat kaç? (saat ve dakika)",
        "sq": "Çfarë ore është? (orë dhe minuta)",
        "de": "Wie lautet die Uhrzeit? (Stunden und Minuten)",
        "ru": "Какое время? (часы и минуты)",
        "uk": "Який час? (години та хвилини)",
    },
    # Additional common fields — full questions
    "Name": {
        "en": "What is your full name?", "fr": "Quel est votre nom complet ?",
        "ar": "ما هو اسمك الكامل؟", "es": "¿Cuál es tu nombre completo?",
        "tr": "Tam adınız nedir?", "sq": "Cili është emri juaj i plotë?",
        "de": "Wie lautet Ihr vollständiger Name?",
        "ru": "Как ваше полное имя?", "uk": "Як ваше повне ім'я?",
    },
    "Adresse": {
        "en": "What is your address?", "fr": "Quelle est votre adresse ?",
        "ar": "ما هو عنوانك؟", "es": "¿Cuál es tu dirección?",
        "tr": "Adresiniz nedir?", "sq": "Cila është adresa juaj?",
        "de": "Wie lautet Ihre Adresse?",
        "ru": "Какой у вас адрес?", "uk": "Яка ваша адреса?",
    },
    "Anschrift": {
        "en": "What is your postal address?", "fr": "Quelle est votre adresse postale ?",
        "ar": "ما هو عنوانك البريدي؟", "es": "¿Cuál es tu dirección postal?",
        "tr": "Posta adresiniz nedir?", "sq": "Cila është adresa juaj postare?",
        "de": "Wie lautet Ihre Anschrift?",
        "ru": "Какой у вас почтовый адрес?", "uk": "Яка ваша поштова адреса?",
    },
    "Betrag": {
        "en": "What is the amount in Euros? (write a number, e.g. 25.50)",
        "fr": "Quel est le montant en euros ? (écrivez un nombre, p.ex. 25,50)",
        "ar": "ما هو المبلغ باليورو؟ (اكتب رقماً، مثلاً 25.50)",
        "es": "¿Cuál es el importe en euros? (escribe un número, ej. 25,50)",
        "tr": "Euro cinsinden tutar nedir? (sayı yazın, örn. 25,50)",
        "sq": "Sa është shuma në Euro? (shkruani numër, p.sh. 25,50)",
        "de": "Wie hoch ist der Betrag in Euro? (Zahl eintragen, z.B. 25,50)",
        "ru": "Какова сумма в евро? (напишите число, напр. 25,50)",
        "uk": "Яка сума в євро? (напишіть число, напр. 25,50)",
    },
    "Anzahl": {
        "en": "How many? (write only a number, e.g. 3)",
        "fr": "Combien ? (écrivez uniquement un nombre, p.ex. 3)",
        "ar": "كم عدداً؟ (اكتب رقماً فقط، مثلاً 3)",
        "es": "¿Cuántos? (escribe solo un número, ej. 3)",
        "tr": "Kaç tane? (sadece sayı yazın, örn. 3)",
        "sq": "Sa? (shkruani vetëm një numër, p.sh. 3)",
        "de": "Wie viele? (nur Zahl eintragen, z.B. 3)",
        "ru": "Сколько? (напишите только число, напр. 3)",
        "uk": "Скільки? (напишіть тільки число, напр. 3)",
    },
    "Ja": {
        "en": "Yes", "fr": "Oui", "ar": "نعم",
        "es": "Sí", "tr": "Evet", "sq": "Po",
        "de": "Ja", "ru": "Да", "uk": "Так",
    },
    "Nein": {
        "en": "No", "fr": "Non", "ar": "لا",
        "es": "No", "tr": "Hayır", "sq": "Jo",
        "de": "Nein", "ru": "Нет", "uk": "Ні",
    },
    # Transport / location — full questions
    "Startort": {
        "en": "Where does the journey start?",
        "fr": "D'où part le trajet ?",
        "ar": "من أين تبدأ الرحلة؟",
        "es": "¿Dónde comienza el viaje?",
        "tr": "Yolculuk nereden başlıyor?",
        "sq": "Ku fillon udhëtimi?",
        "de": "Wo beginnt die Fahrt?",
        "ru": "Откуда начинается поездка?",
        "uk": "Звідки починається поїздка?",
    },
    "Zielort": {
        "en": "Where does the journey end?",
        "fr": "Où se termine le trajet ?",
        "ar": "أين تنتهي الرحلة؟",
        "es": "¿Dónde termina el viaje?",
        "tr": "Yolculuk nerede bitiyor?",
        "sq": "Ku përfundon udhëtimi?",
        "de": "Wo endet die Fahrt?",
        "ru": "Где заканчивается поездка?",
        "uk": "Де закінчується поїздка?",
    },
    "Zielort / Startort": {
        "en": "Where does the journey go? (start and destination)",
        "fr": "Quel est l'itinéraire ? (départ et destination)",
        "ar": "أين تسير الرحلة؟ (البداية والنهاية)",
        "es": "¿A dónde va el viaje? (salida y destino)",
        "tr": "Yolculuk nereye gidiyor? (başlangıç ve varış)",
        "sq": "Ku shkon udhëtimi? (nisja dhe destinacioni)",
        "de": "Wohin geht die Fahrt? (Start und Ziel)",
        "ru": "Куда идёт поездка? (начало и конец)",
        "uk": "Куди їде? (початок і кінець поїздки)",
    },
    "Beförderung": {
        "en": "What type of transportation is used?",
        "fr": "Quel moyen de transport est utilisé ?",
        "ar": "ما هو نوع وسيلة النقل المستخدمة؟",
        "es": "¿Qué tipo de transporte se usa?",
        "tr": "Hangi ulaşım aracı kullanılıyor?",
        "sq": "Çfarë lloj transporti përdoret?",
        "de": "Welches Beförderungsmittel wird genutzt?",
        "ru": "Какой вид транспорта используется?",
        "uk": "Який вид транспорту використовується?",
    },
    "Strecke": {
        "en": "How far is the route in kilometres? (one way only)",
        "fr": "Quelle est la distance du trajet en kilomètres ? (aller simple uniquement)",
        "ar": "ما هي مسافة الطريق بالكيلومترات؟ (ذهاباً فقط)",
        "es": "¿Cuántos kilómetros hay en el trayecto? (solo ida)",
        "tr": "Güzergah kaç kilometre? (sadece tek yön)",
        "sq": "Sa kilometra është rruga? (vetëm njëdrejt)",
        "de": "Wie viele Kilometer beträgt die Strecke? (nur einfach)",
        "ru": "Сколько километров маршрут? (только в одну сторону)",
        "uk": "Скільки кілометрів маршрут? (тільки в один бік)",
    },
    "Abfahrt": {
        "en": "What time does the journey depart? (hours and minutes)",
        "fr": "À quelle heure part le trajet ? (heures et minutes)",
        "ar": "في أي وقت تغادر الرحلة؟ (ساعة ودقيقة)",
        "es": "¿A qué hora parte el viaje? (horas y minutos)",
        "tr": "Yolculuk saat kaçta başlıyor? (saat ve dakika)",
        "sq": "Në çfarë ore niset udhëtimi? (orë dhe minuta)",
        "de": "Wann beginnt die Fahrt? (Stunden und Minuten)",
        "ru": "В какое время начинается поездка? (часы и минуты)",
        "uk": "О котрій годині починається поїздка? (години та хвилини)",
    },
    "Ankunft": {
        "en": "What time does the journey arrive? (hours and minutes)",
        "fr": "À quelle heure arrive le trajet ? (heures et minutes)",
        "ar": "في أي وقت تصل الرحلة؟ (ساعة ودقيقة)",
        "es": "¿A qué hora llega el viaje? (horas y minutos)",
        "tr": "Yolculuk saat kaçta varıyor? (saat ve dakika)",
        "sq": "Në çfarë ore mbërrin udhëtimi? (orë dhe minuta)",
        "de": "Wann kommt die Fahrt an? (Stunden und Minuten)",
        "ru": "В какое время прибывает поездка? (часы и минуты)",
        "uk": "О котрій годині прибуває поїздка? (години та хвилини)",
    },
    "Grund": {
        "en": "What is the reason?",
        "fr": "Quelle est la raison ?",
        "ar": "ما هو السبب؟",
        "es": "¿Cuál es el motivo?",
        "tr": "Gerekçe nedir?",
        "sq": "Cila është arsyeja?",
        "de": "Was ist der Grund?",
        "ru": "Какова причина?",
        "uk": "Яка причина?",
    },
    "Zweck": {
        "en": "What is the purpose of this?",
        "fr": "Quel est le but ?",
        "ar": "ما هو الغرض من ذلك؟",
        "es": "¿Cuál es el propósito?",
        "tr": "Bu ne amaçla?",
        "sq": "Cili është qëllimi?",
        "de": "Was ist der Zweck?",
        "ru": "В чём цель?",
        "uk": "Яка мета?",
    },
    "Beschreibung": {
        "en": "Please describe:",
        "fr": "Veuillez décrire :",
        "ar": "يرجى الوصف:",
        "es": "Por favor describa:",
        "tr": "Lütfen açıklayın:",
        "sq": "Ju lutemi përshkruani:",
        "de": "Bitte beschreiben Sie:",
        "ru": "Пожалуйста, опишите:",
        "uk": "Будь ласка, опишіть:",
    },
    "Bemerkungen": {
        "en": "Do you have any additional notes or remarks?",
        "fr": "Avez-vous des notes ou remarques supplémentaires ?",
        "ar": "هل لديك أي ملاحظات إضافية؟",
        "es": "¿Tienes alguna nota adicional?",
        "tr": "Ek notunuz veya açıklamanız var mı?",
        "sq": "Keni ndonjë shënim ose vërejtje shtesë?",
        "de": "Haben Sie weitere Anmerkungen?",
        "ru": "Есть ли у вас дополнительные примечания?",
        "uk": "Чи є у вас додаткові примітки?",
    },
}

# Generic "translation unavailable" prefix per language
_UNAVAILABLE_PREFIX: dict[str, str] = {
    "en": "⚠ Translation unavailable",
    "fr": "⚠ Traduction non disponible",
    "ar": "⚠ الترجمة غير متوفرة",
    "es": "⚠ Traducción no disponible",
    "tr": "⚠ Çeviri mevcut değil",
    "sq": "⚠ Përkthimi nuk është i disponueshëm",
    "ru": "⚠ Перевод недоступен",
    "uk": "⚠ Переклад недоступний",
    "fa": "⚠ ترجمه موجود نیست",
    "de": "⚠ Übersetzung nicht verfügbar",
}

# Regex patterns for label normalization
_NUMBERING_PREFIX_RE  = re.compile(r"^\d+\s*[-–.]\s*")       # "13 - Startort" → "Startort"
_TRAILING_NUMBER_RE   = re.compile(r"\s+\d+$")                # "Startort 13"   → "Startort"
_EQUALS_SPLIT_RE      = re.compile(r"\s*=\s*")                # "Zielort=Startort" → split


def _normalize_label_candidates(label: str) -> list[str]:
    """
    Return ordered candidate strings for deterministic lookup.

    Handles:
      "Startort 13"        → ["Startort 13", "Startort"]
      "1 - Startort"       → ["1 - Startort", "Startort"]
      "Zielort=Startort 16"→ ["Zielort=Startort 16", "Zielort=Startort", "Zielort", "Startort"]
      "Vorname der Person" → ["Vorname der Person", "Vorname"]
    """
    s = label.strip()
    seen: list[str] = [s]

    def add(v: str) -> None:
        v = v.strip()
        if v and v not in seen:
            seen.append(v)

    # Strip leading "N - " or "N. " prefix
    no_prefix = _NUMBERING_PREFIX_RE.sub("", s).strip()
    add(no_prefix)

    # Strip trailing " N" number
    no_suffix = _TRAILING_NUMBER_RE.sub("", s).strip()
    add(no_suffix)

    # Both prefix and suffix stripped
    no_both = _TRAILING_NUMBER_RE.sub("", no_prefix).strip()
    add(no_both)

    # Handle "Zielort=Startort" — try each part
    base = no_both or no_suffix or no_prefix or s
    if "=" in base:
        parts = _EQUALS_SPLIT_RE.split(base)
        for part in parts:
            add(part.strip())
            add(_TRAILING_NUMBER_RE.sub("", part).strip())

    # First word as last resort
    first = (no_both or no_suffix or no_prefix or s).split()[0] if (no_both or no_suffix or no_prefix or s).split() else ""
    add(first)

    return [c for c in seen if c]


def get_deterministic_translation(label: str, lang: str) -> Optional[str]:
    """
    Return a hardcoded question for a common German form label, or None.

    Normalises the label before lookup so trailing/leading numbers and
    compound labels like "Zielort=Startort 16" are handled gracefully.
    """
    for candidate in _normalize_label_candidates(label.strip()):
        candidate_lower = candidate.lower()
        entry = _DETERMINISTIC_TRANSLATIONS.get(candidate)
        if entry is None:
            for key, val in _DETERMINISTIC_TRANSLATIONS.items():
                if key.lower() == candidate_lower:
                    entry = val
                    break
        if entry:
            return entry.get(lang) or entry.get("en")
    return None


def generic_untranslated_msg(original_label: str, lang: str) -> str:
    """
    Return a language-appropriate 'translation unavailable' message.
    Never silently shows German as if it were translated.
    """
    prefix = _UNAVAILABLE_PREFIX.get(lang, "⚠ Translation unavailable")
    return f"{prefix}: {original_label}"


# Anthropic model for question translation. Sonnet is the quality/cost sweet
# spot for this short-string translation workload.
ANTHROPIC_MODEL = "claude-sonnet-4-6"

# Unicode block (start, end) per non-Latin target language. Used to sniff
# whether the model actually wrote in the requested script. Latin-script and
# unknown languages are omitted — we can't cheaply verify those, so they pass.
_SCRIPT_RANGES: dict[str, tuple[int, int]] = {
    "ar": (0x0600, 0x06FF), "fa": (0x0600, 0x06FF), "ur": (0x0600, 0x06FF),
    "ru": (0x0400, 0x04FF), "uk": (0x0400, 0x04FF),
    "hi": (0x0900, 0x097F), "bn": (0x0980, 0x09FF),
    "am": (0x1200, 0x137F), "zh": (0x4E00, 0x9FFF),
}


def _looks_like_language(text: str, lang: str) -> bool:
    """
    Cheap sanity check that `text` is plausibly written in `lang`.

    For non-Latin targets we require at least one character in the expected
    Unicode block — this catches the common failure where the model answers in
    English/German for an Arabic/Russian/etc. request. For Latin-script or
    unmapped languages we cannot sniff cheaply, so we return True and rely on
    the verbatim-label check in translate_fields.
    """
    rng = _SCRIPT_RANGES.get(lang)
    if not rng:
        return True
    lo, hi = rng
    return any(lo <= ord(ch) <= hi for ch in text)


def _extract_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating surrounding prose."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            return {}
    return {}


def _resolve_anthropic_key() -> str:
    """
    Effective Anthropic key, or "" when missing/placeholder.

    Reads `settings.anthropic_api_key` first (this is what loads backend/.env,
    since nothing calls load_dotenv()), then falls back to a real OS env var for
    deployment. A key left as the REPLACE placeholder counts as unset.
    """
    key = ""
    try:
        from app.config import settings
        key = settings.anthropic_api_key or ""
    except Exception:
        key = ""
    key = (key or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
    if not key or key.startswith("REPLACE"):
        return ""
    return key


def anthropic_key_configured() -> bool:
    """True when a usable (non-placeholder) Anthropic key is available."""
    return bool(_resolve_anthropic_key())


def _anthropic_client():
    """
    Return an Anthropic client, or None when the SDK is missing or no real key
    is configured (so callers fall back to the deterministic table — never crash).
    """
    try:
        import anthropic
    except ImportError:
        return None
    key = _resolve_anthropic_key()
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def translate_fields(
    fields: list[dict],
    user_language: str,
    document_language: str = "de",
) -> dict[str, dict]:
    """
    Translate field labels + options into user_language via Anthropic (Claude).

    Falls back to static_fallback when the Anthropic SDK/key is unavailable or
    the model returns wrong-language output.
    """
    client = _anthropic_client()
    if client is None:
        return static_fallback(fields, user_language)

    target = LANGUAGE_NAMES.get(user_language, user_language)
    source = LANGUAGE_NAMES.get(document_language, document_language)

    field_lines: list[str] = []
    for f in fields:
        line = f"- {f['field_name']} (type={f['field_type']}"
        if f.get("options"):
            line += f", options={f['options']}"
        if f.get("original_label") and f["original_label"] != f["field_name"]:
            line += f", label='{f['original_label']}'"
        line += ")"
        field_lines.append(line)

    prompt = f"""You are helping immigrants fill out official {source} government forms.
The user speaks {target}. Write EVERYTHING in {target}. Not in {source}. Not in English unless {target} is English.

You are like a patient social worker sitting next to someone with low literacy.
Write questions so simply that a 7-year-old can understand what to answer.

STRICT RULES:
1. Every value MUST be in {target}. Any {source} or wrong-language text is REJECTED.
2. Do NOT include raw field names (txtfPersonVorname, etc.) in any output text.
3. Questions must be complete sentences, not single words or noun phrases.
4. For date fields: always include an example like "e.g. 06.05.2026".
5. For number fields: always say what unit is needed (euros, kilometres, etc.).
6. For checkbox fields: phrase as a yes/no question.
7. Use formal/polite register appropriate for government forms.

Form fields from the {source} document:
{chr(10).join(field_lines)}

Respond with a single JSON object. Keys = exact field names above. For each field provide:
- "question": a clear, complete question in {target} (max 15 words)
- "help": one simple helpful sentence in {target} (what to write and how)
- "example": a concrete example answer in {target} (leave empty string if obvious)
- "format": short format instruction in {target} (e.g. "DD.MM.YYYY", leave empty if not needed)
- "translated_options": map each original option value to its {target} translation (empty object if no options)

Example if {target} were French:
{{
  "txtfPersonVorname": {{
    "question": "Quel est votre prénom ?",
    "help": "Entrez votre prénom exactement comme sur votre pièce d'identité.",
    "example": "Mamadou",
    "format": "",
    "translated_options": {{}}
  }},
  "datePersonGebDatum": {{
    "question": "Quelle est votre date de naissance ?",
    "help": "Entrez votre date de naissance en format jour.mois.année.",
    "example": "15.03.1990",
    "format": "JJ.MM.AAAA",
    "translated_options": {{}}
  }}
}}

Return ONLY valid JSON. No other text."""

    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4000,
            temperature=0.1,
            messages=[
                {"role": "user", "content": prompt},
                # Prefill the reply with "{" so Claude emits a bare JSON object.
                {"role": "assistant", "content": "{"},
            ],
        )
        raw = "{" + (resp.content[0].text or "")
        result = _extract_json(raw)
    except Exception:
        return static_fallback(fields, user_language)

    if not isinstance(result, dict) or not result:
        return static_fallback(fields, user_language)

    # ── Wrong-language / not-translated guard ────────────────────────────────
    # The old guard only caught questions returned verbatim as the German label.
    # We also catch wrong-SCRIPT output (e.g. English/German when Arabic was
    # requested) via a cheap Unicode-block sniff. Behavior:
    #   • > half the fields look wrong → whole-batch deterministic fallback
    #   • otherwise                    → repair only the bad fields in place
    #                                    (deterministic table, else raw label)
    if user_language not in ("de", document_language):
        label_by_name = {f["field_name"]: f.get("original_label", "") for f in fields}
        bad: list[str] = []
        for fid, tr in result.items():
            q = tr.get("question", "") if isinstance(tr, dict) else ""
            if (not q
                    or q == label_by_name.get(fid)
                    or not _looks_like_language(q, user_language)):
                bad.append(fid)
        if len(bad) > len(fields) / 2:
            return static_fallback(fields, user_language)
        for fid in bad:
            label = label_by_name.get(fid, "")
            repaired = get_deterministic_translation(label, user_language) or label
            if isinstance(result.get(fid), dict):
                result[fid]["question"] = repaired
            else:
                result[fid] = {
                    "question": repaired,
                    "explanation": "",
                    "translated_options": {},
                }
    return result


def static_fallback(fields: list[dict], user_language: str) -> dict[str, dict]:
    """
    Fallback when Groq is unavailable or no_ai=true.

    Fallback order per field:
    1. Deterministic lookup (exact label, number-prefix-stripped, first-word)
    2. original_label as-is — always human-readable, never a raw technical ID

    The user may see a German label when translation is unavailable, but they will
    never see "Translation unavailable" text or a raw technical field_id.
    field_map_to_defs applies additional quality gates after this runs.
    """
    result = {}
    for f in fields:
        label = f.get("original_label") or f.get("field_name", "")
        opts = f.get("options", [])

        # Try deterministic translation (handles exact, prefix-stripped, first-word)
        question = get_deterministic_translation(label, user_language) or label

        result[f["field_name"]] = {
            "question": question,
            "explanation": "",
            "translated_options": {o: o for o in opts},
        }
    return result


# Keep private alias for backward compat
_static_fallback = static_fallback
