"use client";

import React from "react";

/**
 * OutputGuarantee — Phase E/E3
 *
 * Visible right next to the "Generate & Download PDF" button on the review
 * screen, so the user understands exactly what they will get back BEFORE
 * they click. Eliminates the worst silent-failure mode: a user thinking
 * they got the original form but receiving a summary document.
 *
 * Copy per level:
 *   Level 1: original official PDF
 *   Level 2: PDF's digital form fields
 *   Level 3: a SEPARATE answer sheet (not the original form) — said explicitly
 *   Level 4: should never reach the review screen — show a stop message
 */

type Locale = "en" | "de" | "fr" | "ar" | "tr" | "sq" | "es" | "fa" | "ru" | "uk";

const STR: Record<Locale, { l1: string; l2: string; l3: string; l4: string }> = {
  en: {
    l1: "Verified form: your answers will be placed on the original official PDF.",
    l2: "Fillable PDF: your answers will be inserted into the PDF's digital form fields.",
    l3: "Note: we cannot fill this PDF directly. You will receive a separate answer sheet — copy your answers into the original form by hand.",
    l4: "This document type is not supported. Please upload a digital PDF.",
  },
  de: {
    l1: "Geprüftes Formular: Ihre Antworten werden auf der ursprünglichen offiziellen PDF platziert.",
    l2: "Ausfüllbare PDF: Ihre Antworten werden in die digitalen Formularfelder der PDF eingetragen.",
    l3: "Hinweis: Diese PDF kann nicht direkt ausgefüllt werden. Sie erhalten ein separates Antwortblatt — übertragen Sie Ihre Antworten von Hand in das Originalformular.",
    l4: "Dieser Dokumenttyp wird nicht unterstützt. Bitte laden Sie eine digitale PDF hoch.",
  },
  fr: {
    l1: "Formulaire vérifié : vos réponses seront placées sur le PDF officiel d'origine.",
    l2: "PDF remplissable : vos réponses seront insérées dans les champs de formulaire numériques du PDF.",
    l3: "Remarque : ce PDF ne peut pas être rempli directement. Vous recevrez une feuille de réponses séparée — recopiez vos réponses à la main sur le formulaire original.",
    l4: "Ce type de document n'est pas pris en charge. Veuillez téléverser un PDF numérique.",
  },
  ar: {
    l1: "نموذج موثق: ستوضع إجاباتك على ملف PDF الرسمي الأصلي.",
    l2: "PDF قابل للتعبئة: ستُدرج إجاباتك في حقول النموذج الرقمية في PDF.",
    l3: "ملاحظة: لا يمكن تعبئة هذا الملف مباشرةً. ستحصل على ورقة إجابات منفصلة — انقل إجاباتك يدويًا إلى النموذج الأصلي.",
    l4: "هذا النوع من المستندات غير مدعوم. يرجى تحميل ملف PDF رقمي.",
  },
  tr: {
    l1: "Doğrulanmış form: cevaplarınız orijinal resmi PDF'in üzerine yerleştirilecek.",
    l2: "Doldurulabilir PDF: cevaplarınız PDF'in dijital form alanlarına eklenecek.",
    l3: "Not: Bu PDF doğrudan doldurulamıyor. Ayrı bir cevap kağıdı alacaksınız — cevaplarınızı elle orijinal forma aktarın.",
    l4: "Bu belge türü desteklenmiyor. Lütfen dijital bir PDF yükleyin.",
  },
  sq: {
    l1: "Formular i verifikuar: përgjigjet tuaja do të vendosen në PDF-në zyrtare origjinale.",
    l2: "PDF i plotësueshëm: përgjigjet tuaja do të futen në fushat dixhitale të formularit të PDF.",
    l3: "Shënim: ky PDF nuk mund të plotësohet drejtpërdrejt. Do të merrni një fletë përgjigjesh të veçantë — kopjoni përgjigjet tuaja me dorë në formularin origjinal.",
    l4: "Ky lloj dokumenti nuk mbështetet. Ngarkoni një PDF dixhital.",
  },
  es: {
    l1: "Formulario verificado: sus respuestas se colocarán en el PDF oficial original.",
    l2: "PDF rellenable: sus respuestas se insertarán en los campos de formulario digitales del PDF.",
    l3: "Nota: este PDF no se puede rellenar directamente. Recibirá una hoja de respuestas separada — copie sus respuestas a mano en el formulario original.",
    l4: "Este tipo de documento no es compatible. Suba un PDF digital.",
  },
  fa: {
    l1: "فرم تأیید شده: پاسخ‌های شما روی PDF رسمی اصلی قرار خواهند گرفت.",
    l2: "PDF قابل تکمیل: پاسخ‌های شما در فیلدهای فرم دیجیتال PDF درج خواهند شد.",
    l3: "توجه: این PDF را نمی‌توان مستقیماً پر کرد. یک برگه پاسخ جداگانه دریافت می‌کنید — پاسخ‌های خود را با دست در فرم اصلی بنویسید.",
    l4: "این نوع سند پشتیبانی نمی‌شود. لطفاً یک PDF دیجیتال آپلود کنید.",
  },
  ru: {
    l1: "Проверенная форма: ваши ответы будут размещены на оригинальном официальном PDF.",
    l2: "Заполняемый PDF: ваши ответы будут вставлены в цифровые поля формы PDF.",
    l3: "Внимание: этот PDF нельзя заполнить напрямую. Вы получите отдельный лист с ответами — перенесите ответы в оригинальную форму от руки.",
    l4: "Этот тип документа не поддерживается. Загрузите цифровой PDF.",
  },
  uk: {
    l1: "Перевірена форма: ваші відповіді будуть розміщені на оригінальному офіційному PDF.",
    l2: "PDF, що заповнюється: ваші відповіді будуть вставлені у цифрові поля форми PDF.",
    l3: "Увага: цей PDF не можна заповнити безпосередньо. Ви отримаєте окремий аркуш з відповідями — перенесіть відповіді в оригінальну форму від руки.",
    l4: "Цей тип документа не підтримується. Завантажте цифровий PDF.",
  },
};

const KNOWN: Locale[] = ["en", "de", "fr", "ar", "tr", "sq", "es", "fa", "ru", "uk"];

function _strs(locale: string) {
  return STR[(KNOWN as string[]).includes(locale) ? (locale as Locale) : "en"];
}

interface Props {
  supportLevel: number | null;
  locale: string;
}

export function OutputGuarantee({ supportLevel, locale }: Props) {
  if (supportLevel == null) return null;
  const s = _strs(locale);

  let bg: string, border: string, text: string, copy: string, icon: string;
  switch (supportLevel) {
    case 1:
      bg = "bg-green-50"; border = "border-green-200"; text = "text-green-900";
      icon = "✓"; copy = s.l1;
      break;
    case 2:
      bg = "bg-blue-50"; border = "border-blue-200"; text = "text-blue-900";
      icon = "📄"; copy = s.l2;
      break;
    case 3:
      bg = "bg-amber-50"; border = "border-amber-200"; text = "text-amber-900";
      icon = "⚠"; copy = s.l3;
      break;
    default:
      bg = "bg-red-50"; border = "border-red-200"; text = "text-red-900";
      icon = "✕"; copy = s.l4;
      break;
  }

  return (
    <div
      role="status"
      data-testid="output-guarantee"
      className={`${bg} ${border} ${text} border rounded-xl px-4 py-3 mb-4 flex items-start gap-3`}
    >
      <span className="text-lg leading-none mt-0.5" aria-hidden>{icon}</span>
      <p className="text-sm leading-relaxed flex-1 min-w-0">{copy}</p>
    </div>
  );
}
