/**
 * Centralized UI i18n table.
 *
 * Every user-facing string in the app should resolve through `t(key, locale)`.
 * Tier-A locales (en, de, fr, ar, tr, sq) MUST be populated for every key.
 * Tier-B locales (es, fa, ru, uk) are best-effort and fall back to English
 * when missing — this is acceptable per spec.
 *
 * ⚠ Do NOT add inline locale ternaries (`locale === "de" ? ... : ...`) in
 * components or pages. Add the key here and call `t(key, locale)`.
 */
export const TIER_A_LOCALES = ["en", "de", "fr", "ar", "tr", "sq"] as const;
export const SUPPORTED_LOCALES = [
  "en", "de", "fr", "ar", "tr", "sq", "es", "fa", "ru", "uk",
] as const;

export type Locale = typeof SUPPORTED_LOCALES[number];

type Dict = Record<string, string>;

const STRINGS: Record<string, Dict> = {
  // ── Landing page ─────────────────────────────────────────────────────────
  "landing.tagline":            {
    en: "Form assistance · مساعدة استمارات · Form yardımı",
    de: "Formularhilfe · مساعدة استمارات · Form yardımı",
    fr: "Aide aux formulaires · مساعدة استمارات · Form yardımı",
    ar: "مساعدة استمارات · Form assistance · Form yardımı",
    tr: "Form yardımı · Form assistance · مساعدة استمارات",
    sq: "Ndihmë me formularë · Form assistance · مساعدة استمارات",
  },
  "landing.select_language":    {
    en: "Select your language / اختر لغتك / Dilinizi seçin",
    de: "Sprache auswählen / اختر لغتك / Dilinizi seçin",
    fr: "Choisissez votre langue / اختر لغتك / Dilinizi seçin",
    ar: "اختر لغتك / Select your language / Dilinizi seçin",
    tr: "Dilinizi seçin / Select your language / اختر لغتك",
    sq: "Zgjidhni gjuhën tuaj / Select your language / اختر لغتك",
  },
  "landing.start":              { en: "Start →", de: "Starten →", fr: "Commencer →", ar: "ابدأ →", tr: "Başla →", sq: "Fillo →" },
  "landing.disclaimer":         {
    en: "This is a form completion tool. We provide no legal advice.",
    de: "Dies ist eine Formular-Ausfüllhilfe. Wir geben keine Rechtsberatung.",
    fr: "Ceci est un outil d'aide au remplissage de formulaires. Nous ne fournissons aucun conseil juridique.",
    ar: "هذه أداة لمساعدتك في تعبئة الاستمارات فقط. لا نقدم أي استشارات قانونية.",
    tr: "Bu yalnızca bir form doldurma aracıdır. Hukuki tavsiye vermiyoruz.",
    sq: "Ky është një vegël për të plotësuar formularë. Nuk ofrojmë këshilla ligjore.",
  },

  // Saved-form card
  "saved.title":                { en: "Saved form", de: "Gespeichertes Formular", fr: "Formulaire enregistré", ar: "نموذج محفوظ", tr: "Kaydedilmiş form", sq: "Formular i ruajtur" },
  "saved.questions_answered":   { en: "questions answered", de: "Fragen beantwortet", fr: "questions répondues", ar: "أسئلة تمت الإجابة عنها", tr: "soru yanıtlandı", sq: "pyetje të përgjigjura" },
  "saved.missing":              { en: "missing", de: "fehlen", fr: "manquantes", ar: "مفقودة", tr: "eksik", sq: "mungojnë" },
  "saved.saved_at":             { en: "Saved", de: "Gespeichert", fr: "Enregistré", ar: "تم الحفظ", tr: "Kaydedildi", sq: "U ruajt" },
  "saved.continue":             { en: "Continue filling in →", de: "Weiter ausfüllen →", fr: "Continuer le remplissage →", ar: "متابعة التعبئة ←", tr: "Doldurmaya devam et →", sq: "Vazhdo plotësimin →" },
  "saved.delete":               { en: "Delete saved form", de: "Gespeichertes Formular löschen", fr: "Supprimer le formulaire enregistré", ar: "حذف النموذج المحفوظ", tr: "Kaydedilen formu sil", sq: "Fshi formularin e ruajtur" },
  "saved.local_only":           { en: "Saved only on this device/browser.", de: "Nur auf diesem Gerät/Browser gespeichert.", fr: "Enregistré uniquement sur cet appareil/navigateur.", ar: "محفوظ فقط على هذا الجهاز/المتصفح.", tr: "Yalnızca bu cihaz/tarayıcıda kaydedildi.", sq: "Ruajtur vetëm në këtë pajisje/shfletues." },

  // Expired form card
  "expired.title":              { en: "Saved form expired", de: "Gespeichertes Formular abgelaufen", fr: "Formulaire enregistré expiré", ar: "انتهت صلاحية النموذج المحفوظ", tr: "Kaydedilen form süresi doldu", sq: "Formulari i ruajtur ka skaduar" },
  "expired.body":               {
    en: "For privacy reasons, saved forms expire after 4 hours. Please re-upload the PDF.",
    de: "Aus Datenschutzgründen laufen gespeicherte Formulare nach 4 Stunden ab. Bitte laden Sie das PDF erneut hoch.",
    fr: "Pour des raisons de confidentialité, les formulaires enregistrés expirent après 4 heures. Veuillez retéléverser le PDF.",
    ar: "لأسباب تتعلق بالخصوصية، تنتهي صلاحية النماذج المحفوظة بعد 4 ساعات. يرجى إعادة رفع ملف PDF.",
    tr: "Gizlilik nedeniyle kaydedilen formlar 4 saat sonra sona erer. Lütfen PDF'yi tekrar yükleyin.",
    sq: "Për arsye privatësie, formularët e ruajtur skadojnë pas 4 orësh. Ju lutemi ringarkoni PDF-në.",
  },
  "expired.reupload":           { en: "Re-upload PDF", de: "Erneut hochladen", fr: "Retéléverser le PDF", ar: "إعادة الرفع", tr: "Tekrar yükle", sq: "Ringarko PDF-në" },
  "expired.delete":             { en: "Delete", de: "Löschen", fr: "Supprimer", ar: "حذف", tr: "Sil", sq: "Fshi" },

  // Start-new modal
  "modal.start_new.title":      { en: "Start a new form?", de: "Neues Formular starten?", fr: "Commencer un nouveau formulaire ?", ar: "بدء نموذج جديد؟", tr: "Yeni form başlatılsın mı?", sq: "Të nis një formular të ri?" },
  "modal.start_new.body":       {
    en: "Starting a new form will delete the saved form on this device.",
    de: "Ein neues Formular zu starten löscht das gespeicherte Formular auf diesem Gerät.",
    fr: "Commencer un nouveau formulaire supprimera le formulaire enregistré sur cet appareil.",
    ar: "سيؤدي بدء نموذج جديد إلى حذف النموذج المحفوظ على هذا الجهاز.",
    tr: "Yeni bir form başlatmak bu cihazdaki kaydedilmiş formu silecek.",
    sq: "Nisja e një formulari të ri do të fshijë formularin e ruajtur në këtë pajisje.",
  },
  "modal.start_new.confirm":    { en: "Yes, start new", de: "Ja, neu starten", fr: "Oui, recommencer", ar: "نعم، ابدأ من جديد", tr: "Evet, yeniden başlat", sq: "Po, fillo nga e para" },
  "common.cancel":              { en: "Cancel", de: "Abbrechen", fr: "Annuler", ar: "إلغاء", tr: "İptal", sq: "Anuloni" },
  "common.back":                { en: "Back", de: "Zurück", fr: "Retour", ar: "رجوع", tr: "Geri", sq: "Mbrapa" },

  // ── Header ──────────────────────────────────────────────────────────────
  "header.tagline":             {
    en: "Form assistance · No legal advice",
    de: "Formularhilfe · Keine Rechtsberatung",
    fr: "Aide aux formulaires · Aucun conseil juridique",
    ar: "مساعدة استمارات · لا توجد استشارات قانونية",
    tr: "Form yardımı · Hukuki tavsiye yok",
    sq: "Ndihmë me formularë · Pa këshilla ligjore",
  },

  // ── Step progress labels ────────────────────────────────────────────────
  "step.upload":                { en: "Upload", de: "Hochladen", fr: "Téléverser", ar: "تحميل", tr: "Yükle", sq: "Ngarko" },
  "step.questions":             { en: "Questions", de: "Fragen", fr: "Questions", ar: "أسئلة", tr: "Sorular", sq: "Pyetjet" },
  "step.review":                { en: "Review", de: "Überprüfen", fr: "Vérifier", ar: "مراجعة", tr: "İncele", sq: "Rishikim" },
  "step.download":              { en: "Download", de: "Herunterladen", fr: "Télécharger", ar: "تنزيل", tr: "İndir", sq: "Shkarko" },

  // ── Upload page ─────────────────────────────────────────────────────────
  "upload.title":               { en: "Upload your PDF form", de: "PDF-Formular hochladen", fr: "Téléversez votre formulaire PDF", ar: "ارفع نموذج PDF", tr: "PDF formunuzu yükleyin", sq: "Ngarkoni formularin tuaj PDF" },
  "upload.instr":               {
    en: "Drop any fillable PDF — fields are read directly from your document.",
    de: "Beliebiges ausfüllbares PDF ablegen — Felder werden direkt aus Ihrem Dokument gelesen.",
    fr: "Déposez n'importe quel PDF remplissable — les champs sont lus directement depuis votre document.",
    ar: "أسقط أي نموذج PDF — تُقرأ الحقول مباشرة من مستندك.",
    tr: "Doldurulabilir PDF'yi bırakın — alanlar doğrudan belgenizden okunur.",
    sq: "Lëshoni një PDF të plotësueshëm — fushat lexohen drejtpërdrejt nga dokumenti juaj.",
  },
  "upload.supported":           {
    en: "Any fillable PDF (government forms, contracts, applications…)",
    de: "Jedes ausfüllbare PDF (Behördenformulare, Verträge, Anträge…)",
    fr: "Tout PDF remplissable (formulaires administratifs, contrats, demandes…)",
    ar: "أي نموذج PDF قابل للتعبئة (نماذج حكومية، عقود، طلبات…)",
    tr: "Her doldurulabilir PDF (resmi formlar, sözleşmeler, başvurular…)",
    sq: "Çdo PDF i plotësueshëm (formularë qeveritarë, kontrata, aplikime…)",
  },
  "upload.processing":          { en: "Reading your PDF…", de: "PDF wird gelesen…", fr: "Lecture de votre PDF…", ar: "جارٍ قراءة ملف PDF…", tr: "PDF okunuyor…", sq: "Po lexohet PDF-ja juaj…" },
  "upload.proc_sub":            {
    en: "Extracting fields and translating questions. This takes a few seconds.",
    de: "Felder werden extrahiert und Fragen übersetzt. Dies dauert ein paar Sekunden.",
    fr: "Extraction des champs et traduction des questions. Cela prend quelques secondes.",
    ar: "جارٍ استخراج الحقول وترجمة الأسئلة. يستغرق هذا بضع ثوانٍ.",
    tr: "Alanlar çıkarılıyor ve sorular çevriliyor. Bu birkaç saniye sürer.",
    sq: "Po nxirren fushat dhe po përkthehen pyetjet. Kjo zgjat pak sekonda.",
  },
  "upload.no_fields":           { en: "No fillable fields found in this PDF.", de: "Keine ausfüllbaren Felder in diesem PDF gefunden.", fr: "Aucun champ remplissable trouvé dans ce PDF.", ar: "لم يتم العثور على حقول قابلة للتعبئة في ملف PDF هذا.", tr: "Bu PDF'de doldurulabilir alan bulunamadı.", sq: "Nuk u gjetën fusha të plotësueshme në këtë PDF." },
  "upload.continue_saved":      { en: "Continue saved form", de: "Gespeichertes Formular fortsetzen", fr: "Continuer le formulaire enregistré", ar: "متابعة النموذج المحفوظ", tr: "Kaydedilen forma devam et", sq: "Vazhdo formularin e ruajtur" },
  "upload.continue":            { en: "Continue", de: "Weiter", fr: "Continuer", ar: "متابعة", tr: "Devam et", sq: "Vazhdo" },
  "upload.upload_pdf":          { en: "Upload PDF", de: "PDF hochladen", fr: "Téléverser un PDF", ar: "رفع ملف PDF", tr: "PDF yükle", sq: "Ngarko PDF" },
  "upload.upload_pdf_desc":     {
    en: "Upload an official PDF form from your device.",
    de: "Offizielles PDF-Formular von Ihrem Gerät hochladen.",
    fr: "Téléversez un formulaire PDF officiel depuis votre appareil.",
    ar: "ارفع نموذج PDF الرسمي من جهازك.",
    tr: "Cihazınızdan resmi PDF formu yükleyin.",
    sq: "Ngarkoni një formular zyrtar PDF nga pajisja juaj.",
  },
  "upload.scan_doc":            { en: "Scan document", de: "Dokument scannen", fr: "Scanner un document", ar: "مسح المستند", tr: "Belge tara", sq: "Skano dokument" },
  "upload.scan_desc":           {
    en: "Use your camera to scan a paper form page by page.",
    de: "Papierformular mit der Kamera Seite für Seite scannen.",
    fr: "Utilisez votre caméra pour scanner un formulaire papier page par page.",
    ar: "امسح نموذجًا ورقيًا بالكاميرا صفحةً بصفحة.",
    tr: "Kameranızla kağıt formu sayfa sayfa tarayın.",
    sq: "Përdorni kamerën për të skanuar një formular letre faqe pas faqe.",
  },
  "upload.scan_warning":        {
    en: "Scanning is experimental and may not work on all devices.",
    de: "Scan ist experimentell und funktioniert möglicherweise nicht auf allen Geräten.",
    fr: "Le scan est expérimental et peut ne pas fonctionner sur tous les appareils.",
    ar: "المسح تجريبي وقد لا يعمل على جميع الأجهزة.",
    tr: "Tarama deneyseldir ve tüm cihazlarda çalışmayabilir.",
    sq: "Skanimi është eksperimental dhe mund të mos funksionojë në të gjitha pajisjet.",
  },
  "upload.try_again":           { en: "Try again", de: "Erneut versuchen", fr: "Réessayer", ar: "حاول مرة أخرى", tr: "Tekrar dene", sq: "Provo përsëri" },
  "upload.api_unavailable":     {
    en: "The service is unavailable right now. Please try again later.",
    de: "Der Dienst ist gerade nicht erreichbar. Bitte versuchen Sie es später erneut.",
    fr: "Le service est actuellement indisponible. Veuillez réessayer plus tard.",
    ar: "الخدمة غير متاحة الآن. يرجى المحاولة لاحقًا.",
    tr: "Hizmet şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin.",
    sq: "Shërbimi nuk është i disponueshëm tani. Provoni më vonë.",
  },
  "upload.continue_to_questions": { en: "Continue to Questions →", de: "Weiter zu den Fragen →", fr: "Passer aux questions →", ar: "المتابعة إلى الأسئلة ←", tr: "Sorulara devam et →", sq: "Kalo te pyetjet →" },
  "upload.upload_different":    { en: "Upload different PDF", de: "Anderes PDF hochladen", fr: "Téléverser un autre PDF", ar: "رفع ملف PDF آخر", tr: "Başka PDF yükle", sq: "Ngarko një PDF tjetër" },
  "upload.leave_title":         { en: "Leave page?", de: "Seite verlassen?", fr: "Quitter la page ?", ar: "مغادرة الصفحة؟", tr: "Sayfadan ayrılınsın mı?", sq: "Të largohesh nga faqja?" },
  "upload.leave_body":          {
    en: "The PDF is still being processed. If you leave now, progress will be lost.",
    de: "Das PDF wird noch verarbeitet. Wenn Sie jetzt gehen, geht der Fortschritt verloren.",
    fr: "Le PDF est encore en cours de traitement. Si vous partez maintenant, votre progression sera perdue.",
    ar: "لا يزال ملف PDF قيد المعالجة. إذا غادرت الآن، ستفقد التقدم.",
    tr: "PDF hâlâ işleniyor. Şimdi ayrılırsanız ilerleme kaybolacak.",
    sq: "PDF-ja është ende duke u përpunuar. Nëse largoheni tani, përparimi do të humbasë.",
  },
  "upload.leave_anyway":        { en: "Leave anyway", de: "Trotzdem verlassen", fr: "Quitter quand même", ar: "المغادرة على أي حال", tr: "Yine de ayrıl", sq: "Largohu gjithsesi" },
  "upload.stay":                { en: "Stay", de: "Bleiben", fr: "Rester", ar: "البقاء", tr: "Kal", sq: "Rri" },

  // ── Questions page ──────────────────────────────────────────────────────
  "q.loading":                  { en: "Reading your document…", de: "Dokument wird gelesen…", fr: "Lecture de votre document…", ar: "جارٍ قراءة مستندك…", tr: "Belgeniz okunuyor…", sq: "Po lexohet dokumenti juaj…" },
  "q.next":                     { en: "Next →", de: "Weiter →", fr: "Suivant →", ar: "التالي →", tr: "İleri →", sq: "Tjetër →" },
  "q.question_n_of_m":          {
    en: "Question {n} of {m}",
    de: "Frage {n} von {m}",
    fr: "Question {n} sur {m}",
    ar: "سؤال {n} من {m}",
    tr: "Soru {n} / {m}",
    sq: "Pyetja {n} nga {m}",
  },
  "q.missing":                  { en: "missing", de: "fehlend", fr: "manquant", ar: "مفقود", tr: "eksik", sq: "mungon" },
  "q.save_btn":                 { en: "Save for later", de: "Speichern", fr: "Enregistrer", ar: "حفظ لوقت لاحق", tr: "Sonra devam et", sq: "Ruaj" },
  "q.new_doc_btn":              { en: "New document", de: "Neues Dokument", fr: "Nouveau document", ar: "مستند جديد", tr: "Yeni belge", sq: "Dokument i ri" },
  "q.saved_msg":                { en: "Saved on this device.", de: "Auf diesem Gerät gespeichert.", fr: "Enregistré sur cet appareil.", ar: "تم الحفظ على هذا الجهاز.", tr: "Bu cihaza kaydedildi.", sq: "Ruajtur në këtë pajisje." },
  "q.saved_warn":               { en: "Only saved locally — do not use on a shared computer.", de: "Nur lokal gespeichert — nicht auf einem gemeinsam genutzten Computer verwenden.", fr: "Enregistré localement uniquement — ne pas utiliser sur un ordinateur partagé.", ar: "محفوظ محليًا فقط — لا تستخدمه على جهاز مشترك.", tr: "Yalnızca yerel olarak kaydedildi — paylaşılan bir bilgisayarda kullanmayın.", sq: "Ruajtur vetëm lokalisht — mos përdorni në një kompjuter të përbashkët." },
  "q.modal_title":              { en: "Start a new document?", de: "Neues Dokument starten?", fr: "Commencer un nouveau document ?", ar: "بدء مستند جديد؟", tr: "Yeni bir belge?", sq: "Të nis një dokument të ri?" },
  "q.modal_msg":                { en: "Your current answers will be lost. Save first if you want to return to this form.", de: "Ihre aktuellen Antworten gehen verloren. Speichern Sie zuerst.", fr: "Vos réponses actuelles seront perdues. Enregistrez d'abord.", ar: "ستُفقد إجاباتك الحالية. احفظ أولاً.", tr: "Mevcut yanıtlarınız kaybolacak. Önce kaydedin.", sq: "Përgjigjet tuaja aktuale do të humbasin. Ruajini fillimisht." },
  "q.save_first":               { en: "Save first, then start new", de: "Erst speichern, dann neu", fr: "Enregistrer d'abord, puis nouveau", ar: "احفظ أولاً ثم ابدأ", tr: "Önce kaydet, sonra başla", sq: "Ruaj fillimisht, pastaj nis të ri" },
  "q.start_new":                { en: "Start new (don't save)", de: "Neu starten (nicht speichern)", fr: "Nouveau (sans enregistrer)", ar: "ابدأ جديداً (بدون حفظ)", tr: "Kaydetmeden başla", sq: "Nis të ri (pa ruajtur)" },
  "q.continue_now":             { en: "Continue answering", de: "Weiter ausfüllen", fr: "Continuer à répondre", ar: "تابع الإجابة", tr: "Yanıtlamaya devam et", sq: "Vazhdo të përgjigjesh" },
  "q.answer":                   { en: "Answer", de: "Antworten", fr: "Répondre", ar: "أجب", tr: "Yanıtla", sq: "Përgjigju" },
  "q.no_grounding":             { en: "No fields were extracted from this PDF.", de: "Aus diesem PDF wurden keine Felder extrahiert.", fr: "Aucun champ n'a été extrait de ce PDF.", ar: "لم يتم استخراج أي حقول من ملف PDF هذا.", tr: "Bu PDF'den hiç alan çıkarılamadı.", sq: "Nuk u nxor asnjë fushë nga kjo PDF." },
  "q.no_grounding_body":        {
    en: "The app cannot safely generate questions without a verified PDF field map.",
    de: "Die App kann ohne eine verifizierte PDF-Feldzuordnung keine Fragen sicher generieren.",
    fr: "L'application ne peut pas générer de questions en toute sécurité sans une carte de champs PDF vérifiée.",
    ar: "لا يمكن للتطبيق إنشاء أسئلة بأمان بدون خريطة حقول PDF موثقة.",
    tr: "Uygulama doğrulanmış bir PDF alan haritası olmadan güvenli bir şekilde soru oluşturamaz.",
    sq: "Aplikacioni nuk mund të gjenerojë pyetje në mënyrë të sigurt pa një hartë të verifikuar të fushave të PDF-së.",
  },
  "q.upload_again":             { en: "Upload again", de: "Erneut hochladen", fr: "Téléverser à nouveau", ar: "إعادة الرفع", tr: "Tekrar yükle", sq: "Ringarko" },

  // ── Review page ─────────────────────────────────────────────────────────
  "review.title":               { en: "Review your answers", de: "Antworten überprüfen", fr: "Vérifiez vos réponses", ar: "راجع إجاباتك", tr: "Cevaplarınızı inceleyin", sq: "Rishikoni përgjigjet tuaja" },
  "review.instr":               { en: "Check everything before generating the PDF.", de: "Alles prüfen, bevor das PDF erstellt wird.", fr: "Vérifiez tout avant de générer le PDF.", ar: "تحقق من كل شيء قبل إنشاء PDF.", tr: "PDF'yi oluşturmadan önce kontrol edin.", sq: "Kontrolloni gjithçka para se të gjeneroni PDF-në." },
  "review.generate":            { en: "Generate & Download PDF", de: "PDF erstellen & herunterladen", fr: "Générer et télécharger le PDF", ar: "إنشاء وتنزيل PDF", tr: "PDF Oluştur ve İndir", sq: "Gjenero & Shkarko PDF" },
  "review.edit":                { en: "← Edit answers", de: "← Antworten bearbeiten", fr: "← Modifier les réponses", ar: "← تعديل الإجابات", tr: "← Yanıtları düzenle", sq: "← Modifiko përgjigjet" },
  "review.generating":          { en: "Generating PDF…", de: "PDF wird erstellt…", fr: "Génération du PDF…", ar: "جارٍ إنشاء PDF…", tr: "PDF oluşturuluyor…", sq: "Po gjenerohet PDF-ja…" },
  "review.no_token":            { en: "PDF session expired. Please re-upload your document.", de: "Sitzung abgelaufen. Bitte Dokument erneut hochladen.", fr: "La session PDF a expiré. Veuillez retéléverser votre document.", ar: "انتهت الجلسة. يرجى رفع المستند مرة أخرى.", tr: "Oturum süresi doldu. Lütfen belgeyi tekrar yükleyin.", sq: "Sesioni i PDF-së ka skaduar. Ringarkoni dokumentin tuaj." },
  "review.start_new":           { en: "Start a new form", de: "Neues Formular starten", fr: "Commencer un nouveau formulaire", ar: "ابدأ استمارة جديدة", tr: "Yeni form başlat", sq: "Fillo një formular të ri" },
  "review.manual_fields":       { en: "Must be filled in manually after printing:", de: "Nach dem Drucken manuell ausfüllen:", fr: "À remplir manuellement après impression :", ar: "يجب ملؤها يدويًا بعد الطباعة:", tr: "Yazdırdıktan sonra manuel doldurulmalı:", sq: "Duhet plotësuar manualisht pas printimit:" },
  "review.no_answers":          { en: "Please answer the questions first.", de: "Bitte beantworten Sie zuerst die Fragen.", fr: "Veuillez d'abord répondre aux questions.", ar: "يرجى الإجابة على الأسئلة أولاً.", tr: "Lütfen önce soruları yanıtlayın.", sq: "Ju lutemi përgjigjuni pyetjeve së pari." },
  "review.no_answers_yet":      { en: "No answers yet.", de: "Noch keine Antworten.", fr: "Aucune réponse pour le moment.", ar: "لا توجد إجابات بعد.", tr: "Henüz yanıt yok.", sq: "Ende pa përgjigje." },
  "review.disclaimer":          {
    en: "⚠️ This is a form completion tool only. We provide no legal advice. Please verify all information before submitting.",
    de: "⚠️ Dies ist nur eine Formular-Ausfüllhilfe. Wir geben keine Rechtsberatung. Bitte überprüfen Sie alle Angaben.",
    fr: "⚠️ Ceci est uniquement un outil d'aide au remplissage. Nous ne fournissons aucun conseil juridique. Vérifiez toutes les informations avant de soumettre.",
    ar: "⚠️ هذه أداة لمساعدتك في تعبئة الاستمارات فقط. لا نقدم أي استشارات قانونية.",
    tr: "⚠️ Bu yalnızca bir form doldurma aracıdır. Hukuki tavsiye vermiyoruz.",
    sq: "⚠️ Kjo është vetëm një vegël për plotësimin e formularëve. Nuk ofrojmë këshilla ligjore.",
  },
  "review.unanswered_n":        {
    en: "⚠ {n} question(s) not answered yet",
    de: "⚠ {n} Frage(n) noch nicht beantwortet",
    fr: "⚠ {n} question(s) sans réponse",
    ar: "⚠ {n} سؤال لم تتم الإجابة عنه بعد",
    tr: "⚠ {n} soru henüz yanıtlanmadı",
    sq: "⚠ {n} pyetje pa përgjigje",
  },
  "review.pdf_downloaded":      { en: "PDF downloaded!", de: "PDF heruntergeladen!", fr: "PDF téléchargé !", ar: "تم تنزيل PDF!", tr: "PDF indirildi!", sq: "PDF u shkarkua!" },
  "review.fitz_overlay_note":   {
    en: "✅ Written directly onto the original form layout",
    de: "✅ Direkt auf das ursprüngliche Formular-Layout geschrieben",
    fr: "✅ Écrit directement sur la mise en page d'origine",
    ar: "✅ كُتب مباشرة على تخطيط النموذج الأصلي",
    tr: "✅ Doğrudan orijinal form düzenine yazıldı",
    sq: "✅ Shkruar drejtpërdrejt mbi paraqitjen origjinale të formularit",
  },
  "review.submit_to_office":    {
    en: "Please submit it to the Jobcenter.",
    de: "Bitte beim Jobcenter einreichen.",
    fr: "Veuillez le remettre au Jobcenter.",
    ar: "يرجى تقديمه إلى مركز التشغيل (Jobcenter).",
    tr: "Lütfen Jobcenter'a teslim edin.",
    sq: "Ju lutemi dorëzojeni te Jobcenter.",
  },
  "review.reupload":            { en: "Re-upload", de: "Erneut hochladen", fr: "Retéléverser", ar: "إعادة التحميل", tr: "Tekrar yükle", sq: "Ringarko" },
  "review.ios_title":           { en: "On iPhone or iPad", de: "Auf iPhone oder iPad", fr: "Sur iPhone ou iPad", ar: "على iPhone أو iPad", tr: "iPhone veya iPad'de", sq: "Në iPhone ose iPad" },
  "review.ios_body":            {
    en: "Tap the Share button, then choose Save to Files to keep your completed PDF on this device.",
    de: "Tippen Sie auf das Teilen-Symbol und wählen Sie In Dateien sichern, um Ihre PDF auf diesem Gerät zu speichern.",
    fr: "Appuyez sur le bouton Partager, puis choisissez Enregistrer dans Fichiers pour conserver le PDF sur cet appareil.",
    ar: "اضغط على زر المشاركة، ثم اختر حفظ في الملفات للاحتفاظ بملف PDF على هذا الجهاز.",
    tr: "Paylaş düğmesine dokunun, sonra Dosyalar'a Kaydet seçeneğini seçin.",
    sq: "Prekni butonin Ndaj, pastaj zgjidhni Ruaj në Skedarë për të mbajtur PDF-në në këtë pajisje.",
  },

  // ── Download page ───────────────────────────────────────────────────────
  "download.title":             { en: "Your form is ready!", de: "Ihr Formular ist fertig!", fr: "Votre formulaire est prêt !", ar: "استمارتك جاهزة!", tr: "Formunuz hazır!", sq: "Formulari juaj është gati!" },
  "download.instruction":       {
    en: "Download the completed form and bring it to the Jobcenter.",
    de: "Laden Sie das ausgefüllte Formular herunter und bringen Sie es zum Jobcenter.",
    fr: "Téléchargez le formulaire complété et apportez-le au Jobcenter.",
    ar: "قم بتنزيل الاستمارة المكتملة وأحضرها إلى مركز التشغيل.",
    tr: "Tamamlanan formu indirin ve Jobcenter'a götürün.",
    sq: "Shkarkoni formularin e plotësuar dhe sillni te Jobcenter.",
  },
  "download.pdf":               { en: "Download PDF", de: "PDF herunterladen", fr: "Télécharger le PDF", ar: "تنزيل PDF", tr: "PDF İndir", sq: "Shkarko PDF" },

  // ── Yes/No (used by YesNoInput) ─────────────────────────────────────────
  "yn.yes":                     { en: "Yes", de: "Ja", fr: "Oui", ar: "نعم", tr: "Evet", sq: "Po" },
  "yn.no":                      { en: "No", de: "Nein", fr: "Non", ar: "لا", tr: "Hayır", sq: "Jo" },

  // ── Guidance panel ──────────────────────────────────────────────────────
  "guidance.toggle":            { en: "Need help understanding this?", de: "Erklärung anzeigen?", fr: "Besoin d'aide pour comprendre ?", ar: "هل تحتاج مساعدة في فهم هذا؟", tr: "Bu soruyu anlamak için yardım ister misiniz?", sq: "Keni nevojë për ndihmë me këtë?" },
  "guidance.hide":              { en: "Hide explanation", de: "Erklärung ausblenden", fr: "Masquer l'explication", ar: "إخفاء الشرح", tr: "Açıklamayı gizle", sq: "Fshih shpjegimin" },
  "guidance.plain":             { en: "In simple words", de: "Einfach erklärt", fr: "En termes simples", ar: "بكلمات بسيطة", tr: "Basit ifadeyle", sq: "Me fjalë të thjeshta" },
  "guidance.why":               { en: "Why is this asked?", de: "Warum wird das gefragt?", fr: "Pourquoi cette question ?", ar: "لماذا يُطرح هذا السؤال؟", tr: "Bu neden soruluyor?", sq: "Pse pyetet kjo?" },
  "guidance.where":             { en: "Where to find it", de: "Wo finde ich das?", fr: "Où le trouver", ar: "أين يمكن إيجاده؟", tr: "Nerede bulunur?", sq: "Ku mund ta gjej" },
  "guidance.format":            { en: "Format", de: "Format", fr: "Format", ar: "الصيغة", tr: "Format", sq: "Formati" },
  "guidance.example":           { en: "Example", de: "Beispiel", fr: "Exemple", ar: "مثال", tr: "Örnek", sq: "Shembull" },
  "guidance.docs":              { en: "Documents you may need", de: "Benötigte Unterlagen", fr: "Documents qui peuvent être nécessaires", ar: "المستندات التي قد تحتاجها", tr: "Gerekebilecek belgeler", sq: "Dokumentet që mund t'ju nevojiten" },
  "guidance.mistakes":          { en: "Common mistakes", de: "Häufige Fehler", fr: "Erreurs courantes", ar: "الأخطاء الشائعة", tr: "Sık yapılan hatalar", sq: "Gabime të zakonshme" },
  "guidance.disclaimer":        {
    en: "This is form assistance, not legal advice. Please review your answers before submitting.",
    de: "Dies ist Formularunterstützung, keine Rechtsberatung. Bitte prüfen Sie Ihre Angaben vor dem Einreichen.",
    fr: "Ceci est une aide au remplissage, pas un conseil juridique. Vérifiez vos réponses avant de soumettre.",
    ar: "هذه مساعدة في تعبئة النموذج، وليست استشارة قانونية. يرجى مراجعة إجاباتك قبل الإرسال.",
    tr: "Bu, form doldurma yardımıdır; hukuki danışmanlık değildir. Lütfen göndermeden önce yanıtlarınızı gözden geçirin.",
    sq: "Kjo është ndihmë me formularë, jo këshillë ligjore. Ju lutemi rishikoni përgjigjet tuaja para se të dorëzoni.",
  },
};

// Tier-B locales — fall back to English when missing.
function _resolve(key: string, locale: string): string {
  const dict = STRINGS[key];
  if (!dict) return key;
  return dict[locale] ?? dict["en"] ?? key;
}

export function t(key: string, locale: string, vars?: Record<string, string | number>): string {
  let s = _resolve(key, locale);
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

export function isRTL(locale: string): boolean {
  return ["ar", "fa", "he", "ur", "ps"].includes(locale);
}
