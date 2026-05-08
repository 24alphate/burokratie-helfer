"""
Verified human-quality question text and guidance for known form fields.

Priority: these win over AI translation and the deterministic table.
They are written at a level a 7-year-old can understand.

Keyed by:
  - field_id: matches exact PDF field identifier (verified templates)
  - label_key: matches original_label (case-insensitive, after light normalisation)

Structure per entry:
  { locale: { "question": "...", "help": "...", "example": "..." } }

"help" maps to GuidanceText.plain_language.
"example" maps to GuidanceText.example.
"format" maps to GuidanceText.format_hint.
"""
from __future__ import annotations

# ── Verified question text by field_id ───────────────────────────────────────
# These override AI translation for verified template fields.
# Keyed by exact field_id from the verified template.

VERIFIED_BY_FIELD_ID: dict[str, dict[str, dict[str, str]]] = {

    # ── Jobcenter BuT template ────────────────────────────────────────────────

    "applicant_name_vorname": {
        "en": {
            "question": "What is your full name?",
            "help": "Write your last name first, then your first name, exactly as on your ID or official documents.",
            "example": "Bah Mamadou",
        },
        "fr": {
            "question": "Quel est votre nom complet ?",
            "help": "Écrivez d'abord votre nom de famille, puis votre prénom, exactement comme sur votre document officiel.",
            "example": "Bah Mamadou",
        },
        "ar": {
            "question": "ما هو اسمك الكامل؟",
            "help": "اكتب اسمك الأخير أولاً ثم اسمك الأول، كما يظهران في وثيقة هويتك.",
            "example": "باه محمدو",
        },
        "tr": {
            "question": "Tam adınız nedir?",
            "help": "Önce soyadınızı, sonra adınızı resmi belgenizdeki gibi yazın.",
            "example": "Bah Mamadou",
        },
        "de": {
            "question": "Wie lautet Ihr vollständiger Name?",
            "help": "Schreiben Sie zuerst den Nachnamen, dann den Vornamen, wie auf Ihrem Ausweis.",
            "example": "Müller, Anna",
        },
        "es": {
            "question": "¿Cuál es tu nombre completo?",
            "help": "Escribe primero tu apellido y luego tu nombre, tal como aparece en tu documento oficial.",
            "example": "Bah Mamadou",
        },
        "sq": {
            "question": "Cili është emri juaj i plotë?",
            "help": "Shkruani fillimisht mbiemrin, pastaj emrin, si në dokumentin tuaj zyrtar.",
            "example": "Bah Mamadou",
        },
        "ru": {
            "question": "Как ваше полное имя?",
            "help": "Напишите сначала фамилию, затем имя, как в официальном документе.",
            "example": "Баh Мамаду",
        },
        "uk": {
            "question": "Як ваше повне ім'я?",
            "help": "Напишіть спочатку прізвище, потім ім'я, як в офіційному документі.",
            "example": "Бах Мамаду",
        },
    },

    "applicant_postanschrift": {
        "en": {
            "question": "What is your postal address?",
            "help": "Write the address where you receive letters: street, house number, postal code, and city.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "fr": {
            "question": "Quelle est votre adresse postale ?",
            "help": "Écrivez l'adresse où vous recevez vos courriers : rue, numéro, code postal et ville.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "ar": {
            "question": "ما هو عنوانك البريدي؟",
            "help": "اكتب العنوان الذي تستلم منه الرسائل: الشارع، رقم المنزل، الرمز البريدي، والمدينة.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "tr": {
            "question": "Posta adresiniz nedir?",
            "help": "Mektuplarınızı aldığınız adresi yazın: sokak, kapı numarası, posta kodu ve şehir.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "de": {
            "question": "Wie lautet Ihre Postanschrift?",
            "help": "Straße, Hausnummer, Postleitzahl und Ort, an dem Sie Briefe erhalten.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "es": {
            "question": "¿Cuál es tu dirección postal?",
            "help": "Escribe la dirección donde recibes cartas: calle, número, código postal y ciudad.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "sq": {
            "question": "Cila është adresa juaj postare?",
            "help": "Shkruani adresën ku merrni letra: rruga, numri, kodi postar dhe qyteti.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "ru": {
            "question": "Какой у вас почтовый адрес?",
            "help": "Напишите адрес, по которому получаете письма: улица, номер дома, индекс, город.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
        "uk": {
            "question": "Яка ваша поштова адреса?",
            "help": "Напишіть адресу, де ви отримуєте листи: вулиця, номер будинку, поштовий індекс, місто.",
            "example": "Musterstraße 1, 18055 Rostock",
        },
    },

    "bedarfsgemeinschaft_nummer": {
        "en": {
            "question": "What is your Jobcenter case number (BG-Nummer)?",
            "help": "This number is on letters from the Jobcenter. It links all members of your household in the benefit system.",
            "example": "12345BG0001234",
            "format": "Copy it exactly as written, including spaces, slashes, or dashes.",
        },
        "fr": {
            "question": "Quel est votre numéro de dossier Jobcenter (BG-Nummer) ?",
            "help": "Ce numéro figure sur les courriers du Jobcenter. Il relie tous les membres de votre foyer au système d'allocations.",
            "example": "12345BG0001234",
            "format": "Copiez-le exactement tel qu'il est écrit.",
        },
        "ar": {
            "question": "ما هو رقم ملفك في مركز العمل (BG-Nummer)؟",
            "help": "هذا الرقم موجود في رسائل مركز العمل. يربط جميع أفراد أسرتك بنظام الإعانات.",
            "example": "12345BG0001234",
        },
        "tr": {
            "question": "Jobcenter dosya numaranız (BG-Nummer) nedir?",
            "help": "Bu numara Jobcenter'dan gelen mektuplarda yazıyor. Hanenizin tüm üyelerini sosyal yardım sistemine bağlar.",
            "example": "12345BG0001234",
        },
        "de": {
            "question": "Wie lautet Ihre BG-Nummer?",
            "help": "Diese Nummer finden Sie auf Schreiben des Jobcenters, meist oben rechts.",
            "example": "12345BG0001234",
        },
        "sq": {
            "question": "Cili është numri juaj i dosjes Jobcenter (BG-Nummer)?",
            "help": "Ky numër gjendet në letrat e Jobcenter. Lidh të gjithë anëtarët e familjes suaj me sistemin e përfitimeve.",
            "example": "12345BG0001234",
        },
        "es": {
            "question": "¿Cuál es su número de expediente del Jobcenter (BG-Nummer)?",
            "help": "Este número aparece en las cartas del Jobcenter. Vincula a todos los miembros de su hogar en el sistema de prestaciones.",
            "example": "12345BG0001234",
        },
        "ru": {
            "question": "Какой ваш номер дела в Jobcenter (BG-Nummer)?",
            "help": "Этот номер указан в письмах Jobcenter. Он связывает всех членов вашей семьи в системе социальных выплат.",
            "example": "12345BG0001234",
        },
        "uk": {
            "question": "Який ваш номер справи в Jobcenter (BG-Nummer)?",
            "help": "Цей номер вказаний у листах від Jobcenter. Він пов'язує всіх членів вашого домогосподарства в системі виплат.",
            "example": "12345BG0001234",
        },
    },

    "tag_der_antragstellung": {
        "en": {
            "question": "What is today's date (when you are filling out this form)?",
            "help": "Write the date you are completing this application.",
            "example": "06.05.2026",
            "format": "Use the German format: DD.MM.YYYY",
        },
        "fr": {
            "question": "Quelle est la date d'aujourd'hui (quand vous remplissez ce formulaire) ?",
            "help": "Écrivez la date à laquelle vous remplissez cette demande.",
            "example": "06.05.2026",
            "format": "Format allemand : JJ.MM.AAAA",
        },
        "ar": {
            "question": "ما هو تاريخ اليوم (عندما تملأ هذا النموذج)؟",
            "help": "اكتب تاريخ اليوم الذي تملأ فيه هذا الطلب.",
            "example": "06.05.2026",
            "format": "استخدم الصيغة الألمانية: يوم.شهر.سنة",
        },
        "tr": {
            "question": "Bu formu doldurduğunuz bugünün tarihi nedir?",
            "help": "Bu başvuruyu doldurduğunuz tarihi yazın.",
            "example": "06.05.2026",
            "format": "Alman formatını kullanın: GG.AA.YYYY",
        },
        "de": {
            "question": "Welches Datum ist heute (Datum der Antragstellung)?",
            "help": "Tragen Sie das Datum ein, an dem Sie diesen Antrag ausfüllen.",
            "example": "06.05.2026",
        },
        "sq": {
            "question": "Cili është data e sotme (kur po plotësoni këtë formular)?",
            "help": "Shkruani datën kur po plotësoni këtë kërkesë.",
            "example": "06.05.2026",
            "format": "Formati: DD.MM.VVVV",
        },
        "es": {
            "question": "¿Cuál es la fecha de hoy (cuando rellena este formulario)?",
            "help": "Escriba la fecha en que completa esta solicitud.",
            "example": "06.05.2026",
            "format": "Formato alemán: DD.MM.AAAA",
        },
        "ru": {
            "question": "Какова сегодняшняя дата (когда вы заполняете этот бланк)?",
            "help": "Напишите дату, когда вы заполняете это заявление.",
            "example": "06.05.2026",
            "format": "Немецкий формат: ДД.ММ.ГГГГ",
        },
        "uk": {
            "question": "Яка сьогоднішня дата (коли ви заповнюєте цей бланк)?",
            "help": "Напишіть дату, коли ви заповнюєте цю заявку.",
            "example": "06.05.2026",
            "format": "Формат: ДД.ММ.РРРР",
        },
    },

    "bg_nummer": {
        "en": {
            "question": "What is the case reference number from your approval letter?",
            "help": "This is printed on your most recent Jobcenter approval letter (Bewilligungsbescheid), labelled 'BG-Nummer', 'Aktenzeichen', or 'Geschäftszeichen'. It proves you are entitled to apply for Bildung und Teilhabe.",
            "example": "12345BG0001234",
            "format": "Copy it exactly as written, including any slashes, dashes, or spaces.",
        },
        "fr": {
            "question": "Quel est le numéro de dossier de votre lettre d'approbation ?",
            "help": "Il figure sur votre dernière lettre d'approbation du Jobcenter, sous la mention 'BG-Nummer', 'Aktenzeichen' ou 'Geschäftszeichen'.",
            "example": "12345BG0001234",
            "format": "Recopiez-le exactement tel qu'il est écrit.",
        },
        "ar": {
            "question": "ما هو رقم الملف من رسالة الموافقة الخاصة بك؟",
            "help": "يظهر في آخر رسالة موافقة من مركز العمل، تحت عنوان 'BG-Nummer' أو 'Aktenzeichen'. يُثبت أنك مؤهل للتقدم بطلب لـ Bildung und Teilhabe.",
            "example": "12345BG0001234",
        },
        "tr": {
            "question": "Onay mektubunuzdaki dosya referans numarası nedir?",
            "help": "Bu numara, Jobcenter onay mektubunuzda (Bewilligungsbescheid) 'BG-Nummer' veya 'Aktenzeichen' olarak geçer.",
            "example": "12345BG0001234",
        },
        "de": {
            "question": "Wie lautet das Aktenzeichen / die BG-Nummer des Bewilligungsbescheids?",
            "help": "Das Aktenzeichen finden Sie auf Ihrem aktuellen Bewilligungsbescheid, meist oben rechts.",
            "example": "12345BG0001234",
        },
        "es": {
            "question": "¿Cuál es el número de referencia del expediente de su carta de aprobación?",
            "help": "Se encuentra en su última carta de aprobación del Jobcenter, con la etiqueta 'BG-Nummer' o 'Aktenzeichen'.",
            "example": "12345BG0001234",
        },
        "sq": {
            "question": "Cili është numri i referencës së dosjes nga letra juaj e miratimit?",
            "help": "Gjendet në letrën tuaj të fundit të miratimit nga Jobcenter, me etiketën 'BG-Nummer' ose 'Aktenzeichen'.",
            "example": "12345BG0001234",
        },
        "ru": {
            "question": "Какой номер дела указан в вашем письме об одобрении?",
            "help": "Он указан в последнем письме об одобрении от Jobcenter под обозначением 'BG-Nummer' или 'Aktenzeichen'.",
            "example": "12345BG0001234",
        },
        "uk": {
            "question": "Який номер справи вказано у вашому листі про схвалення?",
            "help": "Він зазначений у вашому останньому листі про схвалення від Jobcenter під позначенням 'BG-Nummer' або 'Aktenzeichen'.",
            "example": "12345BG0001234",
        },
    },

    "zustaendiger_standort": {
        "en": {
            "question": "Which Jobcenter office is responsible for your case?",
            "help": "Write the name or address of the Jobcenter branch that manages your benefits. Find it on any recent Jobcenter letter.",
        },
        "fr": {
            "question": "Quel bureau du Jobcenter s'occupe de votre dossier ?",
            "help": "Écrivez le nom ou l'adresse du Jobcenter qui gère vos allocations. Trouvez-le sur un courrier récent.",
        },
        "ar": {
            "question": "أي مكتب Jobcenter مسؤول عن ملفك؟",
            "help": "اكتب اسم أو عنوان فرع Jobcenter الذي يدير إعاناتك.",
        },
        "tr": {
            "question": "Hangi Jobcenter şubesi sizin dosyanızdan sorumludur?",
            "help": "Sosyal yardımlarınızı yöneten Jobcenter şubesinin adını veya adresini yazın.",
        },
        "de": {
            "question": "Welche Jobcenter-Dienststelle ist für Sie zuständig?",
            "help": "Den zuständigen Standort finden Sie auf Schreiben des Jobcenters.",
        },
        "sq": {
            "question": "Cili zyrë e Jobcenter është përgjegjëse për dosjen tuaj?",
            "help": "Shkruani emrin ose adresën e degës Jobcenter që menaxhon përfitimet tuaja.",
        },
        "es": {
            "question": "¿Qué oficina del Jobcenter es responsable de su expediente?",
            "help": "Escriba el nombre o la dirección de la oficina del Jobcenter que gestiona sus prestaciones.",
        },
        "ru": {
            "question": "Какое отделение Jobcenter ведёт ваше дело?",
            "help": "Напишите название или адрес отделения Jobcenter, которое управляет вашими выплатами.",
        },
        "uk": {
            "question": "Яке відділення Jobcenter відповідає за вашу справу?",
            "help": "Вкажіть назву або адресу відділення Jobcenter, яке управляє вашими виплатами.",
        },
    },

    "child_name_vorname_geburtsdatum": {
        "en": {
            "question": "What is the child's full name and date of birth?",
            "help": "Write the last name, first name, and date of birth of the child you are applying for.",
            "example": "Müller, Lena, 12.03.2016",
            "format": "Last name, First name, Date of birth (DD.MM.YYYY)",
        },
        "fr": {
            "question": "Quel est le nom complet et la date de naissance de l'enfant ?",
            "help": "Écrivez le nom, prénom et date de naissance de l'enfant pour lequel vous faites la demande.",
            "example": "Müller, Lena, 12.03.2016",
            "format": "Nom, Prénom, Date de naissance (JJ.MM.AAAA)",
        },
        "ar": {
            "question": "ما هو الاسم الكامل وتاريخ ميلاد الطفل؟",
            "help": "اكتب اسم الطفل الذي تتقدم بالطلب له، واسمه الأول وتاريخ ميلاده.",
            "example": "Müller, Lena, 12.03.2016",
        },
        "tr": {
            "question": "Çocuğun tam adı ve doğum tarihi nedir?",
            "help": "Başvurduğunuz çocuğun soyadı, adı ve doğum tarihini yazın.",
            "example": "Müller, Lena, 12.03.2016",
        },
        "de": {
            "question": "Wie lauten Name, Vorname und Geburtsdatum des Kindes?",
            "help": "Tragen Sie Nachname, Vorname und Geburtsdatum des Kindes ein.",
            "example": "Müller, Lena, 12.03.2016",
        },
        "sq": {
            "question": "Cili është emri i plotë dhe data e lindjes e fëmijës?",
            "help": "Shkruani mbiemrin, emrin dhe datën e lindjes të fëmijës për të cilin bëni kërkesën.",
            "example": "Müller, Lena, 12.03.2016",
            "format": "Mbiemri, Emri, Data e lindjes (DD.MM.VVVV)",
        },
        "es": {
            "question": "¿Cuál es el nombre completo y fecha de nacimiento del niño?",
            "help": "Escriba el apellido, nombre y fecha de nacimiento del niño por el que solicita.",
            "example": "Müller, Lena, 12.03.2016",
            "format": "Apellido, Nombre, Fecha de nacimiento (DD.MM.AAAA)",
        },
        "ru": {
            "question": "Каковы полное имя и дата рождения ребёнка?",
            "help": "Напишите фамилию, имя и дату рождения ребёнка, за которого подаёте заявление.",
            "example": "Müller, Lena, 12.03.2016",
            "format": "Фамилия, Имя, Дата рождения (ДД.ММ.ГГГГ)",
        },
        "uk": {
            "question": "Яке повне ім'я та дата народження дитини?",
            "help": "Напишіть прізвище, ім'я та дату народження дитини, за яку подаєте заявку.",
            "example": "Müller, Lena, 12.03.2016",
        },
    },

    "institution_name": {
        "en": {
            "question": "What is the name of the school, kindergarten, or institution the child attends?",
            "help": "Write the official full name of the school, Kita, daycare, or training institution.",
            "example": "Grundschule am Mühlenberg",
        },
        "fr": {
            "question": "Quel est le nom de l'école, de la crèche ou de l'établissement que fréquente l'enfant ?",
            "help": "Écrivez le nom officiel complet de l'école ou de la garderie.",
            "example": "Grundschule am Mühlenberg",
        },
        "ar": {
            "question": "ما هو اسم المدرسة أو الحضانة التي يلتحق بها الطفل؟",
            "help": "اكتب الاسم الرسمي الكامل للمدرسة أو الحضانة.",
            "example": "Grundschule am Mühlenberg",
        },
        "tr": {
            "question": "Çocuğun gittiği okul, anaokulu veya kurumun adı nedir?",
            "help": "Okulun veya kreşin tam resmi adını yazın.",
            "example": "Grundschule am Mühlenberg",
        },
        "de": {
            "question": "Wie heißt die Schule / Kita / Einrichtung, die das Kind besucht?",
            "help": "Tragen Sie den vollständigen offiziellen Namen ein.",
            "example": "Grundschule am Mühlenberg",
        },
        "sq": {
            "question": "Si quhet shkolla, kopshti ose institucioni që frekuenton fëmija?",
            "help": "Shkruani emrin zyrtar të plotë të shkollës ose kopshtit.",
            "example": "Grundschule am Mühlenberg",
        },
        "es": {
            "question": "¿Cómo se llama la escuela, guardería o institución a la que asiste el niño?",
            "help": "Escriba el nombre oficial completo del centro educativo.",
            "example": "Grundschule am Mühlenberg",
        },
        "ru": {
            "question": "Как называется школа, детский сад или учреждение, которое посещает ребёнок?",
            "help": "Напишите полное официальное название учебного заведения.",
            "example": "Grundschule am Mühlenberg",
        },
        "uk": {
            "question": "Як називається школа, дитячий садок або установа, яку відвідує дитина?",
            "help": "Напишіть повну офіційну назву навчального закладу.",
            "example": "Grundschule am Mühlenberg",
        },
    },

    "institution_address": {
        "en": {
            "question": "What is the address of the school or institution?",
            "help": "Include the street, house number, postal code, and city.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "fr": {
            "question": "Quelle est l'adresse de l'école ou de l'établissement ?",
            "help": "Indiquez la rue, le numéro, le code postal et la ville.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "ar": {
            "question": "ما هو عنوان المدرسة أو المؤسسة؟",
            "help": "أدخل الشارع ورقم المبنى والرمز البريدي والمدينة.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "tr": {
            "question": "Okul veya kurumun adresi nedir?",
            "help": "Sokak, kapı numarası, posta kodu ve şehri ekleyin.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "de": {
            "question": "Wie lautet die Anschrift der Schule / Kita / Einrichtung?",
            "help": "Straße, Hausnummer, Postleitzahl und Ort.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "sq": {
            "question": "Cila është adresa e shkollës ose institucionit?",
            "help": "Përfshini rrugën, numrin e shtëpisë, kodin postar dhe qytetin.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "es": {
            "question": "¿Cuál es la dirección de la escuela o institución?",
            "help": "Incluya la calle, el número, el código postal y la ciudad.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "ru": {
            "question": "Каков адрес школы или учреждения?",
            "help": "Укажите улицу, номер дома, почтовый индекс и город.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
        "uk": {
            "question": "Яка адреса школи або установи?",
            "help": "Вкажіть вулицю, номер будинку, поштовий індекс та місто.",
            "example": "Schulstraße 5, 18055 Rostock",
        },
    },

    "leistung_a_ausflug": {
        "en": {"question": "Are you applying for help with the costs of a school or kindergarten day trip?"},
        "fr": {"question": "Demandez-vous une aide pour les frais d'une sortie scolaire d'une journée ?"},
        "ar": {"question": "هل تطلب مساعدة لتغطية تكاليف رحلة يومية مدرسية؟"},
        "tr": {"question": "Bir günlük okul gezisinin masrafları için yardım talep ediyor musunuz?"},
        "de": {"question": "Beantragen Sie Kostenübernahme für einen eintägigen Schulausflug?"},
        "sq": {"question": "A po aplikoni për ndihmë me kostot e një ekskursioni ditor shkollor?"},
        "es": {"question": "¿Solicita ayuda para los gastos de una excursión escolar de un día?"},
        "ru": {"question": "Подаёте ли вы заявку на помощь в оплате однодневной школьной экскурсии?"},
        "uk": {"question": "Чи подаєте ви заявку на допомогу з витратами на одноденну шкільну екскурсію?"},
    },

    "leistung_b_klassenfahrt": {
        "en": {"question": "Are you applying for help with the costs of a multi-day school or kindergarten trip?"},
        "fr": {"question": "Demandez-vous une aide pour les frais d'un voyage scolaire de plusieurs jours ?"},
        "ar": {"question": "هل تطلب مساعدة لتغطية تكاليف رحلة مدرسية متعددة الأيام؟"},
        "tr": {"question": "Çok günlük okul veya kreş gezisinin masrafları için yardım talep ediyor musunuz?"},
        "de": {"question": "Beantragen Sie Kostenübernahme für eine mehrtägige Klassenfahrt?"},
        "sq": {"question": "A po aplikoni për ndihmë me kostot e një udhëtimi shkollor me shumë ditë?"},
        "es": {"question": "¿Solicita ayuda para los gastos de un viaje escolar de varios días?"},
        "ru": {"question": "Подаёте ли вы заявку на помощь в оплате многодневной школьной поездки?"},
        "uk": {"question": "Чи подаєте ви заявку на допомогу з витратами на багатоденну шкільну поїздку?"},
    },

    "leistung_c_schuelerbefoerderung": {
        "en": {
            "question": "Are you applying for help with the cost of transporting the child to and from school?",
            "help": "This covers bus passes, train tickets, or private car costs when no suitable public transport is available.",
        },
        "fr": {
            "question": "Demandez-vous une aide pour le transport scolaire de l'enfant ?",
            "help": "Cela couvre les abonnements de bus, les tickets de train ou les frais de voiture privée quand il n'y a pas de transport en commun adapté.",
        },
        "ar": {
            "question": "هل تطلب مساعدة لتغطية تكاليف نقل الطفل من وإلى المدرسة؟",
        },
        "tr": {
            "question": "Çocuğun okula gidiş-geliş ulaşım masrafları için yardım talep ediyor musunuz?",
        },
        "de": {
            "question": "Beantragen Sie Kostenübernahme für die Schülerbeförderung?",
        },
        "sq": {
            "question": "A po aplikoni për ndihmë me kostot e transportit të fëmijës deri në shkollë?",
        },
        "es": {
            "question": "¿Solicita ayuda para los gastos de transporte escolar del niño?",
        },
        "ru": {
            "question": "Подаёте ли вы заявку на помощь в оплате транспорта ребёнка до школы?",
        },
        "uk": {
            "question": "Чи подаєте ви заявку на допомогу з витратами на транспорт дитини до школи?",
        },
    },

    "leistung_d_lernfoerderung": {
        "en": {
            "question": "Is the child in need of tutoring or extra learning support to reach the expected grade level?",
            "help": "Select yes if a teacher or school has confirmed the child needs additional tutoring.",
        },
        "fr": {
            "question": "L'enfant a-t-il besoin de soutien scolaire ou de cours particuliers pour atteindre le niveau attendu ?",
        },
        "ar": {
            "question": "هل يحتاج الطفل إلى دروس خصوصية أو دعم تعليمي إضافي للوصول إلى المستوى المطلوب؟",
        },
        "tr": {
            "question": "Çocuğun beklenen sınıf düzeyine ulaşmak için ek özel ders veya öğrenme desteğine ihtiyacı var mı?",
        },
        "de": {
            "question": "Benötigt das Kind Lernförderung (z.B. Nachhilfe), um das Klassenziel zu erreichen?",
        },
        "sq": {
            "question": "A ka nevojë fëmija për mësim privat ose mbështetje shtesë mësimore?",
        },
        "es": {
            "question": "¿Necesita el niño clases particulares o apoyo educativo adicional?",
        },
        "ru": {
            "question": "Нуждается ли ребёнок в дополнительных занятиях или репетиторстве?",
        },
        "uk": {
            "question": "Чи потребує дитина репетиторства або додаткової навчальної підтримки?",
        },
    },

    "leistung_e_mittagessen": {
        "en": {
            "question": "Are you applying for help paying for the child's lunch at school, after-school care, or daycare?",
            "help": "Select yes if the child eats lunch at school, Hort, Kita, or with a childminder and you want support for those costs.",
        },
        "fr": {
            "question": "Demandez-vous une aide pour payer le repas de midi de l'enfant à l'école, en garderie ou en crèche ?",
            "help": "Sélectionnez oui si l'enfant mange à la cantine de l'école, au Hort, à la Kita ou chez une assistante maternelle.",
        },
        "ar": {
            "question": "هل تطلب مساعدة لدفع تكاليف غداء الطفل في المدرسة أو مرفق رعاية الأطفال؟",
        },
        "tr": {
            "question": "Çocuğun okulda, Hort'ta veya kreşteki öğle yemeği masrafları için yardım talep ediyor musunuz?",
        },
        "de": {
            "question": "Beantragen Sie einen Zuschuss zu den Kosten des gemeinschaftlichen Mittagessens?",
        },
        "sq": {
            "question": "A po aplikoni për ndihmë me koston e drekës së fëmijës në shkollë ose kopsht?",
        },
        "es": {
            "question": "¿Solicita ayuda para pagar el almuerzo del niño en la escuela o guardería?",
        },
        "ru": {
            "question": "Подаёте ли вы заявку на помощь в оплате обедов ребёнка в школе или детском саду?",
        },
        "uk": {
            "question": "Чи подаєте ви заявку на допомогу з оплатою обідів дитини в школі або дитячому садку?",
        },
    },

    "leistung_f_soziale_teilhabe": {
        "en": {
            "question": "Are you applying for support for the child's social or cultural activities (e.g. sports club, music lessons)?",
            "help": "This covers up to 15 EUR per month for activities like sports clubs, music lessons, or cultural events that help the child participate socially.",
        },
        "fr": {
            "question": "Demandez-vous une aide pour les activités sociales ou culturelles de l'enfant (sport, musique, etc.) ?",
            "help": "Cela couvre jusqu'à 15 EUR par mois pour des activités comme un club sportif, des cours de musique ou des sorties culturelles.",
        },
        "ar": {
            "question": "هل تطلب دعماً للأنشطة الاجتماعية أو الثقافية للطفل (مثل نادي رياضي، دروس موسيقى)؟",
        },
        "tr": {
            "question": "Çocuğun sosyal veya kültürel faaliyetleri için (spor kulübü, müzik dersi vb.) destek talep ediyor musunuz?",
        },
        "de": {
            "question": "Beantragen Sie Leistungen für die soziale und kulturelle Teilhabe des Kindes?",
        },
        "sq": {
            "question": "A po aplikoni për mbështetje për aktivitetet sociale ose kulturore të fëmijës?",
        },
        "es": {
            "question": "¿Solicita apoyo para las actividades sociales o culturales del niño?",
        },
        "ru": {
            "question": "Подаёте ли вы заявку на поддержку социальных или культурных занятий ребёнка?",
        },
        "uk": {
            "question": "Чи подаєте ви заявку на підтримку соціальних або культурних занять дитини?",
        },
    },

    "transport_cost_period": {
        "en": {
            "question": "How often do the school transport costs occur — monthly, quarterly, or annually?",
            "help": "Choose how often the transport costs are billed: monthly = every month, quarterly = every 3 months, annually = once a year.",
            "example": "monthly",
        },
        "fr": {
            "question": "À quelle fréquence les frais de transport scolaire sont-ils facturés — mensuellement, trimestriellement ou annuellement ?",
            "example": "mensuellement",
        },
        "ar": {
            "question": "كم مرة تتكرر تكاليف النقل المدرسي — شهريًا أو ربع سنوي أو سنويًا؟",
        },
        "tr": {
            "question": "Okul ulaşım masrafları ne sıklıkla oluşuyor — aylık, üç aylık veya yıllık?",
        },
        "de": {
            "question": "Wie oft fallen die Beförderungskosten an — monatlich, vierteljährlich oder jährlich?",
        },
        "sq": {
            "question": "Sa shpesh ndodhin kostot e transportit shkollor — mujore, tremujore ose vjetore?",
            "example": "mujore",
        },
        "es": {
            "question": "¿Con qué frecuencia se producen los gastos de transporte escolar — mensual, trimestral o anualmente?",
            "example": "mensualmente",
        },
        "ru": {
            "question": "Как часто возникают расходы на школьный транспорт — ежемесячно, ежеквартально или ежегодно?",
            "example": "ежемесячно",
        },
        "uk": {
            "question": "Як часто виникають витрати на шкільний транспорт — щомісячно, щоквартально або щорічно?",
            "example": "щомісячно",
        },
    },

    "transport_public_cost_eur": {
        "en": {
            "question": "How much does the public transport pass or ticket cost for the child's school journey (in Euros)?",
            "help": "Enter the amount in Euros. Use a dot or comma for cents.",
            "example": "29.50",
        },
        "fr": {
            "question": "Combien coûte l'abonnement ou le ticket de transport en commun pour le trajet scolaire de l'enfant (en euros) ?",
            "example": "29,50",
        },
        "ar": {
            "question": "ما هي تكلفة تذكرة أو اشتراك المواصلات العامة لرحلة الطفل المدرسية (باليورو)؟",
            "example": "29.50",
        },
        "tr": {
            "question": "Çocuğun okul yolculuğu için toplu taşıma bileti veya aboneliği ne kadar tutuyor (Euro olarak)?",
            "example": "29,50",
        },
        "de": {
            "question": "Wie viel kostet das ÖPNV-Ticket für den Schulweg des Kindes (in Euro)?",
            "example": "29,50",
        },
        "sq": {
            "question": "Sa kushton bileta ose aboniamenti i transportit publik për rrugën e shkollës (në Euro)?",
            "example": "29.50",
        },
        "es": {
            "question": "¿Cuánto cuesta el abono o billete de transporte público para el trayecto escolar del niño (en euros)?",
            "example": "29,50",
        },
        "ru": {
            "question": "Сколько стоит проездной или билет на общественный транспорт для школьной поездки ребёнка (в евро)?",
            "example": "29.50",
        },
        "uk": {
            "question": "Скільки коштує проїзний або квиток на громадський транспорт для шкільної поїздки дитини (у євро)?",
            "example": "29.50",
        },
    },

    "transport_private_cost_eur": {
        "en": {
            "question": "If using a private car, how much does the school journey cost per billing period (in Euros)?",
            "help": "Only fill this in if no public transport is available for the school journey. The billing period is usually monthly.",
            "example": "45.00",
            "format": "Enter the total cost in Euros for the billing period, e.g. 45.00",
        },
        "fr": {
            "question": "Si vous utilisez une voiture privée, quel est le coût du trajet scolaire par période de facturation (en euros) ?",
            "help": "Ne remplissez ceci que si aucun transport en commun n'est disponible pour le trajet scolaire. La période de facturation est généralement mensuelle.",
            "example": "45.00",
        },
        "ar": {
            "question": "إذا كنت تستخدم سيارة خاصة، كم تكلف رحلة المدرسة في كل دورة فوترة (باليورو)؟",
            "help": "أكمل هذا فقط إذا لم تتوفر وسائل نقل عامة للرحلة المدرسية. دورة الفوترة تكون عادةً شهرية.",
            "example": "45.00",
        },
        "tr": {
            "question": "Özel araç kullanılıyorsa, okul yolculuğu fatura dönemi başına ne kadar tutuyor (Euro)?",
            "help": "Bunu yalnızca okul yolculuğu için toplu taşıma mevcut değilse doldurun. Fatura dönemi genellikle aylıktır.",
            "example": "45.00",
        },
        "de": {
            "question": "Wie hoch sind die Kosten für private Beförderung je Abrechnungszeitraum (in Euro)?",
            "help": "Nur ausfüllen, wenn kein öffentliches Verkehrsmittel für den Schulweg verfügbar ist. Der Abrechnungszeitraum ist in der Regel monatlich.",
            "example": "45,00",
        },
        "es": {
            "question": "Si usa un coche privado, ¿cuánto cuesta el trayecto escolar por período de facturación (en euros)?",
            "help": "Rellene esto solo si no hay transporte público disponible para el trayecto escolar. El período de facturación suele ser mensual.",
            "example": "45.00",
        },
        "sq": {
            "question": "Nëse përdorni makinë private, sa kushton udhëtimi deri në shkollë për periudhë faturimi (në Euro)?",
            "help": "Plotësoni këtë vetëm nëse nuk ka transport publik për udhëtimin deri në shkollë. Periudha e faturimit është zakonisht mujore.",
            "example": "45.00",
        },
        "ru": {
            "question": "Если вы используете личный автомобиль, сколько стоит поездка в школу за расчётный период (в евро)?",
            "help": "Заполните это только если общественный транспорт до школы недоступен. Расчётный период обычно составляет один месяц.",
            "example": "45.00",
        },
        "uk": {
            "question": "Якщо ви використовуєте приватний автомобіль, скільки коштує поїздка до школи за розрахунковий період (у євро)?",
            "help": "Заповнюйте це лише якщо громадський транспорт до школи недоступний. Розрахунковий період зазвичай складає один місяць.",
            "example": "45.00",
        },
    },

    "transport_distance_km": {
        "en": {
            "question": "How many kilometres is the one-way journey from home to school?",
            "help": "Write the one-way distance only — not the round trip.",
            "example": "5",
        },
        "fr": {
            "question": "Combien de kilomètres y a-t-il entre le domicile et l'école (aller simple) ?",
            "help": "Écrivez uniquement la distance aller simple, pas l'aller-retour.",
            "example": "5",
        },
        "ar": {
            "question": "كم كيلومتراً المسافة ذهاباً فقط من المنزل إلى المدرسة؟",
            "help": "اكتب المسافة ذهاباً فقط، وليس ذهاباً وإياباً.",
            "example": "5",
        },
        "tr": {
            "question": "Evden okula tek yönlü kaç kilometre?",
            "help": "Sadece tek yönlü mesafeyi yazın, gidiş-dönüş değil.",
            "example": "5",
        },
        "de": {
            "question": "Wie viele Kilometer beträgt die einfache Strecke von zu Hause zur Schule?",
            "help": "Bitte nur die einfache Strecke (nicht Hin- und Rückweg) angeben.",
            "example": "5",
        },
        "sq": {
            "question": "Sa kilometra është rruga vetëm në njërën drejtim nga shtëpia deri në shkollë?",
            "help": "Shkruani vetëm distancën në njërin drejtim, jo vajtje-ardhjen.",
            "example": "5",
        },
        "es": {
            "question": "¿Cuántos kilómetros es el trayecto de ida desde casa hasta la escuela?",
            "help": "Escriba solo la distancia de ida, no la de ida y vuelta.",
            "example": "5",
        },
        "ru": {
            "question": "Сколько километров составляет путь в одну сторону от дома до школы?",
            "help": "Укажите только расстояние в одну сторону, а не туда и обратно.",
            "example": "5",
        },
        "uk": {
            "question": "Скільки кілометрів становить шлях в одну сторону від дому до школи?",
            "help": "Вкажіть лише відстань в одну сторону, а не туди і назад.",
            "example": "5",
        },
    },

    "essen_anbieter": {
        "en": {
            "question": "What is the name of the company or organisation that provides the lunch?",
            "help": "Usually printed on the monthly invoice or the school's lunch registration form.",
        },
        "fr": {
            "question": "Quel est le nom du prestataire qui fournit les repas ?",
            "help": "Généralement indiqué sur la facture mensuelle ou le formulaire d'inscription à la cantine.",
        },
        "ar": {
            "question": "ما هو اسم الشركة أو المنظمة التي توفر وجبات الغداء؟",
        },
        "tr": {
            "question": "Öğle yemeklerini sağlayan şirket veya kuruluşun adı nedir?",
        },
        "de": {
            "question": "Wie heißt der Essensanbieter (Catering-Unternehmen)?",
        },
        "sq": {"question": "Si quhet kompania ose organizata që siguron dreka?"},
        "es": {"question": "¿Cómo se llama la empresa u organización que proporciona los almuerzos?"},
        "ru": {"question": "Как называется компания или организация, обеспечивающая питание?"},
        "uk": {"question": "Як називається компанія або організація, що забезпечує харчування?"},
    },

    "lunch_school_hort": {
        "en": {"question": "Does the child eat lunch at school or after-school care (Hort)?"},
        "fr": {"question": "L'enfant mange-t-il à la cantine de l'école ou de la garderie parascolaire (Hort) ?"},
        "ar": {"question": "هل يتناول الطفل وجبة الغداء في المدرسة أو مرفق رعاية ما بعد الدراسة؟"},
        "tr": {"question": "Çocuk okul yemekhanesinde veya okul sonrası bakım merkezinde (Hort) öğle yemeği yiyor mu?"},
        "de": {"question": "Isst das Kind in der Schule oder im Hort zu Mittag?"},
        "sq": {"question": "A ha fëmija drekë në shkollë ose në kujdesin pas shkollës (Hort)?"},
        "es": {"question": "¿El niño almuerza en la escuela o en el servicio de atención extraescolar (Hort)?"},
        "ru": {"question": "Обедает ли ребёнок в школе или в продлёнке (Hort)?"},
        "uk": {"question": "Чи обідає дитина в школі або в продовженому дні (Hort)?"},
    },

    "lunch_kita_kindertagespflege": {
        "en": {"question": "Does the child eat lunch at a kindergarten (Kita) or with a childminder (Kindertagespflege)?"},
        "fr": {"question": "L'enfant mange-t-il à la crèche (Kita) ou chez une assistante maternelle (Kindertagespflege) ?"},
        "ar": {"question": "هل يتناول الطفل وجبة الغداء في الحضانة أو لدى مربية أطفال؟"},
        "tr": {"question": "Çocuk bir kreşte (Kita) veya çocuk bakıcısında (Kindertagespflege) öğle yemeği yiyor mu?"},
        "de": {"question": "Isst das Kind in einer Kita oder Kindertagespflege zu Mittag?"},
        "sq": {"question": "A ha fëmija drekë në kopsht (Kita) ose me kujdestaren e fëmijëve?"},
        "es": {"question": "¿El niño almuerza en una guardería (Kita) o con una cuidadora de niños?"},
        "ru": {"question": "Обедает ли ребёнок в детском саду (Kita) или у няни (Kindertagespflege)?"},
        "uk": {"question": "Чи обідає дитина в дитячому садку (Kita) або у няні (Kindertagespflege)?"},
    },

    "consent_direct_settlement": {
        "en": {
            "question": "Do you agree that the Jobcenter pays the service provider (school, club, etc.) directly instead of reimbursing you?",
            "help": "This is the standard procedure. The Jobcenter transfers the money directly to the school, lunch provider, or club.",
        },
        "fr": {
            "question": "Acceptez-vous que le Jobcenter paye directement le prestataire (école, club, etc.) au lieu de vous rembourser ?",
            "help": "C'est la procédure standard. Le Jobcenter transfère l'argent directement à l'école, au prestataire de repas ou au club.",
        },
        "ar": {
            "question": "هل توافق على أن يدفع Jobcenter مباشرة لمزود الخدمة (المدرسة، النادي، إلخ) بدلاً من سداده إليك؟",
        },
        "tr": {
            "question": "Jobcenter'ın sizi geri ödemek yerine hizmet sağlayıcıya (okul, kulüp vb.) doğrudan ödeme yapmasını kabul ediyor musunuz?",
        },
        "de": {
            "question": "Stimmen Sie zu, dass das Jobcenter die Leistung direkt mit dem Anbieter abrechnet?",
        },
        "sq": {
            "question": "A jeni dakord që Jobcenter t'i paguajë drejtpërdrejt ofruesit të shërbimit (shkollës, klubit, etj.)?",
        },
        "es": {
            "question": "¿Acepta que el Jobcenter pague directamente al proveedor del servicio (escuela, club, etc.)?",
        },
        "ru": {
            "question": "Согласны ли вы, что Jobcenter будет платить напрямую поставщику услуг (школе, клубу и т.д.)?",
        },
        "uk": {
            "question": "Чи згодні ви, що Jobcenter буде платити безпосередньо постачальнику послуг (школі, клубу тощо)?",
        },
    },

    "ort_datum_antragsteller": {
        "en": {
            "question": "What city and date should appear next to your signature?",
            "help": "Write the city where you are submitting the form, followed by today's date.",
            "example": "Rostock, 06.05.2026",
        },
        "fr": {
            "question": "Quelle ville et quelle date doivent figurer à côté de votre signature ?",
            "help": "Écrivez la ville où vous soumettez le formulaire, suivie de la date d'aujourd'hui.",
            "example": "Rostock, 06.05.2026",
        },
        "ar": {
            "question": "ما هي المدينة والتاريخ اللذان يجب أن يظهرا بجوار توقيعك؟",
            "help": "اكتب المدينة التي تقدم فيها النموذج، تليها تاريخ اليوم.",
            "example": "Rostock, 06.05.2026",
        },
        "tr": {
            "question": "İmzanızın yanında hangi şehir ve tarih görünmeli?",
            "help": "Formu sunduğunuz şehri, ardından bugünün tarihini yazın.",
            "example": "Rostock, 06.05.2026",
        },
        "de": {
            "question": "Welcher Ort und welches Datum stehen neben Ihrer Unterschrift?",
            "help": "Ort, an dem Sie den Antrag einreichen, und das heutige Datum.",
            "example": "Rostock, 06.05.2026",
        },
        "sq": {
            "question": "Cili qytet dhe datë duhet të shfaqen pranë nënshkrimit tuaj?",
            "help": "Shkruani qytetin ku po dorëzoni formularin, pastaj datën e sotme.",
            "example": "Rostock, 06.05.2026",
        },
        "es": {
            "question": "¿Qué ciudad y fecha deben aparecer junto a su firma?",
            "help": "Escriba la ciudad donde presenta el formulario, seguida de la fecha de hoy.",
            "example": "Rostock, 06.05.2026",
        },
        "ru": {
            "question": "Какой город и дата должны быть указаны рядом с вашей подписью?",
            "help": "Напишите город, где вы подаёте заявление, затем сегодняшнюю дату.",
            "example": "Rostock, 06.05.2026",
        },
        "uk": {
            "question": "Яке місто та дата мають бути поряд з вашим підписом?",
            "help": "Напишіть місто, де ви подаєте заявку, потім сьогоднішню дату.",
            "example": "Rostock, 06.05.2026",
        },
    },

    "ort_datum_vertreter": {
        "en": {
            "question": "What city and date should appear next to the legal guardian's signature?",
            "help": "If a legal guardian or representative is signing, write their location and today's date.",
            "example": "Rostock, 06.05.2026",
        },
        "fr": {
            "question": "Quelle ville et quelle date doivent figurer à côté de la signature du représentant légal ?",
            "example": "Rostock, 06.05.2026",
        },
        "ar": {
            "question": "ما هي المدينة والتاريخ اللذان يجب أن يظهرا بجوار توقيع الوصي القانوني؟",
        },
        "tr": {
            "question": "Yasal temsilcinin imzasının yanında hangi şehir ve tarih görünmeli?",
        },
        "de": {
            "question": "Welcher Ort und welches Datum stehen neben der Unterschrift des gesetzlichen Vertreters?",
            "example": "Rostock, 06.05.2026",
        },
        "sq": {
            "question": "Cili qytet dhe datë duhet të shfaqen pranë nënshkrimit të kujdestarit ligjor?",
            "example": "Rostock, 06.05.2026",
        },
        "es": {
            "question": "¿Qué ciudad y fecha deben aparecer junto a la firma del representante legal?",
            "example": "Rostock, 06.05.2026",
        },
        "ru": {
            "question": "Какой город и дата должны стоять рядом с подписью законного представителя?",
            "example": "Rostock, 06.05.2026",
        },
        "uk": {
            "question": "Яке місто та дата мають бути поряд з підписом законного представника?",
            "example": "Rostock, 06.05.2026",
        },
    },

    "benefit_sgb_ii": {
        "en": {
            "question": "Do you currently receive Bürgergeld (basic income support) from the Jobcenter under SGB II?",
            "help": "Check your most recent Jobcenter letter — it will mention 'SGB II' or 'Bürgergeld'.",
        },
        "fr": {
            "question": "Bénéficiez-vous actuellement du Bürgergeld (revenu de base) du Jobcenter au titre du SGB II ?",
        },
        "ar": {
            "question": "هل تتلقى حالياً إعانة Bürgergeld (الدعم الأساسي) من Jobcenter بموجب SGB II؟",
        },
        "tr": {
            "question": "Şu anda Jobcenter'dan SGB II kapsamında Bürgergeld (temel gelir desteği) alıyor musunuz?",
        },
        "de": {
            "question": "Beziehen Sie aktuell Bürgergeld nach SGB II vom Jobcenter?",
        },
        "sq": {
            "question": "A merrni aktualisht Bürgergeld (mbështetje bazë e të ardhurave) nga Jobcenter?",
            "help": "Kontrolloni letrën tuaj të fundit të Jobcenter — do të përmendet 'SGB II' ose 'Bürgergeld'.",
        },
        "es": {
            "question": "¿Recibe actualmente Bürgergeld (prestación básica) del Jobcenter?",
            "help": "Consulte su carta más reciente del Jobcenter — mencionará 'SGB II' o 'Bürgergeld'.",
        },
        "ru": {
            "question": "Получаете ли вы сейчас Bürgergeld (базовое пособие) от Jobcenter?",
            "help": "Проверьте последнее письмо от Jobcenter — там будет упоминание 'SGB II' или 'Bürgergeld'.",
        },
        "uk": {
            "question": "Чи отримуєте ви зараз Bürgergeld (базову допомогу) від Jobcenter?",
            "help": "Перевірте останній лист від Jobcenter — там буде згадка 'SGB II' або 'Bürgergeld'.",
        },
    },

    "benefit_sgb_xii": {
        "en": {
            "question": "Do you receive social welfare payments (Sozialhilfe) from the social welfare office (Sozialamt)?",
            "help": "This is paid by the Sozialamt (social welfare office), not the Jobcenter. Check a letter from the Sozialamt mentioning 'SGB XII' or 'Sozialhilfe'.",
        },
        "fr": {
            "question": "Percevez-vous l'aide sociale (Sozialhilfe) du bureau d'aide sociale (Sozialamt) ?",
            "help": "Cette aide est versée par le Sozialamt, pas le Jobcenter. Vérifiez un courrier du Sozialamt mentionnant 'SGB XII' ou 'Sozialhilfe'.",
        },
        "ar": {
            "question": "هل تتلقى مساعدة اجتماعية (Sozialhilfe) من مكتب الرعاية الاجتماعية (Sozialamt)؟",
            "help": "هذه المساعدة تُدفع من مكتب Sozialamt، وليس من مركز العمل Jobcenter. تحقق من رسالة تذكر 'SGB XII' أو 'Sozialhilfe'.",
        },
        "tr": {
            "question": "Sosyal refah ofisinden (Sozialamt) sosyal yardım (Sozialhilfe) alıyor musunuz?",
            "help": "Bu yardım Jobcenter değil, Sozialamt tarafından ödenir. 'SGB XII' veya 'Sozialhilfe' yazan bir Sozialamt mektubuna bakın.",
        },
        "de": {
            "question": "Beziehen Sie Sozialhilfe nach SGB XII vom Sozialamt?",
            "help": "Die Sozialhilfe wird vom Sozialamt gezahlt, nicht vom Jobcenter. Prüfen Sie einen Brief des Sozialamts mit dem Begriff 'SGB XII' oder 'Sozialhilfe'.",
        },
        "es": {
            "question": "¿Recibe asistencia social (Sozialhilfe) de la oficina de bienestar social (Sozialamt)?",
            "help": "Esta ayuda la paga el Sozialamt, no el Jobcenter. Busque una carta del Sozialamt que mencione 'SGB XII' o 'Sozialhilfe'.",
        },
        "sq": {
            "question": "A merrni ndihmë sociale (Sozialhilfe) nga zyra e mirëqenies sociale (Sozialamt)?",
            "help": "Kjo ndihmë paguhet nga Sozialamt, jo nga Jobcenter. Kontrolloni një letër nga Sozialamt që përmend 'SGB XII' ose 'Sozialhilfe'.",
        },
        "ru": {
            "question": "Получаете ли вы социальную помощь (Sozialhilfe) от службы социального обеспечения (Sozialamt)?",
            "help": "Эта помощь выплачивается Sozialamt, а не Jobcenter. Проверьте письмо от Sozialamt с упоминанием 'SGB XII' или 'Sozialhilfe'.",
        },
        "uk": {
            "question": "Чи отримуєте ви соціальну допомогу (Sozialhilfe) від служби соціального забезпечення (Sozialamt)?",
            "help": "Цю допомогу виплачує Sozialamt, а не Jobcenter. Перевірте лист від Sozialamt з позначкою 'SGB XII' або 'Sozialhilfe'.",
        },
    },

    "benefit_kinderzuschlag": {
        "en": {"question": "Do you receive the child supplement (Kinderzuschlag) from the Familienkasse?"},
        "fr": {"question": "Percevez-vous le supplément pour enfant (Kinderzuschlag) de la Familienkasse ?"},
        "ar": {"question": "هل تتلقى مكمّل الطفل (Kinderzuschlag) من Familienkasse؟"},
        "tr": {"question": "Familienkasse'dan çocuk ödeneği (Kinderzuschlag) alıyor musunuz?"},
        "de": {"question": "Beziehen Sie Kinderzuschlag von der Familienkasse?"},
        "sq": {"question": "A merrni shtesën për fëmijë (Kinderzuschlag) nga Familienkasse?"},
        "es": {"question": "¿Recibe el suplemento por hijo (Kinderzuschlag) de la Familienkasse?"},
        "ru": {"question": "Получаете ли вы детское пособие (Kinderzuschlag) от Familienkasse?"},
        "uk": {"question": "Чи отримуєте ви дитячу надбавку (Kinderzuschlag) від Familienkasse?"},
    },

    "benefit_wohngeld": {
        "en": {"question": "Do you receive housing benefit (Wohngeld) from your local authority?"},
        "fr": {"question": "Bénéficiez-vous d'une aide au logement (Wohngeld) de votre autorité locale ?"},
        "ar": {"question": "هل تتلقى إعانة السكن (Wohngeld) من السلطة المحلية؟"},
        "tr": {"question": "Yerel otoriteden konut yardımı (Wohngeld) alıyor musunuz?"},
        "de": {"question": "Beziehen Sie Wohngeld von der Wohngeldstelle?"},
        "sq": {"question": "A merrni ndihmë strehimi (Wohngeld) nga autoriteti lokal?"},
        "es": {"question": "¿Recibe ayuda para la vivienda (Wohngeld) de su autoridad local?"},
        "ru": {"question": "Получаете ли вы жилищное пособие (Wohngeld) от местных органов власти?"},
        "uk": {"question": "Чи отримуєте ви житлову допомогу (Wohngeld) від місцевих органів влади?"},
    },

    "benefit_asylbewerberleistungsgesetz": {
        "en": {"question": "Do you receive benefits under the Asylum Seekers' Benefits Act (AsylbLG)?"},
        "fr": {"question": "Bénéficiez-vous de prestations au titre de la loi sur les prestations pour demandeurs d'asile (AsylbLG) ?"},
        "ar": {"question": "هل تتلقى مساعدات بموجب قانون استحقاقات طالبي اللجوء (AsylbLG)؟"},
        "tr": {"question": "Sığınmacılara Sosyal Yardım Kanunu (AsylbLG) kapsamında yardım alıyor musunuz?"},
        "de": {"question": "Erhalten Sie Leistungen nach dem Asylbewerberleistungsgesetz?"},
        "sq": {"question": "A merrni përfitime sipas Ligjit për Përfitimet e Azilkërkuesve (AsylbLG)?"},
        "es": {"question": "¿Recibe prestaciones en virtud de la Ley de Prestaciones para Solicitantes de Asilo (AsylbLG)?"},
        "ru": {"question": "Получаете ли вы льготы по Закону о льготах для просителей убежища (AsylbLG)?"},
        "uk": {"question": "Чи отримуєте ви виплати за Законом про допомогу шукачам притулку (AsylbLG)?"},
    },

    "benefit_sonstige": {
        "en": {
            "question": "Do you receive any other benefits not listed above? If yes, please specify.",
            "help": "Write the name of the benefit in the space provided on the printed form.",
        },
        "fr": {
            "question": "Percevez-vous d'autres prestations non mentionnées ci-dessus ? Si oui, précisez.",
        },
        "ar": {
            "question": "هل تتلقى أي إعانات أخرى غير المذكورة أعلاه؟ إذا كانت الإجابة نعم، يرجى التوضيح.",
        },
        "tr": {
            "question": "Yukarıda belirtilmeyen başka yardımlar alıyor musunuz? Evet ise belirtiniz.",
        },
        "de": {
            "question": "Beziehen Sie andere, oben nicht genannte Leistungen? Wenn ja, bitte angeben.",
        },
        "sq": {
            "question": "A merrni ndonjë përfitim tjetër të palista më sipër? Nëse po, ju lutemi specifikoni.",
        },
        "es": {
            "question": "¿Recibe alguna otra prestación no mencionada anteriormente? En caso afirmativo, especifique.",
        },
        "ru": {
            "question": "Получаете ли вы какие-либо другие пособия, не указанные выше? Если да, укажите их.",
        },
        "uk": {
            "question": "Чи отримуєте ви будь-які інші виплати, не зазначені вище? Якщо так, вкажіть їх.",
        },
    },

    "lunch_sonstige_angaben": {
        "en": {"question": "Do you have any other information about the lunch arrangement?"},
        "fr": {"question": "Avez-vous d'autres informations à fournir sur les repas ?"},
        "ar": {"question": "هل لديك أي معلومات إضافية حول ترتيب وجبات الغداء؟"},
        "tr": {"question": "Öğle yemeği düzenlemesi hakkında başka bilgi vermek ister misiniz?"},
        "de": {"question": "Haben Sie sonstige Angaben zum Mittagessen?"},
        "sq": {"question": "A keni informacion tjetër për rregullimin e drekës?"},
        "es": {"question": "¿Tiene alguna otra información sobre el servicio de comedor?"},
        "ru": {"question": "Есть ли у вас дополнительная информация об организации питания?"},
        "uk": {"question": "Чи є у вас додаткова інформація щодо організації харчування?"},
    },
}


# ── Verified question text by label (original_label match) ───────────────────
# Used for fields from non-template PDFs where original_label is a common German word.
# Keyed by lowercase original_label (after stripping trailing numbers).

VERIFIED_BY_LABEL: dict[str, dict[str, dict[str, str]]] = {
    "tag": {
        "en": {
            "question": "What day of the month are you filling out this form?",
            "help": "Write only the day number (not the full date).",
            "example": "If today is 6 May 2026, write: 6",
        },
        "fr": {
            "question": "Quel jour du mois remplissez-vous ce formulaire ?",
            "help": "Écrivez uniquement le numéro du jour.",
            "example": "Si aujourd'hui c'est le 6 mai 2026, écrivez : 6",
        },
        "ar": {
            "question": "ما هو يوم الشهر الذي تملأ فيه هذا النموذج؟",
            "help": "اكتب رقم اليوم فقط.",
            "example": "إذا كان اليوم 6 مايو 2026، اكتب: 6",
        },
        "tr": {
            "question": "Bu formu doldurduğunuz ayın kaçıdır?",
            "help": "Sadece gün numarasını yazın.",
            "example": "Bugün 6 Mayıs 2026 ise yazın: 6",
        },
        "de": {
            "question": "An welchem Tag des Monats füllen Sie dieses Formular aus?",
            "help": "Tragen Sie nur die Tageszahl ein.",
            "example": "Heute ist der 6. Mai 2026 → eintragen: 6",
        },
        "es": {
            "question": "¿Qué día del mes estás rellenando este formulario?",
            "example": "Si hoy es 6 de mayo de 2026, escribe: 6",
        },
        "sq": {
            "question": "Cilin ditë të muajit po plotësoni këtë formular?",
            "example": "Nëse sot është 6 maj 2026, shkruani: 6",
        },
        "ru": {
            "question": "Какое число месяца вы заполняете эту форму?",
            "example": "Если сегодня 6 мая 2026, напишите: 6",
        },
        "uk": {
            "question": "Яке число місяця ви заповнюєте цю форму?",
            "example": "Якщо сьогодні 6 травня 2026, напишіть: 6",
        },
    },

    "monat": {
        "en": {
            "question": "What month are you filling out this form?",
            "help": "Write the month number (1–12) or the month name.",
            "example": "If today is 6 May 2026, write: 5 or May",
        },
        "fr": {
            "question": "Quel mois remplissez-vous ce formulaire ?",
            "help": "Écrivez le numéro du mois (1 à 12) ou le nom du mois.",
            "example": "Si aujourd'hui c'est le 6 mai 2026, écrivez : 5 ou mai",
        },
        "ar": {
            "question": "ما هو الشهر الذي تملأ فيه هذا النموذج؟",
            "help": "اكتب رقم الشهر (1–12) أو اسم الشهر.",
            "example": "إذا كان اليوم 6 مايو 2026، اكتب: 5 أو مايو",
        },
        "tr": {
            "question": "Bu formu doldurduğunuz ay kaçıdır?",
            "help": "Ay numarasını (1–12) veya ay adını yazın.",
            "example": "Bugün 6 Mayıs 2026 ise yazın: 5 veya Mayıs",
        },
        "de": {
            "question": "In welchem Monat füllen Sie dieses Formular aus?",
            "help": "Tragen Sie die Monatszahl (1–12) oder den Monatsnamen ein.",
            "example": "Heute ist Mai 2026 → eintragen: 5 oder Mai",
        },
        "es": {
            "question": "¿En qué mes estás rellenando este formulario?",
            "example": "Si hoy es 6 de mayo de 2026, escribe: 5 o mayo",
        },
        "sq": {
            "question": "Cilin muaj po plotësoni këtë formular?",
            "example": "Nëse sot është 6 maj 2026, shkruani: 5 ose maj",
        },
        "ru": {
            "question": "В каком месяце вы заполняете эту форму?",
            "example": "Если сегодня 6 мая 2026, напишите: 5 или май",
        },
        "uk": {
            "question": "В якому місяці ви заповнюєте цю форму?",
            "example": "Якщо сьогодні 6 травня 2026, напишіть: 5 або травень",
        },
    },

    "jahr": {
        "en": {
            "question": "What year are you filling out this form?",
            "help": "Write the full 4-digit year.",
            "example": "2026",
        },
        "fr": {
            "question": "En quelle année remplissez-vous ce formulaire ?",
            "help": "Écrivez l'année complète (4 chiffres).",
            "example": "2026",
        },
        "ar": {
            "question": "ما هو العام الذي تملأ فيه هذا النموذج؟",
            "help": "اكتب السنة الكاملة المكونة من 4 أرقام.",
            "example": "2026",
        },
        "tr": {
            "question": "Bu formu doldurduğunuz yıl nedir?",
            "help": "4 haneli tam yılı yazın.",
            "example": "2026",
        },
        "de": {
            "question": "In welchem Jahr füllen Sie dieses Formular aus?",
            "help": "Tragen Sie die vierstellige Jahreszahl ein.",
            "example": "2026",
        },
        "es": {"question": "¿En qué año estás rellenando este formulario?", "example": "2026"},
        "sq": {"question": "Cilin vit po plotësoni këtë formular?", "example": "2026"},
        "ru": {"question": "В каком году вы заполняете эту форму?", "example": "2026"},
        "uk": {"question": "В якому році ви заповнюєте цю форму?", "example": "2026"},
    },

    "startort": {
        "en": {
            "question": "What is the starting location of the journey?",
            "help": "Write the address or name of the place where the journey begins.",
        },
        "fr": {
            "question": "Quel est le lieu de départ du trajet ?",
            "help": "Écrivez l'adresse ou le nom du lieu de départ.",
        },
        "ar": {
            "question": "ما هو مكان انطلاق الرحلة؟",
            "help": "اكتب عنوان أو اسم المكان الذي تبدأ منه الرحلة.",
        },
        "tr": {
            "question": "Yolculuğun başlangıç noktası nedir?",
            "help": "Yolculuğun başladığı yerin adresini veya adını yazın.",
        },
        "de": {
            "question": "Was ist der Startort der Fahrt?",
            "help": "Tragen Sie die Adresse oder den Namen des Startorts ein.",
        },
        "sq": {
            "question": "Cili është vendi i nisjes së udhëtimit?",
            "help": "Shkruani adresën ose emrin e vendit ku fillon udhëtimi.",
        },
        "es": {"question": "¿Cuál es el lugar de partida del viaje?"},
        "ru": {"question": "Какое место отправления поездки?"},
        "uk": {"question": "Яке місце відправлення поїздки?"},
    },

    "zielort": {
        "en": {
            "question": "What is the destination of the journey?",
            "help": "Write the address or name of the destination.",
        },
        "fr": {
            "question": "Quelle est la destination du trajet ?",
            "help": "Écrivez l'adresse ou le nom de la destination.",
        },
        "ar": {
            "question": "ما هي وجهة الرحلة؟",
            "help": "اكتب عنوان أو اسم وجهة الرحلة.",
        },
        "tr": {
            "question": "Yolculuğun varış noktası nedir?",
            "help": "Varış yerinin adresini veya adını yazın.",
        },
        "de": {
            "question": "Was ist der Zielort der Fahrt?",
            "help": "Tragen Sie die Adresse oder den Namen des Zielorts ein.",
        },
        "sq": {
            "question": "Cili është destinacioni i udhëtimit?",
            "help": "Shkruani adresën ose emrin e destinacionit.",
        },
        "es": {"question": "¿Cuál es el destino del viaje?"},
        "ru": {"question": "Какое место назначения поездки?"},
        "uk": {"question": "Яке місце призначення поїздки?"},
    },
}


def lookup_verified(field_id: str, original_label: str, locale: str) -> dict[str, str] | None:
    """
    Return verified question data for a field, or None if not available.

    Result dict may contain: question, help, example, format.
    Checks field_id first, then normalized original_label.
    Falls back locale → "en" within the matched entry.

    For Tier-A locales (en/de/fr/ar/tr/sq) callers should prefer
    `lookup_verified_strict()` so missing-locale gaps surface as a
    quality-report signal rather than hiding behind a silent English
    fallback. This function keeps the legacy permissive behavior for
    backwards compatibility with the per-field pre-resolution path.
    """
    # 1. Check by field_id (exact match)
    entry = VERIFIED_BY_FIELD_ID.get(field_id)
    if entry:
        return entry.get(locale) or entry.get("en")

    # 2. Check by normalized label (lowercase, strip trailing number)
    import re
    normalized = re.sub(r"\s+\d+$", "", original_label.strip()).strip().lower()
    entry = VERIFIED_BY_LABEL.get(normalized)
    if entry:
        return entry.get(locale) or entry.get("en")

    return None


def lookup_verified_strict(field_id: str, original_label: str, locale: str) -> dict[str, str] | None:
    """
    Strict variant: returns the verified entry only if the requested locale
    is actually present. Used by the locale-quality reporter to detect
    Tier-A coverage gaps. Returns None when:
      - the field has no verified entry at all, or
      - the entry exists but lacks `locale`.
    """
    entry = VERIFIED_BY_FIELD_ID.get(field_id)
    if entry and locale in entry:
        return entry[locale]

    import re
    normalized = re.sub(r"\s+\d+$", "", original_label.strip()).strip().lower()
    entry = VERIFIED_BY_LABEL.get(normalized)
    if entry and locale in entry:
        return entry[locale]

    return None


def get_all_locales_for_field(field_id: str, original_label: str) -> dict[str, dict[str, str]]:
    """
    Return the full {locale: {question, help, ...}} mapping for a verified field.
    Empty dict if the field has no verified entry. Used to pre-fill
    FieldDefinition.question with every Tier-A locale at once so the
    frontend can switch language without reprocessing.
    """
    entry = VERIFIED_BY_FIELD_ID.get(field_id)
    if entry:
        return entry
    import re
    normalized = re.sub(r"\s+\d+$", "", original_label.strip()).strip().lower()
    entry = VERIFIED_BY_LABEL.get(normalized)
    if entry:
        return entry
    return {}
