"use client";

import { useState } from "react";
import { GuidanceText } from "@/types/api";
import { t } from "@/lib/i18n";

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
        <span>{open ? t("guidance.hide", locale) : t("guidance.toggle", locale)}</span>
      </button>

      {open && (
        <div className="mt-3 p-4 bg-blue-50 border border-blue-100 rounded-xl text-sm space-y-4">

          {plain && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.plain", locale)}</p>
              <p className="text-gray-700 leading-relaxed">{plain}</p>
            </div>
          )}

          {why && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.why", locale)}</p>
              <p className="text-gray-700 leading-relaxed">{why}</p>
            </div>
          )}

          {where && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.where", locale)}</p>
              <p className="text-gray-700 leading-relaxed">{where}</p>
            </div>
          )}

          {format && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.format", locale)}</p>
              <p className="text-gray-700">{format}</p>
            </div>
          )}

          {example && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.example", locale)}</p>
              <code className="inline-block bg-white border border-blue-100 rounded px-2 py-0.5 text-gray-800 font-mono">
                {example}
              </code>
            </div>
          )}

          {docs.length > 0 && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.docs", locale)}</p>
              <ul className="list-disc list-inside space-y-0.5 text-gray-700">
                {docs.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </div>
          )}

          {mistakes.length > 0 && (
            <div>
              <p className="font-semibold text-gray-800 mb-1">{t("guidance.mistakes", locale)}</p>
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
            {t("guidance.disclaimer", locale)}
          </p>
        </div>
      )}
    </div>
  );
}
