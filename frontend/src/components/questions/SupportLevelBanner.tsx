"use client";

import React from "react";

/**
 * SupportLevelBanner — visible trust signal at the top of the questions page.
 *
 * Reads `supportLevel` from the case store (mirrored from
 * AnalysisReport.support_level on the backend).
 *
 *   1 (verified)  → green   "Verified form"
 *   2 (acroform)  → blue    "Recognized form fields"
 *   3 (flat)      → amber   "Best-effort extraction"
 *   4 (scanned)   → red     "Not supported yet"   (R6.2 surface — see UnsupportedFormatScreen)
 *
 * Localized strings come from a small inline dict to avoid coupling to
 * the wider locales bundle. Keep entries short — banner is one line.
 */

type Locale = "en" | "de" | "fr" | "ar" | "tr" | "sq" | "es" | "fa" | "ru" | "uk";

const STR: Record<Locale, { l1: string; l2: string; l3: string; l4: string; l1d: string; l2d: string; l3d: string; l4d: string }> = {
  en: {
    l1: "Verified form",
    l2: "Fillable PDF",
    l3: "Best-effort extraction",
    l4: "Not supported yet",
    l1d: "Every question has been written and reviewed by a human.",
    l2d: "This PDF has digital form fields. We will fill those fields directly. Please review the final PDF before submitting.",
    l3d: "We did our best to find the questions. Some may be missing or unclear.",
    l4d: "We can't read this document yet. Please upload a digital PDF.",
  },
  de: {
    l1: "Geprüftes Formular",
    l2: "Ausfüllbare PDF",
    l3: "Beste-Annäherung",
    l4: "Noch nicht unterstützt",
    l1d: "Jede Frage wurde von einem Menschen geschrieben und überprüft.",
    l2d: "Diese PDF hat digitale Formularfelder. Wir füllen diese Felder direkt aus. Bitte prüfen Sie die fertige PDF vor dem Einreichen.",
    l3d: "Wir haben unser Bestes getan. Manche Fragen können fehlen oder unklar sein.",
    l4d: "Wir können dieses Dokument noch nicht lesen. Bitte laden Sie eine digitale PDF hoch.",
  },
  fr: {
    l1: "Formulaire vérifié",
    l2: "PDF remplissable",
    l3: "Extraction approximative",
    l4: "Non pris en charge",
    l1d: "Chaque question a été rédigée et vérifiée par un humain.",
    l2d: "Ce PDF contient des champs de formulaire numériques. Nous les remplirons directement. Vérifiez le PDF final avant de l'envoyer.",
    l3d: "Nous avons fait de notre mieux. Certaines questions peuvent manquer.",
    l4d: "Nous ne pouvons pas encore lire ce document. Veuillez téléverser un PDF numérique.",
  },
  ar: {
    l1: "نموذج موثق",
    l2: "PDF قابل للتعبئة",
    l3: "استخراج تقريبي",
    l4: "غير مدعوم بعد",
    l1d: "كل سؤال تمت كتابته ومراجعته من قبل إنسان.",
    l2d: "يحتوي هذا الملف على حقول نموذج رقمية. سنملأ تلك الحقول مباشرة. يرجى مراجعة الملف النهائي قبل التقديم.",
    l3d: "بذلنا قصارى جهدنا. قد تكون بعض الأسئلة مفقودة أو غير واضحة.",
    l4d: "لا يمكننا قراءة هذا المستند بعد. يرجى تحميل ملف PDF رقمي.",
  },
  tr: {
    l1: "Doğrulanmış form",
    l2: "Doldurulabilir PDF",
    l3: "En iyi tahmin",
    l4: "Henüz desteklenmiyor",
    l1d: "Her soru bir insan tarafından yazıldı ve incelendi.",
    l2d: "Bu PDF dijital form alanları içerir. Bu alanları doğrudan dolduracağız. Lütfen göndermeden önce son PDF'yi inceleyin.",
    l3d: "Elimizden geleni yaptık. Bazı sorular eksik veya belirsiz olabilir.",
    l4d: "Bu belgeyi henüz okuyamıyoruz. Lütfen dijital bir PDF yükleyin.",
  },
  sq: {
    l1: "Formular i verifikuar",
    l2: "PDF i plotësueshëm",
    l3: "Ekstraktim më i mirë",
    l4: "Ende nuk mbështetet",
    l1d: "Çdo pyetje është shkruar dhe rishikuar nga një njeri.",
    l2d: "Ky PDF ka fusha dixhitale formulari. Ne do t'i plotësojmë ato direkt. Ju lutemi rishikoni PDF-në përfundimtare para se ta dorëzoni.",
    l3d: "Bëmë më të mirën. Disa pyetje mund të mungojnë ose të jenë të paqarta.",
    l4d: "Nuk mund ta lexojmë këtë dokument ende. Ngarkoni një PDF dixhital.",
  },
  es: {
    l1: "Formulario verificado",
    l2: "PDF rellenable",
    l3: "Extracción aproximada",
    l4: "No compatible aún",
    l1d: "Cada pregunta ha sido escrita y revisada por un humano.",
    l2d: "Este PDF tiene campos de formulario digitales. Los rellenaremos directamente. Por favor revise el PDF final antes de enviarlo.",
    l3d: "Hicimos lo mejor posible. Algunas preguntas pueden faltar.",
    l4d: "Aún no podemos leer este documento. Suba un PDF digital.",
  },
  fa: {
    l1: "فرم تأیید شده",
    l2: "PDF قابل تکمیل",
    l3: "استخراج تقریبی",
    l4: "هنوز پشتیبانی نمی‌شود",
    l1d: "هر سؤال توسط یک انسان نوشته و بررسی شده است.",
    l2d: "این PDF دارای فیلدهای فرم دیجیتال است. ما آن فیلدها را مستقیماً پر می‌کنیم. لطفاً قبل از ارسال PDF نهایی را بررسی کنید.",
    l3d: "تمام تلاش خود را کردیم. ممکن است برخی سؤالات از دست رفته باشند.",
    l4d: "ما هنوز نمی‌توانیم این سند را بخوانیم. لطفاً یک PDF دیجیتال آپلود کنید.",
  },
  ru: {
    l1: "Проверенная форма",
    l2: "Заполняемый PDF",
    l3: "Приблизительное извлечение",
    l4: "Пока не поддерживается",
    l1d: "Каждый вопрос написан и проверен человеком.",
    l2d: "Этот PDF содержит цифровые поля формы. Мы заполним их напрямую. Пожалуйста, проверьте финальный PDF перед отправкой.",
    l3d: "Мы сделали всё возможное. Некоторые вопросы могут отсутствовать.",
    l4d: "Мы пока не можем прочитать этот документ. Загрузите цифровой PDF.",
  },
  uk: {
    l1: "Перевірена форма",
    l2: "PDF, що заповнюється",
    l3: "Приблизне видобування",
    l4: "Поки не підтримується",
    l1d: "Кожне питання написане та перевірене людиною.",
    l2d: "Цей PDF містить цифрові поля форми. Ми заповнимо їх напряму. Будь ласка, перевірте фінальний PDF перед поданням.",
    l3d: "Ми зробили все можливе. Деякі питання можуть бути відсутні.",
    l4d: "Ми поки не можемо прочитати цей документ. Завантажте цифровий PDF.",
  },
};

