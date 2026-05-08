"use client";

import { useState } from "react";
import { GuidanceText } from "@/types/api";

interface GuidancePanelProps {
  guidance: GuidanceText;
  locale: string;
}

// Resolve a localised string: user locale → "en" → "de" → ""
function pick(dict: Record<string, string> | undefined, locale: string): string {
  if (!dict) return "";
  return dict[locale] ?? dict["en"] ?? dict["de"] ?? "";
}

// Resolve a localised string array
function pickList(dict: Record<string, string[]> | undefined, locale: string): string[] {
  if (!dict) return [];
  return dict[locale] ?? dict["en"] ?? dict["de"] ?? [];
}

const TOGGLE_LABEL: Record<string, string> = {
  en: "Need help understanding this?",
  de: "Erklärung anzeigen?",
  ar: "هل تحتاج مساعدة في فهم هذا؟",
  tr: "Bu soruyu anlamak için yardım ister misiniz?",
  fa: "آیا به کمک در درک این سوال نیاز دارید؟",
  ru: "Нужна помощь с этим вопросом?",
  uk: "Потрібна допомога з цим питанням?",
};

const HIDE_LABEL: Record<string, string> = {
  en: "Hide explanation",
  de: "Erklärung ausblenden",
  ar: "إخفاء الشرح",
  tr: "Açıklamayı gizle",
  fa: "پنهان کردن توضیحات",
  ru: "Скрыть объяснение",
  uk: "Приховати пояснення",
};

const SECTION_LABELS: Record<string, Record<string, string>> = {
  plain:     { en: "In simple words", de: "Einfach erklärt", ar: "بكلمات بسيطة", tr: "Basit ifadeyle", fa: "به زبان ساده", ru: "Простыми словами", uk: "Простими словами" },
  why:       { en: "Why is this asked?", de: "Warum wird das gefragt?", ar: "لماذا يُطرح هذا السؤال؟", tr: "Bu neden soruluyor?", fa: "چرا این پرسیده می‌شود؟", ru: "Почему это спрашивается?", uk: "Чому це запитується?" },
  where:     { en: "Where to find it", de: "Wo finde ich das?", ar: "أين يمكن إيجاده؟", tr: "Nerede bulunur?", fa: "کجا می‌توان آن را یافت؟", ru: "Где это найти", uk: "Де це знайти" },
  format:    { en: "Format", de: "Format", ar: "الصيغة", tr: "Format", fa: "قالب", ru: "Формат", uk: "Формат" },
  example:   { en: "Example", de: "Beispiel", ar: "مثال", tr: "Örnek", fa: "مثال", ru: "Пример", uk: "Приклад" },
  docs:      { en: "Documents you may need", de: "Benötigte Unterlagen", ar: "المستندات التي قد تحتاجها", tr: "Gerekebilecek belgeler", fa: "مدارک مورد نیاز", ru: "Необходимые документы", uk: "Необхідні документи" },
  mistakes:  { en: "Common mistakes", de: "Häufige Fehler", ar: "الأخطاء الشائعة", tr: "Sık yapılan hatalar", fa: "اشتباهات رایج", ru: "Частые ошибки", uk: "Поширені помилки" },
  disclaimer:{ en: "This is form assistance, not legal advice. Please review your answers before submitting.", de: "Dies ist Formularunterstützung, keine Rechtsberatung. Bitte prüfen Sie Ihre Angaben vor dem Einreichen.", ar: "هذه مساعدة في تعبئة النموذج، وليست استشارة قانونية. يرجى مراجعة إجاباتك قبل الإرسال.", tr: "Bu, form doldurma yardımıdır; hukuki danışmanlık değildir. Lütfen göndermeden önce yanıtlarınızı gözden geçirin.", fa: "این کمک در تکمیل فرم است، نه مشاوره حقوقی.", ru: "Это помощь с заполнением формы, а не юридическая консультация.", uk: "Це допомога з формою, а не юридична порада." },
};

function lbl(key: keyof typeof SECTION_LABELS, locale: string): string {
  return SECTION_LABELS[key]?.[locale] ?? SECTION_LABELS[key]?.["en"] ?? key;
}

export function GuidancePanel({ guidance, locale }: GuidancePanelProps) {
  const [open, setOpen] = useState(false);

  const plain     = pick(guidance.plain_language, locale);
  const why       = pick(guidance.why_needed, locale);
  const where     = pick(guidance.where_to_find, locale);
  const format    = pick(guidance.format_hint, locale);
  const example   = pick(guidance.example, locale);
  const docs      = pickList(guidance.required_documents, locale);
  const mistakes  = pickList(guidance.common_mistakes, locale);
  const warning   = pick(guidance.warning, locale);

  // If there is no content at all, render nothing
  const hasContent = plain || why || where || format || example || docs.length > 0 || mistakes.length > 0 || warning;
  if (!hasContent) return null;

  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 transition-colors"
      >
        <span className="text-xs">{open ? "▲" : "▼"}</span>
        <span>{open ? (HIDE_LABEL[locale] ?? HIDE_LABEL.en) : (TOGGLE_LABEL[locale] ?? TOGGLE_LABEL.en)}</span>
      </button>

      {open && (
        <div className="mt-3 p-4 bg-blue-50 border border-blue-100 rounded-xl text-sm space-y-4">

          {plain && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("plain", locale)}</p>
              <p className="text-gray-700 leading-relaxed">{plain}</p>
            </div>
          )}

          {why && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("why", locale)}</p>
              <p className="text-gray-700 leading-relaxed">{why}</p>
            </div>
          )}

          {where && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("where", locale)}</p>
              <p className="text-gray-700 leading-relaxed">{where}</p>
            </div>
          )}

          {format && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("format", locale)}</p>
              <p className="text-gray-700">{format}</p>
            </div>
          )}

          {example && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("example", locale)}</p>
              <code className="inline-block bg-white border border-blue-100 rounded px-2 py-0.5 text-gray-800 font-mono">
                {example}
              </code>
            </div>
          )}

          {docs.length > 0 && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("docs", locale)}</p>
              <ul className="list-disc list-inside space-y-0.5 text-gray-700">
                {docs.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}

          {mistakes.length > 0 && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{lbl("mistakes", locale)}</p>
              <ul className="list-disc list-inside space-y-0.5 text-gray-700">
                {mistakes.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            </div>
          )}

          {warning && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="font-semibold text-yellow-800 mb-1">⚠</p>
              <p className="text-yellow-800">{warning}</p>
            </div>
          )}

          <p className="text-xs text-gray-400 border-t border-blue-100 pt-3 leading-relaxed">
            {lbl("disclaimer", locale)}
          </p>
        </div>
      )}
    </div>
  );
}
