"use client";

import { useState } from "react";
import { FieldDefinition } from "@/types/api";
import { resolveQuestionText } from "@/lib/labelUtils";

interface QuestionOverviewProps {
  questionFields: FieldDefinition[];
  answeredKeys: string[];
  answeredValues: Record<string, string>;
  currentKey: string | null;
  locale: string;
  onJumpTo: (key: string) => void;
  /** Used by resolveQuestionText to enforce strict Tier-A locale rules. */
  supportLevel?: number | null;
}

const TYPE_COLOR: Record<string, string> = {
  text:       "bg-blue-100 text-blue-700",
  date:       "bg-purple-100 text-purple-700",
  number:     "bg-indigo-100 text-indigo-700",
  checkbox:   "bg-orange-100 text-orange-700",
  radio:      "bg-pink-100 text-pink-700",
  select:     "bg-teal-100 text-teal-700",
  multiselect:"bg-teal-100 text-teal-700",
  yes_no:     "bg-orange-100 text-orange-700",
  signature:  "bg-gray-100 text-gray-500",
};

const OVERVIEW_LABEL: Record<string, string> = {
  en: "View all questions", de: "Alle Fragen anzeigen",
  ar: "عرض جميع الأسئلة", tr: "Tüm soruları görüntüle",
  fr: "Voir toutes les questions", es: "Ver todas las preguntas",
  sq: "Shiko të gjitha pyetjet", fa: "مشاهده همه سوالات",
  ru: "Показать все вопросы", uk: "Переглянути всі питання",
};
const HIDE_LABEL: Record<string, string> = {
  en: "Hide overview", de: "Übersicht ausblenden",
  ar: "إخفاء النظرة العامة", tr: "Genel bakışı gizle",
  fr: "Masquer l'aperçu", es: "Ocultar resumen",
  sq: "Fshih përshkrimin", fa: "پنهان کردن",
  ru: "Скрыть", uk: "Сховати",
};
const ANSWERED_LABEL: Record<string, string> = {
  en: "answered", de: "beantwortet", ar: "تمت الإجابة",
  tr: "yanıtlandı", fr: "répondu", es: "respondido",
  sq: "u përgjigj", fa: "پاسخ داده شد",
  ru: "отвечено", uk: "відповіли",
};
const MISSING_LABEL: Record<string, string> = {
  en: "missing", de: "fehlend", ar: "مفقود",
  tr: "eksik", fr: "manquant", es: "pendiente",
  sq: "mungon", fa: "ناقص",
  ru: "нет ответа", uk: "відсутній",
};
const OF_LABEL: Record<string, string> = {
  en: "of", de: "von", ar: "من", tr: "/",
  fr: "sur", es: "de", sq: "nga",
  fa: "از", ru: "из", uk: "з",
};

export function QuestionOverview({
  questionFields, answeredKeys, answeredValues, currentKey, locale, onJumpTo,
  supportLevel = null,
}: QuestionOverviewProps) {
  const [open, setOpen] = useState(false);

  const answeredCount = questionFields.filter(f => answeredKeys.includes(f.key)).length;
  const totalCount    = questionFields.length;
  const missingCount  = totalCount - answeredCount;

  const ovLabel  = OVERVIEW_LABEL[locale] ?? OVERVIEW_LABEL.en;
  const hideLabel = HIDE_LABEL[locale]    ?? HIDE_LABEL.en;
  const ofLabel  = OF_LABEL[locale]       ?? OF_LABEL.en;

  return (
    <div className="mb-4 rounded-2xl border border-gray-200 bg-white overflow-hidden shadow-sm">
      {/* Toggle button */}
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm text-gray-700 hover:bg-gray-50 transition-colors"
      >
        <span className="font-medium">{open ? hideLabel : ovLabel}</span>
        <span className="flex items-center gap-2 text-gray-400">
          <span className="text-xs">
            {answeredCount} {ofLabel} {totalCount}
            {missingCount > 0 && (
              <span className="ml-1.5 text-amber-600 font-semibold">· {missingCount} {MISSING_LABEL[locale] ?? MISSING_LABEL.en}</span>
            )}
          </span>
          <span>{open ? "▲" : "▼"}</span>
        </span>
      </button>

      {/* Scrollable question list */}
      {open && (
        <div className="border-t border-gray-100 max-h-72 overflow-y-auto divide-y divide-gray-50">
          {questionFields.map((field, idx) => {
            const isAnswered = answeredKeys.includes(field.key);
            const isCurrent  = field.key === currentKey;
            const qText = resolveQuestionText(
              field.question, field.original_label, field.key, locale,
              { isLevel1: supportLevel === 1 },
            );
            const rawAnswer  = answeredValues[field.key];

            return (
              <button
                key={field.key}
                type="button"
                onClick={() => { onJumpTo(field.key); setOpen(false); }}
                className={`w-full text-left px-4 py-2.5 flex gap-3 transition-colors hover:bg-gray-50 ${
                  isCurrent ? "bg-brand-50 border-l-4 border-brand-500 pl-3" : ""
                }`}
              >
                {/* Number */}
                <span className="flex-shrink-0 w-5 text-[11px] text-gray-400 pt-0.5 text-right">
                  {idx + 1}.
                </span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 leading-tight line-clamp-2">{qText}</p>
                  <p className="text-[11px] text-gray-400 mt-0.5 truncate">{field.original_label}</p>

                  <div className="flex flex-wrap items-center gap-1 mt-1">
                    {/* Field type */}
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${TYPE_COLOR[field.input_type] ?? "bg-gray-100 text-gray-600"}`}>
                      {field.input_type}
                    </span>

                    {/* Answer status */}
                    {isAnswered ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 font-medium">
                        ✓ {ANSWERED_LABEL[locale] ?? ANSWERED_LABEL.en}
                        {rawAnswer && field.input_type !== "checkbox" && field.input_type !== "yes_no" && (
                          <span className="ml-1 font-mono text-green-600 opacity-70">
                            — {String(rawAnswer).slice(0, 20)}{String(rawAnswer).length > 20 ? "…" : ""}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                        {MISSING_LABEL[locale] ?? MISSING_LABEL.en}
                      </span>
                    )}

                    {/* needs_review badge */}
                    {field.needs_review && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700">⚠</span>
                    )}

                    {/* guidance badge */}
                    {field.guidance && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-500">?</span>
                    )}
                  </div>
                </div>

                <span className="flex-shrink-0 text-gray-300 self-center">›</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