interface Props {
  supportLevel: number | null;
  locale: string;
  templateName?: string | null;
}

const KNOWN_LOCALES: Locale[] = [
  "en", "de", "fr", "ar", "tr", "sq", "es", "fa", "ru", "uk",
];

function _strs(locale: string) {
  const loc = (KNOWN_LOCALES as string[]).includes(locale)
    ? (locale as Locale)
    : "en";
  return STR[loc];
}

export function SupportLevelBanner({ supportLevel, locale, templateName }: Props) {
  if (supportLevel == null) return null;
  const s = _strs(locale);

  let bg: string, border: string, text: string, icon: string, title: string, desc: string;
  switch (supportLevel) {
    case 1:
      bg = "bg-green-50"; border = "border-green-200"; text = "text-green-800";
      icon = "✓"; title = s.l1; desc = s.l1d;
      break;
    case 2:
      bg = "bg-blue-50"; border = "border-blue-200"; text = "text-blue-800";
      icon = "📄"; title = s.l2; desc = s.l2d;
      break;
    case 3:
      bg = "bg-amber-50"; border = "border-amber-200"; text = "text-amber-800";
      icon = "⚠"; title = s.l3; desc = s.l3d;
      break;
    default:
      bg = "bg-red-50"; border = "border-red-200"; text = "text-red-800";
      icon = "✕"; title = s.l4; desc = s.l4d;
      break;
  }

  return (
    <div
      role="status"
      data-testid="support-level-banner"
      className={`${bg} ${border} ${text} border rounded-xl px-4 py-3 mb-4 flex items-start gap-3`}
    >
      <span className="text-xl leading-none mt-0.5" aria-hidden>{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm">
          {title}
          {supportLevel === 1 && templateName && (
            <span className="font-normal opacity-75"> — {templateName}</span>
          )}
        </p>
        <p className="text-xs opacity-90 mt-0.5">{desc}</p>
      </div>
    </div>
  );
}
